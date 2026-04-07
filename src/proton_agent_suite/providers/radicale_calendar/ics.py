from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from icalendar import Calendar, Event, vCalAddress, vText

from proton_agent_suite.domain.enums import EventStatus
from proton_agent_suite.domain.models import EventInfo
from proton_agent_suite.utils.ids import stable_ref
from proton_agent_suite.utils.time import ensure_utc


class CalendarIcsCodec:
    def parse_events(self, ics_text: str, calendar_ref: str | None = None, href: str | None = None, etag: str | None = None) -> list[EventInfo]:
        calendar = Calendar.from_ical(ics_text)
        events: list[EventInfo] = []
        for component in calendar.walk("VEVENT"):
            uid = str(component.get("UID"))
            title = str(component.get("SUMMARY") or "Untitled")
            start = component.decoded("DTSTART")
            end = component.decoded("DTEND") if component.get("DTEND") else start
            start_dt = ensure_utc(start if isinstance(start, datetime) else datetime.combine(start, datetime.min.time(), tzinfo=UTC))
            end_dt = ensure_utc(end if isinstance(end, datetime) else datetime.combine(end, datetime.min.time(), tzinfo=UTC))
            attendees: list[dict[str, Any]] = []
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
                    {
                        "email": str(attendee).removeprefix("mailto:").removeprefix("MAILTO:"),
                        "common_name": params.get("CN"),
                        "partstat": str(params.get("PARTSTAT")) if params.get("PARTSTAT") else None,
                        "role": str(params.get("ROLE")) if params.get("ROLE") else None,
                        "rsvp": str(params.get("RSVP")).upper() == "TRUE" if params.get("RSVP") else None,
                    }
                )
            organizer = component.get("ORGANIZER")
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
                    start_utc=start_dt,
                    end_utc=end_dt,
                    timezone_name=str(tzid) if tzid else None,
                    status=EventStatus.CANCELED if status == "cancelled" else EventStatus(status if status in {"confirmed", "tentative", "canceled"} else "confirmed"),
                    sequence=sequence,
                    organizer=str(organizer).removeprefix("mailto:") if organizer else None,
                    recurrence_id=str(recurrence_id) if recurrence_id else None,
                    attendees=attendees,
                    updated_at=None,
                )
            )
        return events

    def build_event(
        self,
        *,
        uid: str,
        title: str,
        start: datetime,
        end: datetime,
        organizer: str | None = None,
        description: str | None = None,
        location: str | None = None,
        status: str = "CONFIRMED",
        sequence: int = 0,
    ) -> str:
        calendar = Calendar()
        calendar.add("prodid", "-//proton-agent-suite//EN")
        calendar.add("version", "2.0")
        event = Event()
        event.add("uid", uid)
        event.add("summary", title)
        event.add("dtstart", start)
        event.add("dtend", end)
        event.add("dtstamp", datetime.now(UTC))
        event.add("status", status)
        event.add("sequence", sequence)
        if description:
            event.add("description", description)
        if location:
            event.add("location", location)
        if organizer:
            organizer_addr = vCalAddress(f"MAILTO:{organizer}")
            organizer_addr.params["CN"] = vText(organizer)
            event["organizer"] = organizer_addr
        calendar.add_component(event)
        return calendar.to_ical().decode("utf-8")

    def build_reply(
        self,
        *,
        uid: str,
        organizer: str,
        attendee: str,
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
        attendee_addr.params["PARTSTAT"] = vText(partstat.upper())
        attendee_addr.params["RSVP"] = vText("FALSE")
        event["attendee"] = attendee_addr
        calendar.add_component(event)
        return calendar.to_ical().decode("utf-8")
