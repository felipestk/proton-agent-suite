from __future__ import annotations

import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path

from proton_agent_suite.domain.models import CalendarInfo, ConnectorInfo, EventAttendee, EventInfo, HealthCheckResult
from proton_agent_suite.domain.services.calendar_service import CalendarService
from proton_agent_suite.domain.services.invite_service import InviteService
from proton_agent_suite.domain.services.mail_service import MailService
from proton_agent_suite.domain.value_objects import MailSendRequest
from proton_agent_suite.storage.db import create_session_factory, create_sqlite_engine
from proton_agent_suite.utils.ids import stable_ref


class RecordingMailProvider:
    def __init__(self) -> None:
        self.sent: list[MailSendRequest] = []

    def healthcheck(self) -> HealthCheckResult:
        return HealthCheckResult(status="ok")

    def list_folders(self):
        return []

    def sync_folder(self, folder: str, since: datetime):
        return []

    def fetch_message(self, folder: str, uid: int):
        raise NotImplementedError

    def fetch_raw_message(self, folder: str, uid: int) -> bytes:
        raise NotImplementedError

    def send_message(self, request: MailSendRequest) -> dict[str, str]:
        self.sent.append(request)
        index = len(self.sent)
        return {
            "status": "sent",
            "message_id": f"<sent-{index}@example.com>",
            "sent_at": "2026-04-08T12:00:00Z",
        }

    def mark_read(self, folder: str, uid: int) -> None:
        raise NotImplementedError

    def mark_unread(self, folder: str, uid: int) -> None:
        raise NotImplementedError

    def move_message(self, source_folder: str, uid: int, target_folder: str) -> None:
        raise NotImplementedError

    def archive_message(self, source_folder: str, uid: int) -> None:
        raise NotImplementedError

    def list_labels(self) -> list[str]:
        return []

    def add_label(self, source_folder: str, uid: int, label_name: str) -> None:
        raise NotImplementedError

    def remove_label(self, message_id_header: str, label_name: str) -> None:
        raise NotImplementedError

    def normalize_folder_name(self, name: str) -> str:
        return name

    def create_folder(self, name: str):
        raise NotImplementedError

    def rename_folder(self, old_name: str, new_name: str):
        raise NotImplementedError

    def delete_folder(self, name: str) -> None:
        raise NotImplementedError


