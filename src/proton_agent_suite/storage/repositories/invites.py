from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from proton_agent_suite.domain.enums import ErrorCode
from proton_agent_suite.domain.errors import make_error
from proton_agent_suite.storage.schema import InviteInstanceRow, InviteRecordRow
from proton_agent_suite.utils.ids import stable_ref


class InvitesRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def upsert_record(
        self,
        *,
        uid: str,
        organizer: str | None,
        organizer_common_name: str | None,
        recurrence_id: str | None,
        sequence: int,
        method: str | None,
        status: str,
        summary: str | None,
        description: str | None,
        location: str | None,
        start_utc: datetime | None,
        end_utc: datetime | None,
        timezone_name: str | None,
        attendees: list[dict[str, object]],
        calendar_ref: str | None,
        calendar_href: str | None,
        calendar_etag: str | None,
        source_message_ref: str | None,
        outbound_mail_ref: str | None,
        outbound_message_id: str | None,
        warning_flags: list[str],
        reason_codes: list[str],
        raw_ics: str | None,
    ) -> InviteRecordRow:
        row = self.session.scalar(
            select(InviteRecordRow).where(
                InviteRecordRow.uid == uid,
                InviteRecordRow.organizer == organizer,
                InviteRecordRow.recurrence_id == recurrence_id,
                InviteRecordRow.sequence == sequence,
            )
        )
        if row is None:
            row = InviteRecordRow(
                id=stable_ref("inv", uid, organizer or "", recurrence_id or "", sequence),
                uid=uid,
                organizer=organizer,
                organizer_common_name=organizer_common_name,
                recurrence_id=recurrence_id,
                sequence=sequence,
            )
            self.session.add(row)
        row.method = method
        row.status = status
        row.summary = summary
        row.description = description
        row.location = location
        row.start_utc = start_utc
        row.end_utc = end_utc
        row.timezone_name = timezone_name
        row.attendees = attendees
        row.calendar_ref = calendar_ref
        row.calendar_href = calendar_href
        row.calendar_etag = calendar_etag
        row.source_message_ref = source_message_ref
        row.outbound_mail_ref = outbound_mail_ref
        row.outbound_message_id = outbound_message_id
        row.warning_flags = warning_flags
        row.reason_codes = reason_codes
        row.raw_ics = raw_ics
        self.session.flush()

        siblings = list(
            self.session.scalars(
                select(InviteRecordRow).where(
                    InviteRecordRow.uid == uid,
                    InviteRecordRow.organizer == organizer,
                    InviteRecordRow.recurrence_id == recurrence_id,
                )
            )
        )
        latest = max(siblings, key=lambda item: item.sequence)
        for sibling in siblings:
            sibling.latest = sibling.id == latest.id

        instance = self.session.scalar(
            select(InviteInstanceRow).where(
                InviteInstanceRow.uid == uid,
                InviteInstanceRow.organizer == organizer,
                InviteInstanceRow.recurrence_id == recurrence_id,
            )
        )
        if instance is None:
            instance = InviteInstanceRow(
                id=stable_ref("ivi", uid, organizer or "", recurrence_id or ""),
                uid=uid,
                organizer=organizer,
                recurrence_id=recurrence_id,
                latest_record_id=latest.id,
                current_status=latest.status,
                start_utc=latest.start_utc,
                end_utc=latest.end_utc,
                calendar_ref=latest.calendar_ref,
                calendar_href=latest.calendar_href,
                calendar_etag=latest.calendar_etag,
            )
            self.session.add(instance)
        else:
            instance.latest_record_id = latest.id
            instance.current_status = latest.status
            instance.start_utc = latest.start_utc
            instance.end_utc = latest.end_utc
            instance.calendar_ref = latest.calendar_ref
            instance.calendar_href = latest.calendar_href
            instance.calendar_etag = latest.calendar_etag
        self.session.flush()
        return row

    def list_latest(self, status: str | None = None, limit: int = 100) -> list[InviteRecordRow]:
        stmt = select(InviteRecordRow).where(InviteRecordRow.latest.is_(True)).order_by(InviteRecordRow.start_utc.asc().nulls_last())
        if status:
            stmt = stmt.where(InviteRecordRow.status == status)
        return list(self.session.scalars(stmt.limit(limit)))

    def get(self, invite_ref: str) -> InviteRecordRow:
        row = self.session.scalar(select(InviteRecordRow).where(InviteRecordRow.id == invite_ref))
        if row is None:
            raise make_error(ErrorCode.INVITE_NOT_FOUND, "Invite not found", {"invite_ref": invite_ref})
        return row

    def latest(self, limit: int = 20) -> list[InviteRecordRow]:
        stmt = select(InviteRecordRow).where(InviteRecordRow.latest.is_(True)).order_by(InviteRecordRow.updated_at.desc()).limit(limit)
        return list(self.session.scalars(stmt))

    def changed_since(self, since: datetime) -> list[InviteRecordRow]:
        stmt = select(InviteRecordRow).where(InviteRecordRow.updated_at >= since).order_by(InviteRecordRow.updated_at.asc())
        return list(self.session.scalars(stmt))

    def get_latest_for_uid(self, uid: str) -> InviteRecordRow:
        row = self.session.scalar(
            select(InviteRecordRow).where(InviteRecordRow.uid == uid, InviteRecordRow.latest.is_(True))
        )
        if row is None:
            raise make_error(ErrorCode.INVITE_NOT_FOUND, "Invite not found", {"uid": uid})
        return row
