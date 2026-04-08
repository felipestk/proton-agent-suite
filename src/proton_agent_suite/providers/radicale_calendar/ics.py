from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from zoneinfo import ZoneInfo

from icalendar import Calendar, Event, vCalAddress, vText

from proton_agent_suite.domain.enums import EventStatus
from proton_agent_suite.domain.models import EventAttendee, EventInfo
from proton_agent_suite.utils.ids import stable_ref
from proton_agent_suite.utils.time import ensure_utc


class CalendarIcsCodec:
    def parse_events(
        self,
        ics_text: str,
        calendar_ref: str | None = None,
        href: str | None = None,
        etag: str | None = None,
    ) -> list[EventInfo]:
        calendar = Calendar.from_ical(ics_text)
        events: list[EventInfo] = []
        for component in calendar.walk("VEVENT"):
            uid = str(component.get("UID"))
            title = str(component.get("SUMMARY") or "Untitled")
            description = str(component.get("DESCRIPTION") or "") or None
            location = str(component.get("LOCATION") or "") or None
            start = component.decoded("DTSTART")
            end = component.decoded("DTEND") if component.get("DTEND") else start
            start_dt = ensure_utc(
                start if isinstance(start, datetime) else datetime.combine(start, datetime.min.time(), tzinfo=UTC)
            )
            end_dt = ensure_utc(
                end if isinstance(end, datetime) else datetime.combine(end, datetime.min.time(), tzinfo=UTC)
            )
            attendees: list[EventAttendee] = []
            attendee_fields = component.get("ATTENDEE")
            if attendee_fields is None:
                attendee_list: list[Any] = []
            elif isinstance(attendee_fields, list):
                attendee_list = attendee_fields
            else:
                attendee_list = [attendee_fields]
            for attendee in attendee_list:
                params = dict(attendee.params)
                attendees.append(
                    EventAttendee(
                        email=str(attendee).removeprefix("mailto:").removeprefix("MAILTO:"),
                        common_name=str(params.get("CN")) if params.get("CN") else None,
                        partstat=str(params.get("PARTSTAT")) if params.get("PARTSTAT") else None,
                        role=str(params.get("ROLE")) if params.get("ROLE") else None,
                        rsvp=str(params.get("RSVP")).upper() == "TRUE" if params.get("RSVP") else None,
                    )
                )
            organizer = component.get("ORGANIZER")
            organizer_params = dict(organizer.params) if organizer else {}
            status = str(component.get("STATUS") or "CONFIRMED").lower()
            sequence = int(component.get("SEQUENCE") or 0)
            recurrence_id = component.get("RECURRENCE-ID")
            tzid = component.get("DTSTART").params.get("TZID") if component.get("DTSTART") else None
            events.append(
                EventInfo(
                    ref=stable_ref("evt", uid, str(recurrence_id or "")),
                    calendar_ref=calendar_ref,
                    uid=uid,
                    href=href,
                    etag=etag,
                    title=title,
                    description=description,
                    location=location,
                    start_utc=start_dt,
                    end_utc=end_dt,
                    timezone_name=str(tzid) if tzid else None,
                    status=EventStatus.CANCELED
                    if status == "cancelled"
                    else EventStatus(status if status in {"confirmed", "tentative", "canceled"} else "confirmed"),
                    sequence=sequence,
                    organizer=str(organizer).removeprefix("mailto:") if organizer else None,
                    organizer_common_name=str(organizer_params.get("CN")) if organizer_params.get("CN") else None,
                    recurrence_id=str(recurrence_id) if recurrence_id else None,
                    attendees=attendees,
                    updated_at=None,
                )
            )
        return events

    def _localized_datetime(self, value: datetime, timezone_name: str | None) -> datetime:
        if timezone_name:
            zone = ZoneInfo(timezone_name)
            if value.tzinfo is None:
                return value.replace(tzinfo=zone)
            return value.astimezone(zone)
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value

    def build_event(
        self,
        *,
        uid: str,
        title: str,
        start: datetime,
        end: datetime,
        timezone_name: str | None = None,
        organizer: str | None = None,
        organizer_common_name: str | None = None,
        attendees: list[EventAttendee] | None = None,
        description: str | None = None,
        location: str | None = None,
        status: str = "CONFIRMED",
        sequence: int = 0,
        method: str | None = None,
        recurrence_id: datetime | None = None,
    ) -> str:
        calendar = Calendar()
        calendar.add("prodid", "-//proton-agent-suite//EN")
        calendar.add("version", "2.0")
        if method:
            calendar.add("method", method)
        event = Event()
        localized_start = self._localized_datetime(start, timezone_name)
        localized_end = self._localized_datetime(end, timezone_name)
        event.add("uid", uid)
        event.add("summary", title)
        event.add("dtstart", localized_start)
        event.add("dtend", localized_end)
        event.add("dtstamp", datetime.now(UTC))
        event.add("status", status)
        event.add("sequence", sequence)
        event.add("created", datetime.now(UTC))
        event.add("last-modified", datetime.now(UTC))
        if description:
            event.add("description", description)
        if location:
            event.add("location", location)
        if recurrence_id is not None:
            event.add("recurrence-id", self._localized_datetime(recurrence_id, timezone_name))
        if organizer:
            organizer_addr = vCalAddress(f"MAILTO:{organizer}")
            organizer_addr.params["CN"] = vText(organizer_common_name or organizer)
            event["organizer"] = organizer_addr
        for attendee in attendees or []:
            attendee_addr = vCalAddress(f"MAILTO:{attendee.email}")
            if attendee.common_name:
                attendee_addr.params["CN"] = vText(attendee.common_name)
            if attendee.partstat:
                attendee_addr.params["PARTSTAT"] = vText(attendee.partstat.upper())
            if attendee.role:
                attendee_addr.params["ROLE"] = vText(attendee.role.upper())
            if attendee.rsvp is not None:
                attendee_addr.params["RSVP"] = vText("TRUE" if attendee.rsvp else "FALSE")
            event.add("attendee", attendee_addr, encode=0)
        calendar.add_component(event)
        return calendar.to_ical().decode("utf-8")

    def build_reply(
        self,
        *,
        uid: str,
        organizer: str,
        attendee: str,
        attendee_common_name: str | None,
        partstat: str,
        summary: str,
        sequence: int,
        start: datetime,
    ) -> str:
        calendar = Calendar()
        calendar.add("prodid", "-//proton-agent-suite//EN")
        calendar.add("version", "2.0")
        calendar.add("method", "REPLY")
        event = Event()
        event.add("uid", uid)
        event.add("summary", summary)
        event.add("dtstamp", datetime.now(UTC))
        event.add("dtstart", start)
        event.add("sequence", sequence)
        event.add("organizer", f"MAILTO:{organizer}")
        attendee_addr = vCalAddress(f"MAILTO:{attendee}")
        if attendee_common_name:
            attendee_addr.params["CN"] = vText(attendee_common_name)
        attendee_addr.params["PARTSTAT"] = vText(partstat.upper())
        attendee_addr.params["RSVP"] = vText("FALSE")
        event["attendee"] = attendee_addr
        calendar.add_component(event)
        return calendar.to_ical().decode("utf-8")
