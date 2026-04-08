from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from sqlalchemy import inspect, text
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.exc import SQLAlchemyError

from proton_agent_suite.domain.enums import ErrorCode
from proton_agent_suite.domain.errors import make_error
from proton_agent_suite.storage.schema import Base
from proton_agent_suite.utils.ids import stable_ref


@dataclass(frozen=True, slots=True)
class MigrationStep:
    version: int
    name: str
    apply: Callable[[Connection], None]


def _quote(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


def _table_exists(connection: Connection, table_name: str) -> bool:
    return inspect(connection).has_table(table_name)


def _column_names(connection: Connection, table_name: str) -> set[str]:
    rows = connection.execute(text(f"PRAGMA table_info({_quote(table_name)})")).fetchall()
    return {str(row[1]) for row in rows}


def _add_column_if_missing(
    connection: Connection,
    *,
    table_name: str,
    column_name: str,
    ddl: str,
    backfill_sql: str | None = None,
) -> None:
    if not _table_exists(connection, table_name):
        return
    if column_name in _column_names(connection, table_name):
        return
    connection.execute(text(f"ALTER TABLE {_quote(table_name)} ADD COLUMN {_quote(column_name)} {ddl}"))
    if backfill_sql:
        connection.execute(text(backfill_sql))


def _create_index_if_missing(
    connection: Connection,
    *,
    index_name: str,
    table_name: str,
    columns: list[str],
    unique: bool = False,
) -> None:
    joined = ", ".join(_quote(column) for column in columns)
    unique_sql = "UNIQUE " if unique else ""
    connection.execute(
        text(f"CREATE {unique_sql}INDEX IF NOT EXISTS {_quote(index_name)} ON {_quote(table_name)} ({joined})")
    )


def _ensure_schema_migrations_table(connection: Connection) -> None:
    connection.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
    )


def _applied_versions(connection: Connection) -> set[int]:
    _ensure_schema_migrations_table(connection)
    rows = connection.execute(text("SELECT version FROM schema_migrations")).fetchall()
    return {int(row[0]) for row in rows}


def _record_migration(connection: Connection, step: MigrationStep) -> None:
    connection.execute(
        text("INSERT OR IGNORE INTO schema_migrations(version, name) VALUES (:version, :name)"),
        {"version": step.version, "name": step.name},
    )


def _bootstrap_schema(connection: Connection) -> None:
    Base.metadata.create_all(bind=connection)


def _migrate_additive_columns(connection: Connection) -> None:
    for column_name, ddl, backfill_sql in (
        ("related_invite_uid", "VARCHAR(255)", None),
        ("invite_sequence", "INTEGER", None),
        ("method", "VARCHAR(50)", None),
    ):
        _add_column_if_missing(
            connection,
            table_name="outbound_mail",
            column_name=column_name,
            ddl=ddl,
            backfill_sql=backfill_sql,
        )

    for column_name, ddl, backfill_sql in (
        ("description", "TEXT", None),
        ("location", "TEXT", None),
        ("timezone_name", "VARCHAR(128)", None),
        ("organizer_common_name", "VARCHAR(255)", None),
        ("recurrence_id", "VARCHAR(255)", None),
        ("raw_ics", "TEXT", None),
        ("deleted", "BOOLEAN NOT NULL DEFAULT 0", "UPDATE events SET deleted = 0 WHERE deleted IS NULL"),
    ):
        _add_column_if_missing(
            connection,
            table_name="events",
            column_name=column_name,
            ddl=ddl,
            backfill_sql=backfill_sql,
        )

    for column_name, ddl, backfill_sql in (
        ("organizer_common_name", "VARCHAR(255)", None),
        ("description", "TEXT", None),
        ("location", "TEXT", None),
        ("timezone_name", "VARCHAR(128)", None),
        ("attendees", "JSON", "UPDATE invite_records SET attendees = '[]' WHERE attendees IS NULL"),
        ("calendar_ref", "VARCHAR(32)", None),
        ("calendar_href", "VARCHAR(2048)", None),
        ("calendar_etag", "VARCHAR(255)", None),
        ("source_message_ref", "VARCHAR(32)", None),
        ("outbound_mail_ref", "VARCHAR(32)", None),
        ("outbound_message_id", "VARCHAR(998)", None),
        ("warning_flags", "JSON", "UPDATE invite_records SET warning_flags = '[]' WHERE warning_flags IS NULL"),
        ("reason_codes", "JSON", "UPDATE invite_records SET reason_codes = '[]' WHERE reason_codes IS NULL"),
        ("latest", "BOOLEAN NOT NULL DEFAULT 0", "UPDATE invite_records SET latest = 0 WHERE latest IS NULL"),
        ("raw_ics", "TEXT", None),
    ):
        _add_column_if_missing(
            connection,
            table_name="invite_records",
            column_name=column_name,
            ddl=ddl,
            backfill_sql=backfill_sql,
        )


def _ensure_invite_instances_columns(connection: Connection) -> None:
    for column_name, ddl, backfill_sql in (
        ("uid", "VARCHAR(255)", None),
        ("organizer", "VARCHAR(320)", None),
        ("recurrence_id", "VARCHAR(255)", None),
        ("latest_record_id", "VARCHAR(32)", None),
        ("current_status", "VARCHAR(20) NOT NULL DEFAULT 'pending'", "UPDATE invite_instances SET current_status = 'pending' WHERE current_status IS NULL"),
        ("start_utc", "DATETIME", None),
        ("end_utc", "DATETIME", None),
        ("calendar_ref", "VARCHAR(32)", None),
        ("calendar_href", "VARCHAR(2048)", None),
        ("calendar_etag", "VARCHAR(255)", None),
        ("updated_at", "DATETIME", None),
    ):
        _add_column_if_missing(
            connection,
            table_name="invite_instances",
            column_name=column_name,
            ddl=ddl,
            backfill_sql=backfill_sql,
        )


