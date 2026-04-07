from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from proton_agent_suite.cli.app import app


runner = CliRunner()


def test_config_show_json(tmp_path: Path):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "PROTON_AGENT_DB_PATH=./test.sqlite3\n"
        "PROTON_AGENT_BRIDGE_HOST=127.0.0.1\n"
    )
    result = runner.invoke(app, ["--json", "--env-file", str(env_file), "config", "show"])
    assert result.exit_code == 0
    assert '"ok":true' in result.stdout
    assert '"db_path":"./test.sqlite3"' in result.stdout or '"db_path":"test.sqlite3"' in result.stdout


def test_calendar_delete_requires_yes_json(tmp_path: Path):
    env_file = tmp_path / ".env"
    env_file.write_text("PROTON_AGENT_DB_PATH=./test.sqlite3\n")
    result = runner.invoke(app, ["--json", "--env-file", str(env_file), "calendar", "delete", "evt_demo"])
    assert result.exit_code != 0
    assert '"code":"VALIDATION_ERROR"' in result.stdout