class RecordingCalendarProvider:
    def __init__(self) -> None:
        self.events: dict[str, EventInfo] = {}

    def healthcheck(self) -> HealthCheckResult:
        return HealthCheckResult(status="ok")

    def discover(self) -> list[CalendarInfo]:
        return []

    def list_calendars(self) -> list[CalendarInfo]:
        return []

    def get_calendar(self, calendar_ref: str) -> CalendarInfo:
        return CalendarInfo(ref=calendar_ref, name=calendar_ref, href=f"/calendars/{calendar_ref}/")

    def list_upcoming_events(self, days: int, calendar_ref: str | None = None) -> list[EventInfo]:
        return list(self.events.values())

    def changed_since(self, since: datetime, calendar_ref: str | None = None) -> list[EventInfo]:
        return list(self.events.values())

    def get_event(self, event_ref: str) -> EventInfo:
        return self.events[event_ref]

    def create_event(
        self,
        *,
        calendar_ref: str,
        title: str,
        start: datetime,
        end: datetime,
        timezone_name: str | None = None,
        description: str | None = None,
        location: str | None = None,
        organizer: str | None = None,
        organizer_common_name: str | None = None,
        attendees: list[EventAttendee] | None = None,
        status: str = "CONFIRMED",
        sequence: int = 0,
        uid: str | None = None,
    ) -> EventInfo:
        event = EventInfo(
            ref=stable_ref("evt", uid or title, ""),
            calendar_ref=calendar_ref,
            uid=uid or stable_ref("uid", calendar_ref, title, start.isoformat()),
            href=f"/events/{uid or title}.ics",
            etag=f'"etag-{len(self.events)}"',
            title=title,
            description=description,
            location=location,
            start_utc=start,
            end_utc=end,
            timezone_name=timezone_name,
            status=status.lower(),
            sequence=sequence,
            organizer=organizer,
            organizer_common_name=organizer_common_name,
            attendees=attendees or [],
        )
        self.events[event.ref] = event
        return event

    def update_event(self, event_ref: str, **kwargs) -> EventInfo:
        current = self.events[event_ref]
        updated = current.model_copy(
            update={
                "title": kwargs.get("title") or current.title,
                "description": kwargs.get("description")
                if kwargs.get("description") is not None
                else current.description,
                "location": kwargs.get("location") if kwargs.get("location") is not None else current.location,
                "start_utc": kwargs.get("start") or current.start_utc,
                "end_utc": kwargs.get("end") or current.end_utc,
                "timezone_name": kwargs.get("timezone_name") or current.timezone_name,
                "organizer": kwargs.get("organizer") or current.organizer,
                "organizer_common_name": kwargs.get("organizer_common_name") or current.organizer_common_name,
                "attendees": kwargs.get("attendees") if kwargs.get("attendees") is not None else current.attendees,
                "status": (kwargs.get("status") or current.status),
                "sequence": kwargs.get("sequence") if kwargs.get("sequence") is not None else current.sequence,
            }
        )
        self.events[event_ref] = updated
        return updated

    def cancel_event(self, event_ref: str) -> EventInfo:
        return self.update_event(event_ref, status="canceled")

    def delete_event(self, event_ref: str) -> None:
        self.events.pop(event_ref, None)

    def create_calendar(self, name: str) -> CalendarInfo:
        return CalendarInfo(ref=name, name=name, href=f"/calendars/{name}/")

    def update_calendar(self, calendar_ref: str, name: str | None = None) -> CalendarInfo:
        return CalendarInfo(ref=calendar_ref, name=name or calendar_ref, href=f"/calendars/{calendar_ref}/")

    def get_connector_info(self) -> ConnectorInfo:
        return ConnectorInfo(provider="radicale", caldav_base_url="https://example.com", username="user")

    def export_ics_url(self, calendar_ref: str | None = None) -> str | None:
        return None


