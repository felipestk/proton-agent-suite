from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session, sessionmaker

from proton_agent_suite.domain.models import CalendarInfo, ConnectorInfo, EventInfo, HealthCheckResult
from proton_agent_suite.domain.protocols import CalendarProvider
from proton_agent_suite.storage.repositories.calendars import CalendarsRepository
from proton_agent_suite.storage.repositories.events import EventsRepository


class CalendarService:
    def __init__(self, session_factory: sessionmaker[Session], provider: CalendarProvider) -> None:
        self.session_factory = session_factory
        self.provider = provider

    def health(self) -> HealthCheckResult:
        return self.provider.healthcheck()

    def discover(self) -> list[CalendarInfo]:
        calendars = self.provider.discover()
        with self.session_factory() as session:
            repo = CalendarsRepository(session)
            for calendar in calendars:
                repo.upsert(
                    provider="radicale",
                    name=calendar.name,
                    href=calendar.href,
                    url=calendar.href,
                    etag=calendar.etag,
                    color=calendar.color,
                    description=calendar.description,
                    is_default=calendar.is_default,
                )
            session.commit()
        return calendars

    def calendars(self) -> list[CalendarInfo]:
        return self.discover()

    def connector(self) -> ConnectorInfo:
        return self.provider.get_connector_info()

    def upcoming(self, days: int, calendar_ref: str | None = None) -> list[EventInfo]:
        events = self.provider.list_upcoming_events(days, calendar_ref=calendar_ref)
        self._persist_events(events)
        return events

    def changed_since(self, since: datetime, calendar_ref: str | None = None) -> list[EventInfo]:
        events = self.provider.changed_since(since, calendar_ref=calendar_ref)
        self._persist_events(events)
        return events

    def show(self, event_ref: str) -> EventInfo:
        with self.session_factory() as session:
            from proton_agent_suite.storage.schema import EventRow
            row = EventsRepository(session).get(event_ref)
            return self._event_from_row(row)

    def create(self, *, calendar_ref: str, title: str, start: datetime, end: datetime, timezone_name: str | None = None, description: str | None = None, location: str | None = None) -> EventInfo:
        event = self.provider.create_event(calendar_ref=calendar_ref, title=title, start=start, end=end, timezone_name=timezone_name, description=description, location=location)
        self._persist_events([event])
        return event

    def update(self, event_ref: str, *, title: str | None = None, start: datetime | None = None, end: datetime | None = None, description: str | None = None, location: str | None = None) -> EventInfo:
        event = self.provider.update_event(event_ref, title=title, start=start, end=end, description=description, location=location)
        self._persist_events([event])
        return event

    def cancel(self, event_ref: str) -> EventInfo:
        event = self.provider.cancel_event(event_ref)
        self._persist_events([event])
        return event

    def delete(self, event_ref: str) -> dict[str, str]:
        self.provider.delete_event(event_ref)
        with self.session_factory() as session:
            row = EventsRepository(session).get(event_ref)
            row.deleted = True
            session.commit()
        return {"event_ref": event_ref, "status": "deleted"}

    def create_calendar(self, name: str) -> CalendarInfo:
        calendar = self.provider.create_calendar(name)
        self.discover()
        return calendar

    def _persist_events(self, events: list[EventInfo]) -> None:
        with self.session_factory() as session:
            calendars_repo = CalendarsRepository(session)
            events_repo = EventsRepository(session)
            for event in events:
                calendar_id = None
                if event.calendar_ref:
                    try:
                        calendar_id = calendars_repo.get(event.calendar_ref).id
                    except Exception:
                        calendar_id = None
                events_repo.upsert_event(
                    calendar_id=calendar_id,
                    uid=event.uid,
                    href=event.href,
                    etag=event.etag,
                    title=event.title,
                    start_utc=event.start_utc,
                    end_utc=event.end_utc,
                    timezone_name=event.timezone_name,
                    status=event.status.value if hasattr(event.status, 'value') else str(event.status),
                    sequence=event.sequence,
                    organizer=event.organizer,
                    recurrence_id=event.recurrence_id,
                    raw_ics=None,
                    attendees=event.attendees,
                )
            session.commit()

    def _event_from_row(self, row) -> EventInfo:
        return EventInfo(
            ref=row.id,
            calendar_ref=row.calendar_id,
            uid=row.uid,
            href=row.href,
            etag=row.etag,
            title=row.title,
            start_utc=row.start_utc,
            end_utc=row.end_utc,
            timezone_name=row.timezone_name,
            status=row.status,
            sequence=row.sequence,
            organizer=row.organizer,
            recurrence_id=row.recurrence_id,
            attendees=[
                {
                    "email": attendee.email,
                    "common_name": attendee.common_name,
                    "partstat": attendee.partstat,
                    "role": attendee.role,
                    "rsvp": attendee.rsvp,
                }
                for attendee in row.attendees
            ],
            updated_at=row.updated_at,
        )
