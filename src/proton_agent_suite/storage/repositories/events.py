from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from proton_agent_suite.domain.enums import ErrorCode
from proton_agent_suite.domain.errors import make_error
from proton_agent_suite.storage.schema import EventAttendeeRow, EventRow
from proton_agent_suite.utils.ids import stable_ref


class EventsRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def upsert_event(
        self,
        *,
        calendar_id: str | None,
        uid: str,
        href: str | None,
        etag: str | None,
        title: str,
        start_utc: datetime,
        end_utc: datetime,
        timezone_name: str | None,
        status: str,
        sequence: int,
        organizer: str | None,
        recurrence_id: str | None,
        raw_ics: str | None,
        attendees: list[dict[str, object]],
    ) -> EventRow:
        stmt = select(EventRow).where(EventRow.uid == uid, EventRow.recurrence_id == recurrence_id)
        row = self.session.scalar(stmt)
        if row is None:
            row = EventRow(id=stable_ref("evt", uid, recurrence_id or ""), uid=uid, recurrence_id=recurrence_id)
            self.session.add(row)
        row.calendar_id = calendar_id
        row.href = href
        row.etag = etag
        row.title = title
        row.start_utc = start_utc
        row.end_utc = end_utc
        row.timezone_name = timezone_name
        row.status = status
        row.sequence = sequence
        row.organizer = organizer
        row.raw_ics = raw_ics
        row.deleted = status == "canceled"
        self.session.flush()
        for attendee in list(row.attendees):
            self.session.delete(attendee)
        for idx, attendee in enumerate(attendees):
            self.session.add(
                EventAttendeeRow(
                    id=stable_ref("atn", row.id, idx, attendee.get("email") or ""),
                    event_id=row.id,
                    email=str(attendee.get("email") or ""),
                    common_name=str(attendee.get("common_name") or "") or None,
                    partstat=str(attendee.get("partstat") or "") or None,
                    role=str(attendee.get("role") or "") or None,
                    rsvp=bool(attendee.get("rsvp")) if attendee.get("rsvp") is not None else None,
                )
            )
        self.session.flush()
        return row

    def get(self, event_ref: str) -> EventRow:
        row = self.session.scalar(select(EventRow).options(selectinload(EventRow.attendees)).where(EventRow.id == event_ref))
        if row is None:
            raise make_error(ErrorCode.EVENT_NOT_FOUND, "Event not found", {"event_ref": event_ref})
        return row

    def list_upcoming(self, days_from_now: datetime, limit: int = 200) -> list[EventRow]:
        stmt = (
            select(EventRow)
            .options(selectinload(EventRow.attendees))
            .where(EventRow.deleted.is_(False), EventRow.start_utc >= days_from_now)
            .order_by(EventRow.start_utc.asc())
            .limit(limit)
        )
        return list(self.session.scalars(stmt))

    def list_before(self, until: datetime, limit: int = 200) -> list[EventRow]:
        stmt = (
            select(EventRow)
            .options(selectinload(EventRow.attendees))
            .where(EventRow.deleted.is_(False), EventRow.start_utc <= until)
            .order_by(EventRow.start_utc.asc())
            .limit(limit)
        )
        return list(self.session.scalars(stmt))

    def changed_since(self, since: datetime) -> list[EventRow]:
        stmt = select(EventRow).options(selectinload(EventRow.attendees)).where(EventRow.updated_at >= since)
        return list(self.session.scalars(stmt))
