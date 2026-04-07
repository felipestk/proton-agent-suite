from __future__ import annotations

from datetime import UTC, datetime

from proton_agent_suite.domain.enums import ErrorCode, MailboxKind
from proton_agent_suite.providers.bridge_mail.client import BridgeMailProvider
from proton_agent_suite.domain.value_objects import BridgeSettings


class FakeImapClient:
    def __init__(self):
        self.selected = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def capabilities(self):
        return [b"IMAP4rev1"]

    def list_folders(self):
        return [((), "/", "Inbox"), ((), "/", "Labels/Work")]

    def select_folder(self, name, readonly=False):
        self.selected = name

    def search(self, criteria):
        return []


class BrokenBridgeProvider(BridgeMailProvider):
    def _connect(self):
        raise ConnectionRefusedError()


def test_list_folders_maps_labels(monkeypatch):
    provider = BridgeMailProvider(BridgeSettings(username="u", password="p"))
    monkeypatch.setattr(provider, "_connect", lambda: FakeImapClient())
    folders = provider.list_folders()
    assert folders[0].name == "Inbox"
    assert folders[1].kind == MailboxKind.LABEL
    assert provider.list_labels() == ["Work"]


def test_bridge_health_maps_connection_refused():
    provider = BrokenBridgeProvider(BridgeSettings(username="u", password="p"))
    try:
        provider.healthcheck()
    except Exception as exc:
        assert getattr(exc, "code").value in {ErrorCode.BRIDGE_NOT_RUNNING.value, ErrorCode.BRIDGE_SMTP_UNAVAILABLE.value}
    else:  # pragma: no cover
        raise AssertionError("expected bridge health error")
