from __future__ import annotations

from proton_agent_suite.domain.models import EventAttendee
import typer

from proton_agent_suite.cli.app import emit, fail, get_ctx
from proton_agent_suite.domain.enums import ErrorCode
from proton_agent_suite.domain.errors import ProtonAgentError, make_error
from proton_agent_suite.utils.time import parse_timestamp

app = typer.Typer(help="CalDAV/Radicale calendar commands")


def _require_yes(context: typer.Context, yes: bool) -> None:
    ctx = get_ctx(context)
    if yes or ctx.interactive:
        return
    fail(ctx, make_error(ErrorCode.VALIDATION_ERROR, "This action requires --yes", {"required": "--yes"}))


def _parse_attendees(values: list[str]) -> list[EventAttendee]:
    attendees: list[EventAttendee] = []
    for value in values:
        parts = [part.strip() for part in value.split("|") if part.strip()]
        if not parts:
            continue
        email = parts[0]
        fields: dict[str, object] = {"email": email}
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


@app.command("health")
def health(context: typer.Context) -> None:
    ctx = get_ctx(context)
    try:
        emit(ctx, ctx.calendar_service.health())
    except ProtonAgentError as error:
        fail(ctx, error)


@app.command("discover")
def discover(context: typer.Context) -> None:
    ctx = get_ctx(context)
    try:
        emit(ctx, [item.model_dump(mode="json") for item in ctx.calendar_service.discover()])
    except ProtonAgentError as error:
        fail(ctx, error)


@app.command("list")
@app.command("calendars")
def calendars(context: typer.Context) -> None:
    ctx = get_ctx(context)
    try:
        emit(ctx, [item.model_dump(mode="json") for item in ctx.calendar_service.calendars()])
    except ProtonAgentError as error:
        fail(ctx, error)


@app.command("connector")
def connector(context: typer.Context) -> None:
    ctx = get_ctx(context)
    try:
        emit(ctx, ctx.calendar_service.connector())
    except ProtonAgentError as error:
        fail(ctx, error)


@app.command("upcoming")
def upcoming(
    context: typer.Context,
    days: int = typer.Option(14, "--days"),
    calendar_ref: str | None = typer.Option(None, "--calendar"),
) -> None:
    ctx = get_ctx(context)
    try:
        emit(
            ctx,
            [
                item.model_dump(mode="json")
                for item in ctx.calendar_service.upcoming(days, calendar_ref=calendar_ref)
            ],
        )
    except ProtonAgentError as error:
        fail(ctx, error)


@app.command("changed-since")
def changed_since(
    context: typer.Context,
    since: str,
    calendar_ref: str | None = typer.Option(None, "--calendar"),
) -> None:
    ctx = get_ctx(context)
    try:
        emit(
            ctx,
            [
                item.model_dump(mode="json")
                for item in ctx.calendar_service.changed_since(
                    parse_timestamp(since),
                    calendar_ref=calendar_ref,
                )
            ],
        )
    except ProtonAgentError as error:
        fail(ctx, error)


@app.command("show")
def show(context: typer.Context, event_ref: str) -> None:
    ctx = get_ctx(context)
    try:
        emit(ctx, ctx.calendar_service.show(event_ref))
    except ProtonAgentError as error:
        fail(ctx, error)


@app.command("create")
def create(
    context: typer.Context,
    calendar: str = typer.Option(..., "--calendar"),
    title: str = typer.Option(..., "--title"),
    start: str = typer.Option(..., "--start"),
    end: str = typer.Option(..., "--end"),
    timezone: str | None = typer.Option(None, "--timezone"),
    description: str | None = typer.Option(None, "--description"),
    location: str | None = typer.Option(None, "--location"),
    organizer: str | None = typer.Option(None, "--organizer"),
    organizer_cn: str | None = typer.Option(None, "--organizer-cn"),
    attendee: list[str] = typer.Option([], "--attendee"),
) -> None:
    ctx = get_ctx(context)
    try:
        emit(
            ctx,
            ctx.calendar_service.create(
                calendar_ref=calendar,
                title=title,
                start=parse_timestamp(start),
                end=parse_timestamp(end),
                timezone_name=timezone,
                description=description,
                location=location,
                organizer=organizer,
                organizer_common_name=organizer_cn,
                attendees=_parse_attendees(attendee),
            ),
        )
    except ProtonAgentError as error:
        fail(ctx, error)


@app.command("update")
def update(
    context: typer.Context,
    event_ref: str,
    title: str | None = typer.Option(None, "--title"),
    start: str | None = typer.Option(None, "--start"),
    end: str | None = typer.Option(None, "--end"),
    timezone: str | None = typer.Option(None, "--timezone"),
    description: str | None = typer.Option(None, "--description"),
    location: str | None = typer.Option(None, "--location"),
    organizer: str | None = typer.Option(None, "--organizer"),
    organizer_cn: str | None = typer.Option(None, "--organizer-cn"),
    attendee: list[str] = typer.Option([], "--attendee"),
) -> None:
    ctx = get_ctx(context)
    try:
        emit(
            ctx,
            ctx.calendar_service.update(
                event_ref,
                title=title,
                start=parse_timestamp(start) if start else None,
                end=parse_timestamp(end) if end else None,
                timezone_name=timezone,
                description=description,
                location=location,
                organizer=organizer,
                organizer_common_name=organizer_cn,
                attendees=_parse_attendees(attendee) if attendee else None,
            ),
        )
    except ProtonAgentError as error:
        fail(ctx, error)


@app.command("reschedule")
def reschedule(
    context: typer.Context,
    event_ref: str,
    start: str = typer.Option(..., "--start"),
    end: str = typer.Option(..., "--end"),
) -> None:
    ctx = get_ctx(context)
    try:
        emit(
            ctx,
            ctx.calendar_service.update(
                event_ref,
                start=parse_timestamp(start),
                end=parse_timestamp(end),
            ),
        )
    except ProtonAgentError as error:
        fail(ctx, error)


@app.command("cancel")
def cancel(
    context: typer.Context,
    event_ref: str,
    yes: bool = typer.Option(False, "--yes"),
) -> None:
    _require_yes(context, yes)
    ctx = get_ctx(context)
    try:
        emit(ctx, ctx.calendar_service.cancel(event_ref))
    except ProtonAgentError as error:
        fail(ctx, error)


@app.command("delete")
def delete(
    context: typer.Context,
    event_ref: str,
    yes: bool = typer.Option(False, "--yes"),
) -> None:
    _require_yes(context, yes)
    ctx = get_ctx(context)
    try:
        emit(ctx, ctx.calendar_service.delete(event_ref))
    except ProtonAgentError as error:
        fail(ctx, error)


@app.command("create-calendar")
def create_calendar(
    context: typer.Context,
    name: str = typer.Option(..., "--name"),
) -> None:
    ctx = get_ctx(context)
    try:
        emit(ctx, ctx.calendar_service.create_calendar(name))
    except ProtonAgentError as error:
        fail(ctx, error)
