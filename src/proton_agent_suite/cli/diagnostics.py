from __future__ import annotations

import sqlite3

import typer

from proton_agent_suite.cli.app import emit, get_ctx
from proton_agent_suite.security.credentials import validate_settings
from proton_agent_suite.security.permissions import describe_permissions, permissions_are_insecure

app = typer.Typer(help="Operational diagnostics")


@app.command("dump")
def dump(context: typer.Context) -> None:
    ctx = get_ctx(context)
    checks: dict[str, object] = {"config_problems": validate_settings(ctx.settings, env_file=ctx.env_file)}
    checks["db"] = {"path": str(ctx.settings.db_path), "ok": False}
    try:
        sqlite3.connect(ctx.settings.db_path).close()
        checks["db"]["ok"] = True
    except sqlite3.Error as exc:
        checks["db"]["error"] = str(exc)
    if ctx.env_file:
        checks["env_file"] = {
            "path": str(ctx.env_file),
            "permissions": describe_permissions(ctx.env_file),
            "insecure": permissions_are_insecure(ctx.env_file),
        }
    for key, fn in {
        "bridge": ctx.mail_service.health,
        "calendar": ctx.calendar_service.health,
        "connector": ctx.calendar_service.connector,
    }.items():
        try:
            result = fn()
            checks[key] = result.model_dump(mode="json") if hasattr(result, "model_dump") else result
        except Exception as exc:
            checks[key] = {"ok": False, "error": str(exc)}
    emit(ctx, checks)
