from __future__ import annotations

import typer

from proton_agent_suite.cli.app import emit, fail, get_ctx
from proton_agent_suite.domain.models import EventAttendee
from proton_agent_suite.domain.enums import InviteStatus
from proton_agent_suite.domain.errors import ProtonAgentError
from proton_agent_suite.utils.time import parse_timestamp

app = typer.Typer(help="Invite ingestion, RSVP, and organizer workflows")


def _parse_attendees(values: list[str]) -> list[EventAttendee]:
    attendees: list[EventAttendee] = []
    for value in values:
        parts = [part.strip() for part in value.split("|") if part.strip()]
        if not parts:
            continue
        fields: dict[str, object] = {"email": parts[0]}
        for item in parts[1:]:
            if "=" not in item:
                continue
            key, raw_value = item.split("=", 1)
            normalized = key.strip().lower()
            if normalized == "cn":
                fields["common_name"] = raw_value.strip()
            elif normalized == "role":
                fields["role"] = raw_value.strip()
            elif normalized == "partstat":
                fields["partstat"] = raw_value.strip()
            elif normalized == "rsvp":
                fields["rsvp"] = raw_value.strip().lower() in {"1", "true", "yes"}
        attendees.append(EventAttendee.model_validate(fields))
    return attendees


@app.command("scan")
def scan(context: typer.Context) -> None:
    ctx = get_ctx(context)
    try:
        emit(ctx, ctx.invite_service.scan())
    except ProtonAgentError as error:
        fail(ctx, error)


@app.command("list")
def list_invites(context: typer.Context, status: str | None = typer.Option(None, "--status")) -> None:
    ctx = get_ctx(context)
    emit(ctx, [item.model_dump(mode="json") for item in ctx.invite_service.list_latest(status=status)])


@app.command("show")
def show(context: typer.Context, invite_ref: str) -> None:
    ctx = get_ctx(context)
    try:
        emit(ctx, ctx.invite_service.get(invite_ref))
    except ProtonAgentError as error:
        fail(ctx, error)


@app.command("latest")
def latest(context: typer.Context) -> None:
    ctx = get_ctx(context)
    emit(ctx, [item.model_dump(mode="json") for item in ctx.invite_service.latest()])


@app.command("source")
def source(context: typer.Context, invite_ref: str) -> None:
    ctx = get_ctx(context)
    try:
        emit(ctx, ctx.invite_service.source(invite_ref))
    except ProtonAgentError as error:
        fail(ctx, error)


def _respond(context: typer.Context, invite_ref: str, status: InviteStatus, force: bool = False) -> None:
    ctx = get_ctx(context)
    try:
        emit(ctx, ctx.invite_service.respond(invite_ref, status, force=force))
    except ProtonAgentError as error:
        fail(ctx, error)


@app.command("accept")
def accept(context: typer.Context, invite_ref: str, force: bool = typer.Option(False, "--force")) -> None:
    _respond(context, invite_ref, InviteStatus.ACCEPTED, force=force)


@app.command("tentative")
def tentative(context: typer.Context, invite_ref: str, force: bool = typer.Option(False, "--force")) -> None:
    _respond(context, invite_ref, InviteStatus.TENTATIVE, force=force)


@app.command("decline")
def decline(context: typer.Context, invite_ref: str, force: bool = typer.Option(False, "--force")) -> None:
    _respond(context, invite_ref, InviteStatus.DECLINED, force=force)


@app.command("create")
def create(
    context: typer.Context,
    calendar: str = typer.Option(..., "--calendar"),
    title: str = typer.Option(..., "--title"),
    start: str = typer.Option(..., "--start"),
    end: str = typer.Option(..., "--end"),
    organizer: str = typer.Option(..., "--organizer"),
    organizer_cn: str | None = typer.Option(None, "--organizer-cn"),
    attendee: list[str] = typer.Option(..., "--attendee"),
    description: str | None = typer.Option(None, "--description"),
    location: str | None = typer.Option(None, "--location"),
    timezone: str | None = typer.Option(None, "--timezone"),
) -> None:
    ctx = get_ctx(context)
    try:
        emit(
            ctx,
            ctx.invite_service.create(
                calendar_ref=calendar,
                title=title,
                start=parse_timestamp(start),
                end=parse_timestamp(end),
                organizer=organizer,
                organizer_common_name=organizer_cn,
                attendees=_parse_attendees(attendee),
                description=description,
                location=location,
                timezone_name=timezone,
            ),
        )
    except ProtonAgentError as error:
        fail(ctx, error)


@app.command("update")
def update(
    context: typer.Context,
    invite_ref_or_uid: str,
    title: str | None = typer.Option(None, "--title"),
    start: str | None = typer.Option(None, "--start"),
    end: str | None = typer.Option(None, "--end"),
    organizer: str | None = typer.Option(None, "--organizer"),
    organizer_cn: str | None = typer.Option(None, "--organizer-cn"),
    attendee: list[str] = typer.Option([], "--attendee"),
    description: str | None = typer.Option(None, "--description"),
    location: str | None = typer.Option(None, "--location"),
    timezone: str | None = typer.Option(None, "--timezone"),
) -> None:
    ctx = get_ctx(context)
    try:
        emit(
            ctx,
            ctx.invite_service.update(
                invite_ref_or_uid,
                title=title,
                start=parse_timestamp(start) if start else None,
                end=parse_timestamp(end) if end else None,
                organizer=organizer,
                organizer_common_name=organizer_cn,
                attendees=_parse_attendees(attendee) if attendee else None,
                description=description,
                location=location,
                timezone_name=timezone,
            ),
        )
    except ProtonAgentError as error:
        fail(ctx, error)


@app.command("cancel")
def cancel(
    context: typer.Context,
    invite_ref_or_uid: str,
    keep_local_event: bool = typer.Option(False, "--keep-local-event"),
) -> None:
    ctx = get_ctx(context)
    try:
        emit(
            ctx,
            ctx.invite_service.cancel(invite_ref_or_uid, delete_local_event=not keep_local_event),
        )
    except ProtonAgentError as error:
        fail(ctx, error)