def _create_legacy_schema(db_path: Path) -> None:
    connection = sqlite3.connect(db_path)
    try:
        connection.executescript(
            """
            CREATE TABLE outbound_mail (
                id TEXT PRIMARY KEY,
                message_id_header TEXT,
                subject TEXT,
                to_addresses TEXT NOT NULL DEFAULT '',
                cc_addresses TEXT NOT NULL DEFAULT '',
                bcc_addresses TEXT NOT NULL DEFAULT '',
                source_message_ref TEXT,
                status TEXT NOT NULL DEFAULT 'pending',
                response_json JSON,
                created_at TEXT,
                sent_at TEXT,
                updated_at TEXT
            );

            CREATE TABLE invite_records (
                id TEXT PRIMARY KEY,
                uid TEXT NOT NULL,
                organizer TEXT,
                recurrence_id TEXT,
                sequence INTEGER NOT NULL DEFAULT 0,
                method TEXT,
                status TEXT NOT NULL DEFAULT 'pending',
                summary TEXT,
                start_utc TEXT,
                end_utc TEXT,
                created_at TEXT,
                updated_at TEXT
            );

            CREATE TABLE events (
                id TEXT PRIMARY KEY,
                calendar_id TEXT,
                uid TEXT NOT NULL,
                href TEXT,
                etag TEXT,
                title TEXT NOT NULL,
                start_utc TEXT NOT NULL,
                end_utc TEXT NOT NULL,
                timezone_name TEXT,
                status TEXT NOT NULL DEFAULT 'confirmed',
                sequence INTEGER NOT NULL DEFAULT 0,
                organizer TEXT,
                recurrence_id TEXT,
                updated_at TEXT
            );
            """
        )
        connection.execute(
            """
            INSERT INTO invite_records(id, uid, organizer, recurrence_id, sequence, method, status, summary, start_utc, end_utc)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "legacy_invite",
                "invite-1",
                "owner@example.com",
                None,
                0,
                "REQUEST",
                "pending",
                "Legacy invite",
                "2026-04-10T09:00:00Z",
                "2026-04-10T10:00:00Z",
            ),
        )
        connection.commit()
    finally:
        connection.close()


def _create_partially_upgraded_schema(db_path: Path) -> None:
    connection = sqlite3.connect(db_path)
    try:
        connection.executescript(
            """
            CREATE TABLE outbound_mail (
                id TEXT PRIMARY KEY,
                message_id_header TEXT,
                subject TEXT,
                to_addresses TEXT NOT NULL DEFAULT '',
                cc_addresses TEXT NOT NULL DEFAULT '',
                bcc_addresses TEXT NOT NULL DEFAULT '',
                source_message_ref TEXT,
                related_invite_uid TEXT,
                invite_sequence INTEGER,
                method TEXT,
                status TEXT NOT NULL DEFAULT 'pending',
                response_json JSON,
                created_at TEXT,
                sent_at TEXT,
                updated_at TEXT
            );

            CREATE TABLE invite_records (
                id TEXT PRIMARY KEY,
                uid TEXT NOT NULL,
                organizer TEXT,
                organizer_common_name TEXT,
                recurrence_id TEXT,
                sequence INTEGER NOT NULL DEFAULT 0,
                method TEXT,
                status TEXT NOT NULL DEFAULT 'pending',
                summary TEXT,
                description TEXT,
                location TEXT,
                start_utc TEXT,
                end_utc TEXT,
                timezone_name TEXT,
                attendees JSON,
                calendar_ref TEXT,
                calendar_href TEXT,
                calendar_etag TEXT,
                source_message_ref TEXT,
                outbound_mail_ref TEXT,
                outbound_message_id TEXT,
                warning_flags JSON,
                reason_codes JSON,
                latest BOOLEAN NOT NULL DEFAULT 0,
                raw_ics TEXT,
                created_at TEXT,
                updated_at TEXT
            );

            CREATE TABLE invite_instances (
                id TEXT PRIMARY KEY,
                uid TEXT NOT NULL,
                organizer TEXT,
                recurrence_id TEXT,
                latest_record_id TEXT NOT NULL,
                current_status TEXT NOT NULL DEFAULT 'pending',
                start_utc TEXT,
                end_utc TEXT,
                updated_at TEXT
            );

            CREATE TABLE events (
                id TEXT PRIMARY KEY,
                calendar_id TEXT,
                uid TEXT NOT NULL,
                href TEXT,
                etag TEXT,
                title TEXT NOT NULL,
                description TEXT,
                location TEXT,
                start_utc TEXT NOT NULL,
                end_utc TEXT NOT NULL,
                timezone_name TEXT,
                status TEXT NOT NULL DEFAULT 'confirmed',
                sequence INTEGER NOT NULL DEFAULT 0,
                organizer TEXT,
                organizer_common_name TEXT,
                recurrence_id TEXT,
                raw_ics TEXT,
                deleted BOOLEAN NOT NULL DEFAULT 0,
                updated_at TEXT
            );

            CREATE TABLE event_attendees (
                id TEXT PRIMARY KEY,
                event_id TEXT NOT NULL,
                email TEXT NOT NULL,
                common_name TEXT,
                partstat TEXT,
                role TEXT,
                rsvp BOOLEAN
            );

            CREATE TABLE calendars (
                id TEXT PRIMARY KEY,
                provider TEXT NOT NULL DEFAULT 'radicale',
                name TEXT NOT NULL,
                href TEXT NOT NULL,
                url TEXT,
                etag TEXT,
                color TEXT,
                description TEXT,
                is_default BOOLEAN NOT NULL DEFAULT 0,
                created_at TEXT,
                updated_at TEXT
            );

            CREATE TABLE schema_migrations (
                version INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            """
        )
        connection.executemany(
            "INSERT INTO schema_migrations(version, name) VALUES (?, ?)",
            [
                (1, "bootstrap_schema"),
                (2, "additive_columns"),
                (3, "backfill_invite_state"),
                (4, "indexes"),
            ],
        )
        connection.execute(
            """
            INSERT INTO invite_records(
                id, uid, organizer, organizer_common_name, recurrence_id, sequence, method, status, summary,
                description, location, start_utc, end_utc, timezone_name, attendees, calendar_ref, calendar_href,
                calendar_etag, source_message_ref, outbound_mail_ref, outbound_message_id, warning_flags, reason_codes,
                latest, raw_ics, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "legacy_invite",
                "invite-1",
                "owner@example.com",
                "Owner",
                None,
                2,
                "REQUEST",
                "pending",
                "Legacy invite",
                "Planning session",
                "Lisbon",
                "2026-04-10T09:00:00Z",
                "2026-04-10T10:00:00Z",
                "Europe/Lisbon",
                '[{"email":"guest@example.com","common_name":"Guest","rsvp":true}]',
                "default",
                "/events/invite-1.ics",
                '"etag-legacy"',
                None,
                None,
                None,
                "[]",
                "[]",
                1,
                "BEGIN:VCALENDAR\nEND:VCALENDAR",
                "2026-04-08T12:00:00Z",
                "2026-04-08T12:00:00Z",
            ),
        )
        connection.execute(
            """
            INSERT INTO invite_instances(
                id, uid, organizer, recurrence_id, latest_record_id, current_status, start_utc, end_utc, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                stable_ref("ivi", "invite-1", "owner@example.com", ""),
                "invite-1",
                "owner@example.com",
                None,
                "legacy_invite",
                "pending",
                "2026-04-10T09:00:00Z",
                "2026-04-10T10:00:00Z",
                "2026-04-08T12:00:00Z",
            ),
        )
        connection.commit()
    finally:
        connection.close()


def _table_columns(db_path: Path, table_name: str) -> set[str]:
    connection = sqlite3.connect(db_path)
    try:
        rows = connection.execute(f'PRAGMA table_info("{table_name}")').fetchall()
        return {str(row[1]) for row in rows}
    finally:
        connection.close()


def _index_names(db_path: Path, table_name: str) -> set[str]:
    connection = sqlite3.connect(db_path)
    try:
        rows = connection.execute(f'PRAGMA index_list("{table_name}")').fetchall()
        return {str(row[1]) for row in rows}
    finally:
        connection.close()


def test_migrate_upgrades_existing_sqlite_schema(tmp_path: Path):
    db_path = tmp_path / "legacy.sqlite3"
    _create_legacy_schema(db_path)

    engine = create_sqlite_engine(db_path)
    create_session_factory(engine)

    assert {"description", "location", "organizer_common_name"}.issubset(_table_columns(db_path, "events"))
    assert {"related_invite_uid", "invite_sequence", "method"}.issubset(_table_columns(db_path, "outbound_mail"))
    assert {"attendees", "warning_flags", "reason_codes", "latest"}.issubset(_table_columns(db_path, "invite_records"))
    assert _table_columns(db_path, "invite_instances")
    assert _table_columns(db_path, "event_attendees")


def test_migrate_repairs_existing_invite_instances_schema_in_place(tmp_path: Path):
    db_path = tmp_path / "legacy.sqlite3"
    _create_partially_upgraded_schema(db_path)

    engine = create_sqlite_engine(db_path)
    create_session_factory(engine)

    invite_instance_columns = _table_columns(db_path, "invite_instances")
    invite_instance_indexes = _index_names(db_path, "invite_instances")

    assert {
        "uid",
        "organizer",
        "recurrence_id",
        "latest_record_id",
        "current_status",
        "start_utc",
        "end_utc",
        "calendar_ref",
        "calendar_href",
        "calendar_etag",
        "updated_at",
    }.issubset(invite_instance_columns)
    assert {"ix_invite_instances_calendar_ref", "uq_invite_instances_lookup"}.issubset(invite_instance_indexes)

    connection = sqlite3.connect(db_path)
    try:
        row = connection.execute(
            """
            SELECT uid, organizer, recurrence_id, latest_record_id, current_status, start_utc, end_utc,
                   calendar_ref, calendar_href, calendar_etag
            FROM invite_instances
            """
        ).fetchone()
        assert row == (
            "invite-1",
            "owner@example.com",
            None,
            "legacy_invite",
            "pending",
            "2026-04-10T09:00:00Z",
            "2026-04-10T10:00:00Z",
            "default",
            "/events/invite-1.ics",
            '"etag-legacy"',
        )
    finally:
        connection.close()


def test_migrate_is_idempotent_for_existing_sqlite_schema(tmp_path: Path):
    db_path = tmp_path / "legacy.sqlite3"
    _create_partially_upgraded_schema(db_path)

    engine = create_sqlite_engine(db_path)
    create_session_factory(engine)
    create_session_factory(engine)

    connection = sqlite3.connect(db_path)
    try:
        versions = connection.execute("SELECT version FROM schema_migrations ORDER BY version").fetchall()
        invite_instances = connection.execute("SELECT COUNT(*) FROM invite_instances").fetchone()
        assert [row[0] for row in versions] == [1, 2, 3, 4, 5]
        assert invite_instances == (1,)
    finally:
        connection.close()


def test_fresh_db_creation_runs_full_schema_bootstrap(tmp_path: Path):
    db_path = tmp_path / "fresh.sqlite3"

    engine = create_sqlite_engine(db_path)
    create_session_factory(engine)

    connection = sqlite3.connect(db_path)
    try:
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            ).fetchall()
        }
    finally:
        connection.close()

    assert {"events", "event_attendees", "invite_records", "invite_instances", "outbound_mail", "schema_migrations"}.issubset(
        tables
    )


def test_invite_workflows_and_sent_record_survive_legacy_db_upgrade(tmp_path: Path):
    db_path = tmp_path / "legacy.sqlite3"
    _create_partially_upgraded_schema(db_path)

    engine = create_sqlite_engine(db_path)
    session_factory = create_session_factory(engine)
    mail_service = MailService(session_factory, RecordingMailProvider())
    calendar_service = CalendarService(session_factory, RecordingCalendarProvider())
    invite_service = InviteService(session_factory, mail_service, calendar_service)

    start = datetime(2026, 4, 10, 9, 0, tzinfo=UTC)
    end = start + timedelta(hours=1)
    created = invite_service.create(
        calendar_ref="default",
        title="Migrated Demo",
        start=start,
        end=end,
        organizer="felipe@nurami.ai",
        organizer_common_name="Felipe",
        attendees=[EventAttendee(email="guest@example.com", common_name="Guest", rsvp=True)],
        description="Planning session",
        location="Lisbon",
        timezone_name="Europe/Lisbon",
    )
    updated = invite_service.update(created["invite"]["uid"], location="Porto")
    canceled = invite_service.cancel(created["invite"]["uid"])
    sent_record = mail_service.get_outbound(canceled["mail"]["sent_ref"])

    assert created["invite"]["location"] == "Lisbon"
    assert updated["invite"]["location"] == "Porto"
    assert canceled["invite"]["status"] == "canceled"
    assert created["invite"]["calendar_ref"] == "default"
    assert updated["invite"]["calendar_href"]
    assert canceled["invite"]["calendar_etag"]
    assert sent_record.related_invite_uid == created["invite"]["uid"]
    assert sent_record.method == "CANCEL"
