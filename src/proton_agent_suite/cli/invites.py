from __future__ import annotations

import typer

from proton_agent_suite.cli.app import emit, fail, get_ctx
from proton_agent_suite.domain.enums import InviteStatus
from proton_agent_suite.domain.errors import ProtonAgentError

app = typer.Typer(help="Invite ingestion and RSVP commands")


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
