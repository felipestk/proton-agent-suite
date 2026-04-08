from __future__ import annotations

from datetime import UTC, datetime, timedelta
from urllib.parse import urljoin

from proton_agent_suite.domain.enums import ErrorCode
from proton_agent_suite.domain.errors import make_error
from proton_agent_suite.domain.models import CalendarInfo, ConnectorInfo, EventAttendee, EventInfo, HealthCheckResult
from proton_agent_suite.domain.value_objects import RadicaleSettings
from proton_agent_suite.providers.radicale_calendar.client import RadicaleHttpClient
from proton_agent_suite.providers.radicale_calendar.discovery import parse_calendar_query, parse_propfind_calendars
from proton_agent_suite.providers.radicale_calendar.ics import CalendarIcsCodec
from proton_agent_suite.providers.radicale_calendar.mapper import RadicaleMapper
from proton_agent_suite.utils.ids import stable_ref
from proton_agent_suite.utils.time import ensure_utc


_DISCOVERY_BODY = """<?xml version="1.0" encoding="utf-8" ?>
<d:propfind xmlns:d="DAV:" xmlns:cal="urn:ietf:params:xml:ns:caldav">
  <d:prop>
    <d:displayname />
    <d:resourcetype />
    <d:getetag />
  </d:prop>
</d:propfind>
"""


def _calendar_query_body(start: datetime, end: datetime) -> str:
    start_value = ensure_utc(start).strftime("%Y%m%dT%H%M%SZ")
    end_value = ensure_utc(end).strftime("%Y%m%dT%H%M%SZ")
    return f"""<?xml version="1.0" encoding="utf-8" ?>
<c:calendar-query xmlns:d="DAV:" xmlns:c="urn:ietf:params:xml:ns:caldav">
  <d:prop>
    <d:getetag />
    <c:calendar-data />
  </d:prop>
  <c:filter>
    <c:comp-filter name="VCALENDAR">
      <c:comp-filter name="VEVENT">
        <c:time-range start="{start_value}" end="{end_value}" />
      </c:comp-filter>
    </c:comp-filter>
  </c:filter>
</c:calendar-query>
"""


