from __future__ import annotations

import typer

from proton_agent_suite.cli.app import emit, fail, get_ctx
from proton_agent_suite.domain.errors import ProtonAgentError
from proton_agent_suite.utils.time import parse_since

app = typer.Typer(help="Synchronization commands")


@app.command("all")
def sync_all(context: typer.Context) -> None:
    ctx = get_ctx(context)
    try:
        emit(ctx, ctx.sync_service.sync_all())
    except ProtonAgentError as error:
        fail(ctx, error)


@app.command("mail")
def sync_mail(context: typer.Context, folder: str = typer.Option("Inbox", "--folder"), since: str = typer.Option("30d", "--since")) -> None:
    ctx = get_ctx(context)
    try:
        emit(ctx, ctx.sync_service.sync_mail(folder=folder, since=parse_since(since)))
    except ProtonAgentError as error:
        fail(ctx, error)


@app.command("invites")
def sync_invites(context: typer.Context) -> None:
    ctx = get_ctx(context)
    try:
        emit(ctx, ctx.sync_service.sync_invites())
    except ProtonAgentError as error:
        fail(ctx, error)


@app.command("calendar")
def sync_calendar(context: typer.Context, days: int = typer.Option(30, "--days")) -> None:
    ctx = get_ctx(context)
    try:
        emit(ctx, ctx.sync_service.sync_calendar(days=days))
    except ProtonAgentError as error:
        fail(ctx, error)
