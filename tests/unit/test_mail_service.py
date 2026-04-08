from __future__ import annotations

from proton_agent_suite.domain.models import FolderInfo
from proton_agent_suite.domain.services.mail_service import MailService
from proton_agent_suite.domain.value_objects import MailSendRequest


class FakeMailProvider:
    def __init__(self) -> None:
        self.created: list[str] = []
        self.renamed: list[tuple[str, str]] = []
        self.deleted: list[str] = []
        self.sent: list[MailSendRequest] = []

    def send_message(self, request: MailSendRequest) -> dict[str, str]:
        self.sent.append(request)
        return {
            "status": "sent",
            "message_id": f"<sent-{len(self.sent)}@example.com>",
            "sent_at": "2026-04-08T12:00:00Z",
        }

    def create_folder(self, name: str) -> FolderInfo:
        self.created.append(name)
        return FolderInfo(ref=f"fld_{name}", name=name)

    def rename_folder(self, old_name: str, new_name: str) -> FolderInfo:
        self.renamed.append((old_name, new_name))
        return FolderInfo(ref=f"fld_{new_name}", name=new_name)

    def delete_folder(self, name: str) -> None:
        self.deleted.append(name)


def test_mail_send_records_outbound_message(session_factory):
    service = MailService(session_factory, FakeMailProvider())

    sent = service.send(MailSendRequest(to_addresses=["bob@example.com"], subject="Hello", body_text="Hi"))
    record = service.get_outbound(sent["sent_ref"])

    assert sent["status"] == "sent"
    assert sent["message_id"] == "<sent-1@example.com>"
    assert record.message_id == "<sent-1@example.com>"
    assert record.to_addresses == ["bob@example.com"]


def test_mail_folder_lifecycle_updates_provider_and_db(session_factory):
    provider = FakeMailProvider()
    service = MailService(session_factory, provider)

    created = service.create_folder("Clients/Felipe")
    renamed = service.rename_folder("Clients/Felipe", "Clients/Felipe-2026")
    deleted = service.delete_folder("Clients/Felipe-2026")

    assert created["name"] == "Clients/Felipe"
    assert renamed["name"] == "Clients/Felipe-2026"
    assert deleted["status"] == "deleted"
    assert provider.created == ["Clients/Felipe"]
    assert provider.renamed == [("Clients/Felipe", "Clients/Felipe-2026")]
    assert provider.deleted == ["Clients/Felipe-2026"]