class RadicaleCalendarProvider:
    def __init__(self, settings: RadicaleSettings, ics_public_base_url: str | None = None) -> None:
        self.settings = settings
        self._client = RadicaleHttpClient(settings)
        self._codec = CalendarIcsCodec()
        self._ics_public_base_url = ics_public_base_url

    def _base_url(self) -> str:
        if not self.settings.base_url:
            raise make_error(ErrorCode.CONFIG_INVALID, "Radicale base URL is not configured")
        return self.settings.base_url

    def healthcheck(self) -> HealthCheckResult:
        response = self._client.propfind(self._base_url(), depth=0, body=_DISCOVERY_BODY)
        return HealthCheckResult(status="ok", checks={"http_status": response.status_code, "url": self._base_url()})

    def discover(self) -> list[CalendarInfo]:
        response = self._client.propfind(self._base_url(), depth=1, body=_DISCOVERY_BODY)
        calendars = parse_propfind_calendars(response.text)
        return [RadicaleMapper.calendar_info(item, self.settings.default_calendar) for item in calendars]

    def list_calendars(self) -> list[CalendarInfo]:
        return self.discover()

    def get_calendar(self, calendar_ref: str) -> CalendarInfo:
        for calendar in self.discover():
            if calendar.ref == calendar_ref or calendar.name == calendar_ref:
                return calendar
        raise make_error(ErrorCode.CALENDAR_NOT_FOUND, "Calendar not found", {"calendar_ref": calendar_ref})

    def _events_for_calendar(self, calendar: CalendarInfo, start: datetime, end: datetime) -> list[EventInfo]:
        response = self._client.report(urljoin(self._base_url(), calendar.href), _calendar_query_body(start, end))
        objects = parse_calendar_query(response.text)
        events: list[EventInfo] = []
        for obj in objects:
            events.extend(self._codec.parse_events(obj.calendar_data, calendar_ref=calendar.ref, href=obj.href, etag=obj.etag))
        return sorted(events, key=lambda item: (item.start_utc, item.uid, item.recurrence_id or ""))

    def list_upcoming_events(self, days: int, calendar_ref: str | None = None) -> list[EventInfo]:
        calendars = [self.get_calendar(calendar_ref)] if calendar_ref else self.discover()
        start = datetime.now(UTC) - timedelta(days=1)
        end = datetime.now(UTC) + timedelta(days=days)
        results: list[EventInfo] = []
        for calendar in calendars:
            results.extend(self._events_for_calendar(calendar, start, end))
        return sorted(results, key=lambda item: (item.start_utc, item.uid))

    def changed_since(self, since: datetime, calendar_ref: str | None = None) -> list[EventInfo]:
        upcoming = self.list_upcoming_events(days=365, calendar_ref=calendar_ref)
        return [event for event in upcoming if (event.updated_at or event.start_utc) >= since]

    def get_event(self, event_ref: str) -> EventInfo:
        for event in self.list_upcoming_events(days=365):
            if event.ref == event_ref or event.uid == event_ref:
                return event
        raise make_error(ErrorCode.EVENT_NOT_FOUND, "Event not found", {"event_ref": event_ref})

    def create_event(
        self,
        *,
        calendar_ref: str,
        title: str,
        start: datetime,
        end: datetime,
        timezone_name: str | None = None,
        description: str | None = None,
        location: str | None = None,
        organizer: str | None = None,
        organizer_common_name: str | None = None,
        attendees: list[EventAttendee] | None = None,
        status: str = "CONFIRMED",
        sequence: int = 0,
        uid: str | None = None,
    ) -> EventInfo:
        calendar = self.get_calendar(calendar_ref)
        uid = uid or stable_ref("uid", title, start.isoformat(), end.isoformat(), organizer or "")
        href = f"{calendar.href.rstrip('/')}/{uid}.ics"
        body = self._codec.build_event(
            uid=uid,
            title=title,
            start=start,
            end=end,
            timezone_name=timezone_name,
            organizer=organizer,
            organizer_common_name=organizer_common_name,
            attendees=attendees,
            description=description,
            location=location,
            status=status,
            sequence=sequence,
        )
        self._client.put(urljoin(self._base_url(), href), body)
        return EventInfo(
            ref=stable_ref("evt", uid, ""),
            calendar_ref=calendar.ref,
            uid=uid,
            href=href,
            etag=None,
            title=title,
            description=description,
            location=location,
            start_utc=ensure_utc(start),
            end_utc=ensure_utc(end),
            timezone_name=timezone_name,
            status=status.lower(),
            sequence=sequence,
            organizer=organizer,
            organizer_common_name=organizer_common_name,
            updated_at=datetime.now(UTC),
            attendees=attendees or [],
        )

    def update_event(
        self,
        event_ref: str,
        *,
        title: str | None = None,
        start: datetime | None = None,
        end: datetime | None = None,
        timezone_name: str | None = None,
        description: str | None = None,
        location: str | None = None,
        organizer: str | None = None,
        organizer_common_name: str | None = None,
        attendees: list[EventAttendee] | None = None,
        status: str | None = None,
        sequence: int | None = None,
    ) -> EventInfo:
        current = self.get_event(event_ref)
        href = current.href
        if href is None:
            raise make_error(ErrorCode.EVENT_NOT_FOUND, "Event href is missing", {"event_ref": event_ref})
        next_sequence = sequence if sequence is not None else current.sequence + 1
        body = self._codec.build_event(
            uid=current.uid,
            title=title or current.title,
            start=start or current.start_utc,
            end=end or current.end_utc,
            timezone_name=timezone_name or current.timezone_name,
            organizer=organizer or current.organizer,
            organizer_common_name=organizer_common_name or current.organizer_common_name,
            attendees=attendees if attendees is not None else current.attendees,
            description=description if description is not None else current.description,
            location=location if location is not None else current.location,
            status=(status or current.status.value).upper(),
            sequence=next_sequence,
        )
        self._client.put(urljoin(self._base_url(), href), body, etag=current.etag)
        return current.model_copy(
            update={
                "title": title or current.title,
                "description": description if description is not None else current.description,
                "location": location if location is not None else current.location,
                "start_utc": ensure_utc(start or current.start_utc),
                "end_utc": ensure_utc(end or current.end_utc),
                "timezone_name": timezone_name or current.timezone_name,
                "organizer": organizer or current.organizer,
                "organizer_common_name": organizer_common_name or current.organizer_common_name,
                "attendees": attendees if attendees is not None else current.attendees,
                "status": (status.lower() if status else current.status),
                "sequence": next_sequence,
                "updated_at": datetime.now(UTC),
            }
        )

    def cancel_event(self, event_ref: str) -> EventInfo:
        current = self.get_event(event_ref)
        href = current.href
        if href is None:
            raise make_error(ErrorCode.EVENT_NOT_FOUND, "Event href is missing", {"event_ref": event_ref})
        body = self._codec.build_event(
            uid=current.uid,
            title=current.title,
            start=current.start_utc,
            end=current.end_utc,
            timezone_name=current.timezone_name,
            organizer=current.organizer,
            organizer_common_name=current.organizer_common_name,
            attendees=current.attendees,
            description=current.description,
            location=current.location,
            status="CANCELLED",
            sequence=current.sequence + 1,
        )
        self._client.put(urljoin(self._base_url(), href), body, etag=current.etag)
        from proton_agent_suite.domain.enums import EventStatus
        return current.model_copy(update={"status": EventStatus.CANCELED, "sequence": current.sequence + 1, "updated_at": datetime.now(UTC)})

    def delete_event(self, event_ref: str) -> None:
        current = self.get_event(event_ref)
        if current.href is None:
            raise make_error(ErrorCode.EVENT_NOT_FOUND, "Event href is missing", {"event_ref": event_ref})
        self._client.delete(urljoin(self._base_url(), current.href), etag=current.etag)

    def create_calendar(self, name: str) -> CalendarInfo:
        href = f"{name.strip().replace(' ', '-').lower()}/"
        self._client.mkcalendar(urljoin(self._base_url(), href), name)
        return CalendarInfo(ref=stable_ref("cal", href), name=name, href=href, is_default=False)

    def update_calendar(self, calendar_ref: str, name: str | None = None) -> CalendarInfo:
        calendar = self.get_calendar(calendar_ref)
        if name:
            return calendar.model_copy(update={"name": name})
        return calendar

    def get_connector_info(self) -> ConnectorInfo:
        default = self.settings.default_calendar
        calendar_path = None
        if default:
            for calendar in self.discover():
                if calendar.name == default:
                    calendar_path = calendar.href
                    break
        return ConnectorInfo(
            provider="radicale",
            caldav_base_url=self._base_url(),
            username=self.settings.username or "",
            default_calendar=default,
            calendar_path=calendar_path,
            ics_url=self.export_ics_url(calendar_path),
            notes=[
                "CalDAV is the primary two-way sync path.",
                "ICS subscriptions are read-only when exposed by deployment.",
            ],
        )

    def export_ics_url(self, calendar_ref: str | None = None) -> str | None:
        if not self._ics_public_base_url:
            return None
        if calendar_ref is None:
            default = self.settings.default_calendar or "default"
            return f"{self._ics_public_base_url.rstrip('/')}/{default}.ics"
        cleaned = calendar_ref.strip("/").split("/")[-1]
        return f"{self._ics_public_base_url.rstrip('/')}/{cleaned}.ics"
