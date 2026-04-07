from __future__ import annotations

from dataclasses import dataclass
import xml.etree.ElementTree as ET

NS = {
    "d": "DAV:",
    "cs": "http://calendarserver.org/ns/",
    "cal": "urn:ietf:params:xml:ns:caldav",
}


@dataclass(slots=True)
class DiscoveredCalendar:
    href: str
    display_name: str
    description: str | None
    color: str | None
    etag: str | None


@dataclass(slots=True)
class CalendarObject:
    href: str
    etag: str | None
    calendar_data: str


def parse_propfind_calendars(xml_text: str) -> list[DiscoveredCalendar]:
    root = ET.fromstring(xml_text)
    calendars: list[DiscoveredCalendar] = []
    for response in root.findall("d:response", NS):
        href = (response.findtext("d:href", default="", namespaces=NS) or "").strip()
        prop = response.find("d:propstat/d:prop", NS)
        if prop is None:
            continue
        resource_type = prop.find("d:resourcetype", NS)
        if resource_type is None or resource_type.find("cal:calendar", NS) is None:
            continue
        calendars.append(
            DiscoveredCalendar(
                href=href,
                display_name=(prop.findtext("d:displayname", default=href, namespaces=NS) or href).strip(),
                description=(prop.findtext("cs:getctag", default=None, namespaces=NS) or None),
                color=(prop.findtext("ical:calendar-color", default=None, namespaces={**NS, 'ical': 'http://apple.com/ns/ical/'}) or None),
                etag=(prop.findtext("d:getetag", default=None, namespaces=NS) or None),
            )
        )
    return calendars


def parse_calendar_query(xml_text: str) -> list[CalendarObject]:
    root = ET.fromstring(xml_text)
    objects: list[CalendarObject] = []
    for response in root.findall("d:response", NS):
        href = (response.findtext("d:href", default="", namespaces=NS) or "").strip()
        prop = response.find("d:propstat/d:prop", NS)
        if prop is None:
            continue
        calendar_data = prop.findtext("cal:calendar-data", default="", namespaces=NS)
        if not calendar_data:
            continue
        objects.append(
            CalendarObject(
                href=href,
                etag=prop.findtext("d:getetag", default=None, namespaces=NS),
                calendar_data=calendar_data,
            )
        )
    return objects
