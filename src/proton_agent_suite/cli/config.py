from __future__ import annotations

from pathlib import Path

import typer

from proton_agent_suite.cli.app import emit, fail, get_ctx
from proton_agent_suite.domain.enums import ErrorCode
from proton_agent_suite.domain.errors import make_error
from proton_agent_suite.security.credentials import EnvironmentCredentialStore, validate_settings

app = typer.Typer(help="Configuration and setup commands")


@app.command("init")
def config_init(
    context: typer.Context,
    out: Path = typer.Option(Path(".env"), "--out", help="Output env file"),
    force: bool = typer.Option(False, "--force"),
) -> None:
    ctx = get_ctx(context)
    if out.exists() and not force:
        fail(
            ctx,
            make_error(
                ErrorCode.VALIDATION_ERROR,
                f"{out} already exists. Use --force to overwrite.",
                {"path": str(out)},
            ),
        )
    example = Path(__file__).resolve().parents[3] / ".env.example"
    out.write_text(example.read_text())
    emit(ctx, {"path": str(out), "created": True})


@app.command("doctor")
def doctor(context: typer.Context) -> None:
    ctx = get_ctx(context)
    store = EnvironmentCredentialStore(env_file=ctx.env_file)
    settings = store.load_settings(profile=ctx.profile, db_override=ctx.db_override)
    problems = validate_settings(settings, env_file=ctx.env_file)
    emit(ctx, {"settings": settings.redacted_dict(), "problems": problems})


@app.command("show")
def show(context: typer.Context) -> None:
    ctx = get_ctx(context)
    emit(ctx, ctx.settings.redacted_dict())


@app.command("validate")
def validate(context: typer.Context) -> None:
    ctx = get_ctx(context)
    store = EnvironmentCredentialStore(env_file=ctx.env_file)
    settings = store.load_settings(profile=ctx.profile, db_override=ctx.db_override)
    problems = validate_settings(settings, env_file=ctx.env_file)
    emit(ctx, {"valid": not problems, "problems": problems})
