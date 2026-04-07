from __future__ import annotations

from pathlib import Path

import typer

from proton_agent_suite.cli.app import emit, fail, get_ctx
from proton_agent_suite.domain.errors import ProtonAgentError
from proton_agent_suite.domain.value_objects import MailSendRequest
from proton_agent_suite.utils.time import parse_since

app = typer.Typer(help="Mail commands backed by Proton Mail Bridge")


def _read_body(body_file: Path | None, stdin: bool) -> str:
    if body_file is not None:
        return body_file.read_text()
    if stdin:
        return typer.get_text_stream("stdin").read()
    return ""


@app.command("health")
def health(context: typer.Context) -> None:
    ctx = get_ctx(context)
    try:
        emit(ctx, ctx.mail_service.health())
    except ProtonAgentError as error:
        fail(ctx, error)


@app.command("folders")
def folders(context: typer.Context) -> None:
    ctx = get_ctx(context)
    emit(ctx, [folder.model_dump(mode="json") for folder in ctx.mail_service.folders()])


@app.command("sync")
def sync_mail(context: typer.Context, folder: str = typer.Option("Inbox", "--folder"), since: str = typer.Option("30d", "--since")) -> None:
    ctx = get_ctx(context)
    try:
        emit(ctx, ctx.mail_service.sync(folder, parse_since(since)))
    except ProtonAgentError as error:
        fail(ctx, error)


@app.command("list")
def list_messages(context: typer.Context, folder: str | None = typer.Option(None, "--folder"), limit: int = typer.Option(50, "--limit")) -> None:
    ctx = get_ctx(context)
    emit(ctx, [item.model_dump(mode="json") for item in ctx.mail_service.list_messages(folder=folder, limit=limit)])


@app.command("read")
def read(context: typer.Context, message_ref: str) -> None:
    ctx = get_ctx(context)
    try:
        emit(ctx, ctx.mail_service.read(message_ref))
    except ProtonAgentError as error:
        fail(ctx, error)


@app.command("raw")
def raw(context: typer.Context, message_ref: str) -> None:
    ctx = get_ctx(context)
    try:
        raw_bytes = ctx.mail_service.raw(message_ref)
        emit(ctx, {"message_ref": message_ref, "raw": raw_bytes.decode('utf-8', errors='replace')})
    except ProtonAgentError as error:
        fail(ctx, error)


@app.command("search")
def search(context: typer.Context, query: str, limit: int = typer.Option(50, "--limit")) -> None:
    ctx = get_ctx(context)
    emit(ctx, [item.model_dump(mode="json") for item in ctx.mail_service.search(query, limit=limit)])


@app.command("send")
def send(
    context: typer.Context,
    to: list[str] = typer.Option(..., "--to"),
    subject: str = typer.Option(..., "--subject"),
    body_file: Path | None = typer.Option(None, "--body-file"),
    stdin: bool = typer.Option(False, "--stdin"),
    cc: list[str] = typer.Option([], "--cc"),
    bcc: list[str] = typer.Option([], "--bcc"),
) -> None:
    ctx = get_ctx(context)
    request = MailSendRequest(to_addresses=to, cc_addresses=cc, bcc_addresses=bcc, subject=subject, body_text=_read_body(body_file, stdin))
    try:
        emit(ctx, ctx.mail_service.send(request))
    except ProtonAgentError as error:
        fail(ctx, error)


@app.command("draft")
def draft(
    context: typer.Context,
    to: list[str] = typer.Option(..., "--to"),
    subject: str = typer.Option(..., "--subject"),
    body_file: Path | None = typer.Option(None, "--body-file"),
    stdin: bool = typer.Option(False, "--stdin"),
    cc: list[str] = typer.Option([], "--cc"),
    bcc: list[str] = typer.Option([], "--bcc"),
) -> None:
    ctx = get_ctx(context)
    emit(
        ctx,
        ctx.mail_service.create_draft(
            to_addresses=to,
            cc_addresses=cc,
            bcc_addresses=bcc,
            subject=subject,
            body_text=_read_body(body_file, stdin),
        ),
    )


@app.command("drafts")
def drafts(context: typer.Context) -> None:
    ctx = get_ctx(context)
    emit(ctx, ctx.mail_service.list_drafts())


@app.command("send-draft")
def send_draft(context: typer.Context, draft_ref: str) -> None:
    ctx = get_ctx(context)
    try:
        emit(ctx, ctx.mail_service.send_draft(draft_ref))
    except ProtonAgentError as error:
        fail(ctx, error)


@app.command("reply")
def reply(context: typer.Context, message_ref: str, body_file: Path | None = typer.Option(None, "--body-file"), stdin: bool = typer.Option(False, "--stdin")) -> None:
    ctx = get_ctx(context)
    try:
        emit(ctx, ctx.mail_service.reply(message_ref, _read_body(body_file, stdin)))
    except ProtonAgentError as error:
        fail(ctx, error)


@app.command("attachments")
def attachments(context: typer.Context, message_ref: str) -> None:
    ctx = get_ctx(context)
    try:
        emit(ctx, [item.model_dump(mode="json") for item in ctx.mail_service.attachments(message_ref)])
    except ProtonAgentError as error:
        fail(ctx, error)


@app.command("save-attachment")
def save_attachment(context: typer.Context, message_ref: str, attachment_ref: str, out: Path = typer.Option(..., "--out")) -> None:
    ctx = get_ctx(context)
    try:
        emit(ctx, ctx.mail_service.save_attachment(message_ref, attachment_ref, out))
    except ProtonAgentError as error:
        fail(ctx, error)


@app.command("mark-read")
def mark_read(context: typer.Context, message_ref: str) -> None:
    ctx = get_ctx(context)
    try:
        emit(ctx, ctx.mail_service.mark_read(message_ref, True))
    except ProtonAgentError as error:
        fail(ctx, error)


@app.command("mark-unread")
def mark_unread(context: typer.Context, message_ref: str) -> None:
    ctx = get_ctx(context)
    try:
        emit(ctx, ctx.mail_service.mark_read(message_ref, False))
    except ProtonAgentError as error:
        fail(ctx, error)


@app.command("move")
def move(context: typer.Context, message_ref: str, folder: str = typer.Option(..., "--folder")) -> None:
    ctx = get_ctx(context)
    try:
        emit(ctx, ctx.mail_service.move(message_ref, folder))
    except ProtonAgentError as error:
        fail(ctx, error)


@app.command("archive")
def archive(context: typer.Context, message_ref: str) -> None:
    ctx = get_ctx(context)
    try:
        emit(ctx, ctx.mail_service.archive(message_ref))
    except ProtonAgentError as error:
        fail(ctx, error)


@app.command("labels")
def labels(context: typer.Context) -> None:
    ctx = get_ctx(context)
    try:
        emit(ctx, ctx.mail_service.labels())
    except ProtonAgentError as error:
        fail(ctx, error)


@app.command("add-label")
def add_label(context: typer.Context, message_ref: str, label_name: str) -> None:
    ctx = get_ctx(context)
    try:
        emit(ctx, ctx.mail_service.add_label(message_ref, label_name))
    except ProtonAgentError as error:
        fail(ctx, error)


@app.command("remove-label")
def remove_label(context: typer.Context, message_ref: str, label_name: str) -> None:
    ctx = get_ctx(context)
    try:
        emit(ctx, ctx.mail_service.remove_label(message_ref, label_name))
    except ProtonAgentError as error:
        fail(ctx, error)
