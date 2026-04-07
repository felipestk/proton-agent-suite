from __future__ import annotations

from datetime import UTC, date, datetime, time
from email import policy
from email.parser import BytesParser

from icalendar import Calendar
from sqlalchemy.orm import Session, sessionmaker

from proton_agent_suite.domain.enums import ErrorCode, InviteStatus
from proton_agent_suite.domain.errors import make_error
from proton_agent_suite.domain.models import InviteRecordView, MessageDetail
from proton_agent_suite.domain.protocols import MailProvider
from proton_agent_suite.domain.value_objects import MailSendRequest
from proton_agent_suite.providers.radicale_calendar.ics import CalendarIcsCodec
from proton_agent_suite.storage.repositories.invites import InvitesRepository
from proton_agent_suite.storage.repositories.messages import MessagesRepository
from proton_agent_suite.utils.time import ensure_utc


def _to_utc_datetime(value: date | datetime | None) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return ensure_utc(value)
    return ensure_utc(datetime.combine(value, time.min, tzinfo=UTC))


class InviteService:
    def __init__(self, session_factory: sessionmaker[Session], mail_provider: MailProvider) -> None:
        self.session_factory = session_factory
        self.mail_provider = mail_provider
        self._ics_codec = CalendarIcsCodec()

    def _extract_ics_payloads(self, message_row: object) -> list[str]:
        payloads: list[str] = []
        raw_rfc822 = getattr(message_row, "raw_rfc822", None)
        if raw_rfc822:
            parsed = BytesParser(policy=policy.default).parsebytes(raw_rfc822)
            for part in parsed.walk():
                content_type = part.get_content_type()
                filename = (part.get_filename() or "").lower()
                if content_type == "text/calendar" or filename.endswith(".ics"):
                    raw = part.get_payload(decode=True) or b""
                    payloads.append(raw.decode(part.get_content_charset() or "utf-8", errors="replace"))
        return payloads

    def _warning_flags(
        self,
        subject: str | None,
        from_address: str | None,
        organizer: str | None,
        text_body: str | None,
    ) -> tuple[list[str], list[str]]:
        flags: list[str] = []
        reasons: list[str] = []
        joined = "\n".join(filter(None, [subject or "", text_body or ""]))
        lowered = joined.lower()
        if subject and subject.lower().startswith(("fwd:", "fw:")):
            flags.append("forwarded")
            reasons.append("FORWARDED_SUBJECT")
        if "forwarded message" in lowered:
            flags.append("forwarded")
            reasons.append("FORWARDED_BODY")
        if organizer and from_address and organizer.lower() != from_address.lower():
            flags.append("untrusted_sender")
            reasons.append("ORGANIZER_SENDER_MISMATCH")
        return sorted(set(flags)), sorted(set(reasons))

    def scan(self) -> dict[str, object]:
        created: list[str] = []
        with self.session_factory() as session:
            messages = [row for row in MessagesRepository(session).list_messages(limit=1000) if row.invite_hint]
            repo = InvitesRepository(session)
            for message in messages:
                payloads = self._extract_ics_payloads(message)
                for payload in payloads:
                    try:
                        calendar = Calendar.from_ical(payload)
                    except Exception as exc:
                        raise make_error(
                            ErrorCode.INVITE_PARSE_FAILED,
                            "Failed to parse invite ICS",
                            {"message_ref": message.id},
                        ) from exc
                    method = str(calendar.get("METHOD") or "REQUEST")
                    for component in calendar.walk("VEVENT"):
                        uid = str(component.get("UID"))
                        organizer = (
                            str(component.get("ORGANIZER") or "")
                            .removeprefix("MAILTO:")
                            .removeprefix("mailto:")
                            or None
                        )
                        sequence = int(component.get("SEQUENCE") or 0)
                        summary = str(component.get("SUMMARY") or "") or None
                        recurrence_id = str(component.get("RECURRENCE-ID") or "") or None
                        start = component.decoded("DTSTART") if component.get("DTSTART") else None
                        end = component.decoded("DTEND") if component.get("DTEND") else start
                        start_utc = _to_utc_datetime(start)
                        end_utc = _to_utc_datetime(end)
                        status = InviteStatus.PENDING.value
                        component_status = str(component.get("STATUS") or "").upper()
                        if method.upper() == "CANCEL" or component_status == "CANCELLED":
                            status = InviteStatus.CANCELED.value
                        flags, reasons = self._warning_flags(
                            message.subject,
                            message.from_address,
                            organizer,
                            message.text_body,
                        )
                        row = repo.upsert_record(
                            uid=uid,
                            organizer=organizer,
                            recurrence_id=recurrence_id,
                            sequence=sequence,
                            method=method,
                            status=status,
                            summary=summary,
                            start_utc=start_utc,
                            end_utc=end_utc,
                            timezone_name=(
                                str(component.get("DTSTART").params.get("TZID"))
                                if component.get("DTSTART") and component.get("DTSTART").params.get("TZID")
                                else None
                            ),
                            source_message_ref=message.id,
                            warning_flags=flags,
                            reason_codes=reasons,
                            raw_ics=payload,
                        )
                        created.append(row.id)
            session.commit()
        return {"scanned": len(created), "invite_refs": created}

    def _view(self, row: object) -> InviteRecordView:
        return InviteRecordView(
            ref=row.id,
            uid=row.uid,
            organizer=row.organizer,
            recurrence_id=row.recurrence_id,
            sequence=row.sequence,
            method=row.method,
            status=row.status,
            summary=row.summary,
            start_utc=row.start_utc,
            end_utc=row.end_utc,
            source_message_ref=row.source_message_ref,
            warning_flags=row.warning_flags,
            reason_codes=row.reason_codes,
            latest=row.latest,
        )

    def list_latest(self, status: str | None = None) -> list[InviteRecordView]:
        with self.session_factory() as session:
            rows = InvitesRepository(session).list_latest(status=status)
            return [self._view(row) for row in rows]

    def get(self, invite_ref: str) -> InviteRecordView:
        with self.session_factory() as session:
            row = InvitesRepository(session).get(invite_ref)
            return self._view(row)

    def latest(self) -> list[InviteRecordView]:
        with self.session_factory() as session:
            rows = InvitesRepository(session).latest()
            return [self._view(row) for row in rows]

    def source(self, invite_ref: str) -> MessageDetail:
        with self.session_factory() as session:
            invite = InvitesRepository(session).get(invite_ref)
            if invite.source_message_ref is None:
                raise make_error(
                    ErrorCode.MESSAGE_NOT_FOUND,
                    "Invite source message is unavailable",
                    {"invite_ref": invite_ref},
                )
            message = MessagesRepository(session).get(invite.source_message_ref)
            from proton_agent_suite.providers.bridge_mail.mapper import MailMapper

            return MailMapper.detail_from_row(message)

    def respond(self, invite_ref: str, action: InviteStatus, force: bool = False) -> dict[str, object]:
        with self.session_factory() as session:
            repo = InvitesRepository(session)
            row = repo.get(invite_ref)
            if row.warning_flags and not force:
                raise make_error(
                    ErrorCode.INVITE_UNSAFE_TO_RSVP,
                    "Invite is flagged as unsafe for automatic RSVP",
                    {
                        "invite_ref": invite_ref,
                        "warning_flags": row.warning_flags,
                        "reason_codes": row.reason_codes,
                    },
                )
            if not row.organizer or not row.raw_ics:
                raise make_error(
                    ErrorCode.NOT_IMPLEMENTED_SAFE_FALLBACK,
                    "Cannot safely generate RSVP without organizer and original ICS payload",
                    {"invite_ref": invite_ref},
                )
            message = MessagesRepository(session).get(row.source_message_ref) if row.source_message_ref else None
            attendee = message.to_addresses.split("\n")[0] if message and message.to_addresses else None
            if not attendee:
                raise make_error(
                    ErrorCode.NOT_IMPLEMENTED_SAFE_FALLBACK,
                    "Cannot determine attendee address for RSVP",
                    {"invite_ref": invite_ref},
                )
            ics_body = self._ics_codec.build_reply(
                uid=row.uid,
                organizer=row.organizer,
                attendee=attendee,
                partstat=action.value,
                summary=row.summary or "Meeting",
                sequence=row.sequence,
                start=row.start_utc or datetime.now(UTC),
            )
            request = MailSendRequest(
                to_addresses=[row.organizer],
                subject=f"RSVP: {row.summary or row.uid}",
                body_text=f"Automated RSVP: {action.value}\n\n{ics_body}",
            )
            self.mail_provider.send_message(request)
            row.status = action.value
            session.commit()
            return {"invite_ref": invite_ref, "status": action.value, "organizer": row.organizer}
