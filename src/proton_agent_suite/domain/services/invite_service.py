from __future__ import annotations

from datetime import UTC, date, datetime, time
from email import policy
from email.parser import BytesParser

from icalendar import Calendar
from sqlalchemy.orm import Session, sessionmaker

from proton_agent_suite.domain.enums import ErrorCode, InviteStatus
from proton_agent_suite.domain.errors import ProtonAgentError, make_error
from proton_agent_suite.domain.models import EventAttendee, EventInfo, InviteRecordView, MessageDetail
from proton_agent_suite.domain.services.calendar_service import CalendarService
from proton_agent_suite.domain.services.mail_service import MailService
from proton_agent_suite.domain.value_objects import MailAttachment, MailSendRequest
from proton_agent_suite.providers.radicale_calendar.ics import CalendarIcsCodec
from proton_agent_suite.storage.repositories.invites import InvitesRepository
from proton_agent_suite.storage.repositories.messages import MessagesRepository
from proton_agent_suite.utils.ids import stable_ref
from proton_agent_suite.utils.time import ensure_utc


def _to_utc_datetime(value: date | datetime | None) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return ensure_utc(value)
    return ensure_utc(datetime.combine(value, time.min, tzinfo=UTC))


class InviteService:
    def __init__(
        self,
        session_factory: sessionmaker[Session],
        mail_service: MailService,
        calendar_service: CalendarService,
    ) -> None:
        self.session_factory = session_factory
        self.mail_service = mail_service
        self.calendar_service = calendar_service
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

    def _status_for_component(self, method: str, component_status: str) -> str:
        if method.upper() == "CANCEL" or component_status == "CANCELLED":
            return InviteStatus.CANCELED.value
        return InviteStatus.PENDING.value

    def _decode_attendees(self, attendees: list[dict[str, object]] | None) -> list[EventAttendee]:
        return [EventAttendee.model_validate(item) for item in attendees or []]

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
                        events = self._ics_codec.parse_events(payload)
                    except Exception as exc:
                        raise make_error(
                            ErrorCode.INVITE_PARSE_FAILED,
                            "Failed to parse invite ICS",
                            {"message_ref": message.id},
                        ) from exc
                    method = str(calendar.get("METHOD") or "REQUEST")
                    for event in events:
                        flags, reasons = self._warning_flags(
                            message.subject,
                            message.from_address,
                            event.organizer,
                            message.text_body,
                        )
                        row = repo.upsert_record(
                            uid=event.uid,
                            organizer=event.organizer,
                            organizer_common_name=event.organizer_common_name,
                            recurrence_id=event.recurrence_id,
                            sequence=event.sequence,
                            method=method,
                            status=self._status_for_component(method, event.status.value.upper()),
                            summary=event.title,
                            description=event.description,
                            location=event.location,
                            start_utc=event.start_utc,
                            end_utc=event.end_utc,
                            timezone_name=event.timezone_name,
                            attendees=[attendee.model_dump(mode="python") for attendee in event.attendees],
                            calendar_ref=event.calendar_ref,
                            calendar_href=event.href,
                            calendar_etag=event.etag,
                            source_message_ref=message.id,
                            outbound_mail_ref=None,
                            outbound_message_id=None,
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
            organizer_common_name=row.organizer_common_name,
            recurrence_id=row.recurrence_id,
            sequence=row.sequence,
            method=row.method,
            status=row.status,
            summary=row.summary,
            description=row.description,
            location=row.location,
            start_utc=row.start_utc,
            end_utc=row.end_utc,
            timezone_name=row.timezone_name,
            attendees=self._decode_attendees(row.attendees),
            calendar_ref=row.calendar_ref,
            calendar_href=row.calendar_href,
            calendar_etag=row.calendar_etag,
            source_message_ref=row.source_message_ref,
            outbound_mail_ref=row.outbound_mail_ref,
            outbound_message_id=row.outbound_message_id,
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
            row = self._get_row(session, invite_ref)
            return self._view(row)

    def latest(self) -> list[InviteRecordView]:
        with self.session_factory() as session:
            rows = InvitesRepository(session).latest()
            return [self._view(row) for row in rows]

    def _get_row(self, session: Session, invite_ref_or_uid: str):
        repo = InvitesRepository(session)
        try:
            return repo.get(invite_ref_or_uid)
        except ProtonAgentError as exc:
            if exc.code == ErrorCode.INVITE_NOT_FOUND:
                return repo.get_latest_for_uid(invite_ref_or_uid)
            raise

    def source(self, invite_ref: str) -> MessageDetail:
        with self.session_factory() as session:
            invite = self._get_row(session, invite_ref)
            if invite.source_message_ref is None:
                raise make_error(
                    ErrorCode.MESSAGE_NOT_FOUND,
                    "Invite source message is unavailable",
                    {"invite_ref": invite_ref},
                )
            message = MessagesRepository(session).get(invite.source_message_ref)
            from proton_agent_suite.providers.bridge_mail.mapper import MailMapper

            return MailMapper.detail_from_row(message)

    def _rsvp_attendee(self, row: object, message: object | None) -> EventAttendee:
        candidates = [value for value in (message.to_addresses.split("\n") if message and message.to_addresses else []) if value]
        for candidate in candidates:
            for attendee in self._decode_attendees(row.attendees):
                if attendee.email.lower() == candidate.lower():
                    return attendee
        if candidates:
            return EventAttendee(email=candidates[0])
        raise make_error(
            ErrorCode.NOT_IMPLEMENTED_SAFE_FALLBACK,
            "Cannot determine attendee address for RSVP",
            {"invite_ref": row.id},
        )

    def respond(self, invite_ref: str, action: InviteStatus, force: bool = False) -> dict[str, object]:
        with self.session_factory() as session:
            repo = InvitesRepository(session)
            row = self._get_row(session, invite_ref)
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
            attendee = self._rsvp_attendee(row, message)
            ics_body = self._ics_codec.build_reply(
                uid=row.uid,
                organizer=row.organizer,
                attendee=attendee.email,
                attendee_common_name=attendee.common_name,
                partstat=action.value,
                summary=row.summary or "Meeting",
                sequence=row.sequence,
                start=row.start_utc or datetime.now(UTC),
            )
            request = MailSendRequest(
                to_addresses=[row.organizer],
                subject=f"RSVP: {row.summary or row.uid}",
                body_text=f"RSVP status: {action.value}",
                attachments=[
                    MailAttachment(
                        filename="reply.ics",
                        content_type="text/calendar",
                        content=ics_body.encode("utf-8"),
                        params={"method": "REPLY", "charset": "utf-8"},
                    )
                ],
            )
            result = self.mail_service.send(
                request,
                source_message_ref=row.source_message_ref,
                related_invite_uid=row.uid,
                invite_sequence=row.sequence,
                method="REPLY",
            )
            row.status = action.value
            row.outbound_mail_ref = str(result.get("sent_ref"))
            row.outbound_message_id = str(result.get("message_id")) if result.get("message_id") else None
            session.commit()
            return {"invite_ref": row.id, "status": action.value, "organizer": row.organizer, **result}

    def _persist_invite_record(
        self,
        *,
        event: EventInfo,
        method: str,
        source_message_ref: str | None = None,
        outbound_mail_ref: str | None = None,
        outbound_message_id: str | None = None,
        raw_ics: str | None = None,
    ) -> InviteRecordView:
        with self.session_factory() as session:
            row = InvitesRepository(session).upsert_record(
                uid=event.uid,
                organizer=event.organizer,
                organizer_common_name=event.organizer_common_name,
                recurrence_id=event.recurrence_id,
                sequence=event.sequence,
                method=method,
                status=InviteStatus.CANCELED.value
                if method.upper() == "CANCEL" or str(event.status).lower() == "canceled"
                else InviteStatus.PENDING.value,
                summary=event.title,
                description=event.description,
                location=event.location,
                start_utc=event.start_utc,
                end_utc=event.end_utc,
                timezone_name=event.timezone_name,
                attendees=[attendee.model_dump(mode="python") for attendee in event.attendees],
                calendar_ref=event.calendar_ref,
                calendar_href=event.href,
                calendar_etag=event.etag,
                source_message_ref=source_message_ref,
                outbound_mail_ref=outbound_mail_ref,
                outbound_message_id=outbound_message_id,
                warning_flags=[],
                reason_codes=[],
                raw_ics=raw_ics,
            )
            session.commit()
            return self._view(row)

    def _send_invite_mail(self, *, event: EventInfo, method: str, subject_prefix: str | None = None) -> dict[str, object]:
        if not event.organizer:
            raise make_error(ErrorCode.VALIDATION_ERROR, "Organizer email is required for invite workflows")
        if not event.attendees:
            raise make_error(ErrorCode.VALIDATION_ERROR, "At least one attendee is required for invite workflows")
        ics_body = self._ics_codec.build_event(
            uid=event.uid,
            title=event.title,
            start=event.start_utc,
            end=event.end_utc,
            timezone_name=event.timezone_name,
            organizer=event.organizer,
            organizer_common_name=event.organizer_common_name,
            attendees=event.attendees,
            description=event.description,
            location=event.location,
            status="CANCELLED" if method.upper() == "CANCEL" else "CONFIRMED",
            sequence=event.sequence,
            method=method,
        )
        subject = f"{subject_prefix} {event.title}" if subject_prefix else event.title
        return {
            "request": MailSendRequest(
                to_addresses=[attendee.email for attendee in event.attendees],
                subject=subject,
                body_text=event.description or f"Calendar update: {event.title}",
                attachments=[
                    MailAttachment(
                        filename="invite.ics",
                        content_type="text/calendar",
                        content=ics_body.encode("utf-8"),
                        params={"method": method.upper(), "charset": "utf-8"},
                    )
                ],
            ),
            "ics": ics_body,
        }

    def create(
        self,
        *,
        calendar_ref: str,
        title: str,
        start: datetime,
        end: datetime,
        organizer: str,
        organizer_common_name: str | None = None,
        attendees: list[EventAttendee],
        description: str | None = None,
        location: str | None = None,
        timezone_name: str | None = None,
    ) -> dict[str, object]:
        uid = stable_ref("uid", organizer, title, start.isoformat(), end.isoformat())
        event = self.calendar_service.create(
            calendar_ref=calendar_ref,
            title=title,
            start=start,
            end=end,
            timezone_name=timezone_name,
            description=description,
            location=location,
            organizer=organizer,
            organizer_common_name=organizer_common_name,
            attendees=attendees,
            uid=uid,
        )
        mail = self._send_invite_mail(event=event, method="REQUEST", subject_prefix="Invitation:")
        sent = self.mail_service.send(
            mail["request"],
            related_invite_uid=event.uid,
            invite_sequence=event.sequence,
            method="REQUEST",
        )
        invite = self._persist_invite_record(
            event=event,
            method="REQUEST",
            outbound_mail_ref=str(sent.get("sent_ref")),
            outbound_message_id=str(sent.get("message_id")) if sent.get("message_id") else None,
            raw_ics=str(mail["ics"]),
        )
        return {"invite": invite.model_dump(mode="json"), "mail": sent}

    def update(
        self,
        invite_ref_or_uid: str,
        *,
        title: str | None = None,
        start: datetime | None = None,
        end: datetime | None = None,
        description: str | None = None,
        location: str | None = None,
        timezone_name: str | None = None,
        organizer: str | None = None,
        organizer_common_name: str | None = None,
        attendees: list[EventAttendee] | None = None,
    ) -> dict[str, object]:
        with self.session_factory() as session:
            current = self._view(self._get_row(session, invite_ref_or_uid))
        event_ref = stable_ref("evt", current.uid, current.recurrence_id or "")
        event = self.calendar_service.update(
            event_ref,
            title=title,
            start=start,
            end=end,
            timezone_name=timezone_name,
            description=description,
            location=location,
            organizer=organizer or current.organizer,
            organizer_common_name=organizer_common_name or current.organizer_common_name,
            attendees=attendees if attendees is not None else current.attendees,
            sequence=current.sequence + 1,
            status="CONFIRMED",
        )
        mail = self._send_invite_mail(event=event, method="REQUEST", subject_prefix="Updated invitation:")
        sent = self.mail_service.send(
            mail["request"],
            related_invite_uid=event.uid,
            invite_sequence=event.sequence,
            method="REQUEST",
        )
        invite = self._persist_invite_record(
            event=event,
            method="REQUEST",
            outbound_mail_ref=str(sent.get("sent_ref")),
            outbound_message_id=str(sent.get("message_id")) if sent.get("message_id") else None,
            raw_ics=str(mail["ics"]),
        )
        return {"invite": invite.model_dump(mode="json"), "mail": sent}

    def cancel(
        self,
        invite_ref_or_uid: str,
        *,
        delete_local_event: bool = True,
    ) -> dict[str, object]:
        with self.session_factory() as session:
            current = self._view(self._get_row(session, invite_ref_or_uid))
        cancel_event = EventInfo(
            ref=stable_ref("evt", current.uid, current.recurrence_id or ""),
            calendar_ref=current.calendar_ref,
            uid=current.uid,
            href=current.calendar_href,
            etag=current.calendar_etag,
            title=current.summary or "Meeting",
            description=current.description,
            location=current.location,
            start_utc=current.start_utc or datetime.now(UTC),
            end_utc=current.end_utc or current.start_utc or datetime.now(UTC),
            timezone_name=current.timezone_name,
            status="canceled",
            sequence=current.sequence + 1,
            organizer=current.organizer,
            organizer_common_name=current.organizer_common_name,
            recurrence_id=current.recurrence_id,
            attendees=current.attendees,
        )
        mail = self._send_invite_mail(event=cancel_event, method="CANCEL", subject_prefix="Canceled:")
        sent = self.mail_service.send(
            mail["request"],
            related_invite_uid=cancel_event.uid,
            invite_sequence=cancel_event.sequence,
            method="CANCEL",
        )
        if delete_local_event:
            self.calendar_service.delete(cancel_event.ref)
        else:
            self.calendar_service.update(cancel_event.ref, status="CANCELLED", sequence=cancel_event.sequence)
        invite = self._persist_invite_record(
            event=cancel_event,
            method="CANCEL",
            outbound_mail_ref=str(sent.get("sent_ref")),
            outbound_message_id=str(sent.get("message_id")) if sent.get("message_id") else None,
            raw_ics=str(mail["ics"]),
        )
        return {
            "invite": invite.model_dump(mode="json"),
            "mail": sent,
            "local_calendar_action": "deleted" if delete_local_event else "canceled",
        }