def _backfill_invite_state(connection: Connection) -> None:
    if not _table_exists(connection, "invite_records"):
        return
    columns = _column_names(connection, "invite_records")
    required = {"id", "uid", "organizer", "recurrence_id", "sequence", "status", "latest"}
    if not required.issubset(columns):
        return

    connection.execute(
        text(
            """
            UPDATE invite_records
            SET latest = CASE
                WHEN sequence = (
                    SELECT MAX(candidate.sequence)
                    FROM invite_records AS candidate
                    WHERE candidate.uid = invite_records.uid
                      AND candidate.organizer IS invite_records.organizer
                      AND candidate.recurrence_id IS invite_records.recurrence_id
                )
                THEN 1
                ELSE 0
            END
            """
        )
    )

    if not _table_exists(connection, "invite_instances"):
        return

    _ensure_invite_instances_columns(connection)
    connection.execute(text("DELETE FROM invite_instances"))
    latest_rows = connection.execute(
        text(
            """
            SELECT
                id,
                uid,
                organizer,
                recurrence_id,
                status,
                start_utc,
                end_utc,
                calendar_ref,
                calendar_href,
                calendar_etag
            FROM invite_records
            WHERE latest = 1
            """
        )
    ).mappings()
    for row in latest_rows:
        connection.execute(
            text(
                """
                INSERT INTO invite_instances(
                    id,
                    uid,
                    organizer,
                    recurrence_id,
                    latest_record_id,
                    current_status,
                    start_utc,
                    end_utc,
                    calendar_ref,
                    calendar_href,
                    calendar_etag
                ) VALUES (
                    :id,
                    :uid,
                    :organizer,
                    :recurrence_id,
                    :latest_record_id,
                    :current_status,
                    :start_utc,
                    :end_utc,
                    :calendar_ref,
                    :calendar_href,
                    :calendar_etag
                )
                """
            ),
            {
                "id": stable_ref("ivi", row["uid"], row["organizer"] or "", row["recurrence_id"] or ""),
                "uid": row["uid"],
                "organizer": row["organizer"],
                "recurrence_id": row["recurrence_id"],
                "latest_record_id": row["id"],
                "current_status": row["status"],
                "start_utc": row["start_utc"],
                "end_utc": row["end_utc"],
                "calendar_ref": row["calendar_ref"],
                "calendar_href": row["calendar_href"],
                "calendar_etag": row["calendar_etag"],
            },
        )


def _migrate_indexes(connection: Connection) -> None:
    for index_name, table_name, columns, unique in (
        ("ix_outbound_mail_related_invite_uid", "outbound_mail", ["related_invite_uid"], False),
        ("ix_outbound_mail_method", "outbound_mail", ["method"], False),
        ("ix_events_recurrence_id", "events", ["recurrence_id"], False),
        ("ix_invite_records_latest", "invite_records", ["latest"], False),
        ("ix_invite_records_calendar_ref", "invite_records", ["calendar_ref"], False),
        ("ix_invite_records_source_message_ref", "invite_records", ["source_message_ref"], False),
        ("ix_invite_records_outbound_mail_ref", "invite_records", ["outbound_mail_ref"], False),
        ("ix_invite_instances_uid", "invite_instances", ["uid"], False),
        ("ix_invite_instances_organizer", "invite_instances", ["organizer"], False),
        ("ix_invite_instances_recurrence_id", "invite_instances", ["recurrence_id"], False),
        ("ix_invite_instances_calendar_ref", "invite_instances", ["calendar_ref"], False),
        ("ix_event_attendees_event_id", "event_attendees", ["event_id"], False),
        ("ix_event_attendees_email", "event_attendees", ["email"], False),
        ("uq_invite_instances_lookup", "invite_instances", ["uid", "organizer", "recurrence_id"], True),
        ("uq_invite_record_lookup", "invite_records", ["uid", "organizer", "recurrence_id", "sequence"], True),
        ("uq_event_uid_recurrence", "events", ["uid", "recurrence_id"], True),
    ):
        if _table_exists(connection, table_name):
            _create_index_if_missing(
                connection,
                index_name=index_name,
                table_name=table_name,
                columns=columns,
                unique=unique,
            )


def _repair_invite_instances_schema(connection: Connection) -> None:
    if not _table_exists(connection, "invite_instances"):
        return
    _ensure_invite_instances_columns(connection)
    _backfill_invite_state(connection)
    _migrate_indexes(connection)


MIGRATIONS: tuple[MigrationStep, ...] = (
    MigrationStep(version=1, name="bootstrap_schema", apply=_bootstrap_schema),
    MigrationStep(version=2, name="additive_columns", apply=_migrate_additive_columns),
    MigrationStep(version=3, name="backfill_invite_state", apply=_backfill_invite_state),
    MigrationStep(version=4, name="indexes", apply=_migrate_indexes),
    MigrationStep(version=5, name="repair_invite_instances_schema", apply=_repair_invite_instances_schema),
)


def migrate(engine: Engine) -> None:
    try:
        with engine.begin() as connection:
            applied = _applied_versions(connection)
            for step in MIGRATIONS:
                if step.version in applied:
                    continue
                step.apply(connection)
                _record_migration(connection, step)
    except SQLAlchemyError as exc:
        raise make_error(
            ErrorCode.SQLITE_UNAVAILABLE,
            "SQLite schema migration failed",
            {"reason": str(exc)},
        ) from exc
