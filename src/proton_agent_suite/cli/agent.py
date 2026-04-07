from __future__ import annotations

from datetime import UTC, datetime, timedelta

import typer

from proton_agent_suite.cli.app import emit, get_ctx
from proton_agent_suite.domain.models import Snapshot, SyncStatus
from proton_agent_suite.providers.bridge_mail.mapper import MailMapper
from proton_agent_suite.storage.repositories.events import EventsRepository
from proton_agent_suite.storage.repositories.invites import InvitesRepository
from proton_agent_suite.storage.repositories.messages import MessagesRepository
from proton_agent_suite.storage.repositories.sync_state import SyncStateRepository

app = typer.Typer(help="Deterministic agent-facing polling commands")


@app.command("snapshot")
def snapshot(context: typer.Context) -> None:
    ctx = get_ctx(context)
    try:
        connector_info = ctx.calendar_service.connector()
    except Exception:
        connector_info = None
    with ctx.mail_service.session_factory() as session:
        message_repo = MessagesRepository(session)
        invite_repo = InvitesRepository(session)
        event_repo = EventsRepository(session)
        sync_repo = SyncStateRepository(session)
        data = Snapshot(
            generated_at=datetime.now(UTC),
            unread_messages=[MailMapper.summary_from_row(row) for row in message_repo.unread(limit=20)],
            pending_invites=[ctx.invite_service._view(row) for row in invite_repo.list_latest(status="pending", limit=20)],
            upcoming_events=[
                ctx.calendar_service._event_from_row(row)
                for row in event_repo.list_before(datetime.now(UTC) + timedelta(days=14), limit=20)
            ],
            sync_status=[
                SyncStatus(
                    scope=row.scope,
                    last_success_utc=row.last_success_utc,
                    last_error_code=row.last_error_code,
                    details=row.details_json,
                )
                for row in sync_repo.list_all()
            ],
            recent_failures=[
                {
                    "scope": row.scope,
                    "remote_key": row.remote_key,
                    "last_error_code": row.last_error_code,
                    "last_error_at": row.last_error_at,
                }
                for row in sync_repo.list_all()
                if row.last_error_code
            ],
            connector_info=connector_info,
            changed_refs={},
        )
    emit(ctx, data)


@app.command("changed-since")
def changed_since(context: typer.Context, since: str) -> None:
    from proton_agent_suite.utils.time import parse_timestamp

    ctx = get_ctx(context)
    timestamp = parse_timestamp(since)
    try:
        connector = ctx.calendar_service.connector().model_dump(mode="json")
    except Exception:
        connector = None
    with ctx.mail_service.session_factory() as session:
        message_refs = [row.id for row in MessagesRepository(session).changed_since(timestamp)]
        invite_refs = [row.id for row in InvitesRepository(session).changed_since(timestamp)]
        event_refs = [row.id for row in EventsRepository(session).changed_since(timestamp)]
    emit(
        ctx,
        {
            "generated_at": datetime.now(UTC),
            "since": timestamp,
            "changed_refs": {"messages": message_refs, "invites": invite_refs, "events": event_refs},
            "connector_info": connector,
        },
    )
