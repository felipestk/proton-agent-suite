from __future__ import annotations

from pathlib import Path

from proton_agent_suite.domain.enums import ErrorCode, InviteStatus
from proton_agent_suite.domain.services.invite_service import InviteService
from proton_agent_suite.providers.bridge_mail.parser import MessageParser
from proton_agent_suite.storage.repositories.attachments import AttachmentsRepository
from proton_agent_suite.storage.repositories.messages import MessagesRepository


class DummyMailProvider:
    def __init__(self) -> None:
        self.sent: list[object] = []

    def send_message(self, request):
        self.sent.append(request)
        return {"status": "sent"}


def _seed_message(session_factory, fixtures_dir: Path, filename: str, ref_suffix: int) -> str:
    raw = (fixtures_dir / "messages" / filename).read_bytes()
    parsed = MessageParser().parse_bytes(raw)
    with session_factory() as session:
        message_row = MessagesRepository(session).upsert_message(
            folder_name="Inbox",
            imap_uid=ref_suffix,
            message_id_header=parsed.message_id_header or f"<message-{ref_suffix}@example.com>",
            subject=parsed.subject,
            from_address=parsed.from_address,
            to_addresses=parsed.to_addresses,
            cc_addresses=parsed.cc_addresses,
            date_utc=parsed.date_utc,
            internal_date_utc=None,
            is_read=False,
            text_body=parsed.text_body,
            html_body=parsed.html_body,
            raw_rfc822=raw,
            has_attachments=bool(parsed.attachments),
            invite_hint=parsed.invite_hint,
            checksum=parsed.checksum,
        )
        session.commit()
        return message_row.id


def test_invite_scan_deduplicates_and_tracks_latest(session_factory, fixtures_dir: Path):
    provider = DummyMailProvider()
    service = InviteService(session_factory, provider)
    _seed_message(session_factory, fixtures_dir, "new_invite.eml", 1)
    _seed_message(session_factory, fixtures_dir, "updated_invite.eml", 2)

    result = service.scan()
    assert result["scanned"] == 2

    latest = service.list_latest()
    assert len(latest) == 1
    assert latest[0].sequence == 2
    assert latest[0].summary == "Demo Meeting Updated"


def test_invite_scan_marks_cancellations(session_factory, fixtures_dir: Path):
    provider = DummyMailProvider()
    service = InviteService(session_factory, provider)
    _seed_message(session_factory, fixtures_dir, "canceled_invite.eml", 3)

    service.scan()
    latest = service.list_latest()
    assert latest[0].status == InviteStatus.CANCELED


def test_forwarded_invite_requires_force_for_rsvp(session_factory, fixtures_dir: Path):
    provider = DummyMailProvider()
    service = InviteService(session_factory, provider)
    _seed_message(session_factory, fixtures_dir, "forwarded_invite.eml", 4)
    service.scan()
    invite = service.latest()[0]
    assert "forwarded" in invite.warning_flags
    try:
        service.respond(invite.ref, InviteStatus.ACCEPTED)
    except Exception as exc:
        assert getattr(exc, "code").value == ErrorCode.INVITE_UNSAFE_TO_RSVP.value
    else:  # pragma: no cover
        raise AssertionError("expected unsafe RSVP failure")


def test_safe_rsvp_sends_mail(session_factory, fixtures_dir: Path):
    provider = DummyMailProvider()
    service = InviteService(session_factory, provider)
    _seed_message(session_factory, fixtures_dir, "new_invite.eml", 5)
    service.scan()
    invite = service.latest()[0]
    result = service.respond(invite.ref, InviteStatus.ACCEPTED)
    assert result["status"] == InviteStatus.ACCEPTED.value
    assert len(provider.sent) == 1
