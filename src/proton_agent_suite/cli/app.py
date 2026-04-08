from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import typer
from rich.console import Console

from proton_agent_suite.domain.errors import ProtonAgentError
from proton_agent_suite.domain.services.calendar_service import CalendarService
from proton_agent_suite.domain.services.draft_service import DraftService
from proton_agent_suite.domain.services.invite_service import InviteService
from proton_agent_suite.domain.services.mail_service import MailService
from proton_agent_suite.domain.services.sync_service import SyncService
from proton_agent_suite.providers.bridge_mail.client import BridgeMailProvider
from proton_agent_suite.providers.radicale_calendar.provider import RadicaleCalendarProvider
from proton_agent_suite.security.credentials import EnvironmentCredentialStore
from proton_agent_suite.storage.db import create_session_factory, create_sqlite_engine
from proton_agent_suite.utils.json_output import dumps, error_payload, success_payload
from proton_agent_suite.utils.logging import configure_logging

app = typer.Typer(help="CLI suite for Proton Mail Bridge and Radicale/CalDAV")
console = Console()


@dataclass(slots=True)
class AppContext:
    json_mode: bool
    quiet: bool
    verbose: bool
    profile: str
    interactive: bool
    db_override: str | None
    env_file: Path | None
    settings: Any
    mail_service: MailService
    invite_service: InviteService
    calendar_service: CalendarService
    sync_service: SyncService
    draft_service: DraftService


def emit(ctx: AppContext, data: Any) -> None:
    if ctx.json_mode:
        typer.echo(dumps(success_payload(data)))
        return
    if not ctx.quiet:
        console.print(data)


def fail(ctx: AppContext | None, error: ProtonAgentError) -> None:
    if ctx is not None and ctx.json_mode:
        typer.echo(dumps(error_payload(error)))
    else:
        console.print(f"[red]{error.code.value}[/red] {error.message}")
        if error.details:
            console.print(error.details)
    raise typer.Exit(code=error.exit_code)


def get_ctx(context: typer.Context) -> AppContext:
    ctx = context.obj
    if not isinstance(ctx, AppContext):
        raise RuntimeError("Application context is not initialized")
    return ctx


def build_context(
    *,
    json_mode: bool,
    quiet: bool,
    verbose: bool,
    profile: str,
    db_override: str | None,
    interactive: bool,
    env_file: Path | None,
) -> AppContext:
    configure_logging(verbose=verbose, quiet=quiet)
    store = EnvironmentCredentialStore(env_file=env_file)
    settings = store.load_settings(profile=profile, db_override=db_override)
    engine = create_sqlite_engine(settings.db_path)
    session_factory = create_session_factory(engine)
    mail_provider = BridgeMailProvider(settings.bridge)
    calendar_provider = RadicaleCalendarProvider(
        settings.radicale,
        ics_public_base_url=settings.ics_public_base_url,
    )
    mail_service = MailService(session_factory, mail_provider)
    calendar_service = CalendarService(session_factory, calendar_provider)
    invite_service = InviteService(session_factory, mail_service, calendar_service)
    sync_service = SyncService(session_factory, mail_service, invite_service, calendar_service)
    draft_service = DraftService(session_factory, mail_service)
    return AppContext(
        json_mode=json_mode,
        quiet=quiet,
        verbose=verbose,
        profile=profile,
        interactive=interactive,
        db_override=db_override,
        env_file=env_file,
        settings=settings,
        mail_service=mail_service,
        invite_service=invite_service,
        calendar_service=calendar_service,
        sync_service=sync_service,
        draft_service=draft_service,
    )


@app.callback()
def main(
    context: typer.Context,
    json_mode: bool = typer.Option(False, "--json", help="Emit strict JSON output"),
    quiet: bool = typer.Option(False, "--quiet", help="Reduce human-readable output"),
    verbose: bool = typer.Option(False, "--verbose", help="Increase logging verbosity"),
    profile: str = typer.Option("default", "--profile", help="Configuration profile name"),
    db_override: str | None = typer.Option(None, "--db", help="SQLite path override"),
    interactive: bool = typer.Option(False, "--interactive", help="Allow interactive prompts"),
    env_file: Path | None = typer.Option(None, "--env-file", help="Path to .env file"),
) -> None:
    try:
        context.obj = build_context(
            json_mode=json_mode,
            quiet=quiet,
            verbose=verbose,
            profile=profile,
            db_override=db_override,
            interactive=interactive,
            env_file=env_file,
        )
    except ProtonAgentError as error:
        fail(None if context.obj is None else context.obj, error)


from proton_agent_suite.cli import agent, calendar, config, diagnostics, invites, mail, sync  # noqa: E402

app.add_typer(config.app, name="config")
app.add_typer(mail.app, name="mail")
app.add_typer(invites.app, name="invites")
app.add_typer(calendar.app, name="calendar")
app.add_typer(sync.app, name="sync")
app.add_typer(agent.app, name="agent")
app.add_typer(diagnostics.app, name="diagnostics")
