from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from proton_agent_suite.cli.app import AppContext, app
from proton_agent_suite.domain.enums import MailboxKind
from proton_agent_suite.domain.models import FolderInfo, OutboundMessageInfo


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


def test_mail_folder_and_sent_record_json_shapes(monkeypatch):
    class FakeMailService:
        def folders(self):
            return [
                FolderInfo(
                    ref="fld_clients",
                    name="Clients/Felipe",
                    remote_name="Folders/Clients/Felipe",
                    kind=MailboxKind.FOLDER,
                )
            ]

        def get_outbound(self, sent_ref: str):
            assert sent_ref == "out_1"
            return OutboundMessageInfo(
                ref="out_1",
                status="sent",
                message_id="<out_1@example.com>",
                subject="Hello",
                to_addresses=["bob@example.com"],
                related_invite_uid="invite-1",
                method="REQUEST",
            )

    fake_context = AppContext(
        json_mode=True,
        quiet=False,
        verbose=False,
        profile="default",
        interactive=False,
        db_override=None,
        env_file=None,
        settings={},
        mail_service=FakeMailService(),
        invite_service=None,
        calendar_service=None,
        sync_service=None,
        draft_service=None,
    )

    monkeypatch.setattr("proton_agent_suite.cli.app.build_context", lambda **kwargs: fake_context)

    folders_result = runner.invoke(app, ["--json", "mail", "folders"])
    sent_record_result = runner.invoke(app, ["--json", "mail", "sent-record", "out_1"])

    assert folders_result.exit_code == 0
    assert '"name":"Clients/Felipe"' in folders_result.stdout
    assert '"remote_name":"Folders/Clients/Felipe"' in folders_result.stdout
    assert sent_record_result.exit_code == 0
    assert '"message_id":"<out_1@example.com>"' in sent_record_result.stdout
    assert '"related_invite_uid":"invite-1"' in sent_record_result.stdout
