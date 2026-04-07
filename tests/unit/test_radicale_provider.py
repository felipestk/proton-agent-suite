from __future__ import annotations

from datetime import UTC, datetime

from proton_agent_suite.domain.value_objects import RadicaleSettings
from proton_agent_suite.providers.radicale_calendar.provider import RadicaleCalendarProvider

DISCOVERY_XML = """<?xml version='1.0'?>
<d:multistatus xmlns:d='DAV:' xmlns:cal='urn:ietf:params:xml:ns:caldav'>
  <d:response>
    <d:href>/user/default/</d:href>
    <d:propstat><d:prop>
      <d:displayname>default</d:displayname>
      <d:resourcetype><d:collection /><cal:calendar /></d:resourcetype>
      <d:getetag>\"abc\"</d:getetag>
    </d:prop></d:propstat>
  </d:response>
</d:multistatus>
"""

REPORT_XML = """<?xml version='1.0'?>
<d:multistatus xmlns:d='DAV:' xmlns:cal='urn:ietf:params:xml:ns:caldav'>
  <d:response>
    <d:href>/user/default/event-1.ics</d:href>
    <d:propstat><d:prop>
      <d:getetag>\"etag1\"</d:getetag>
      <cal:calendar-data><![CDATA[BEGIN:VCALENDAR
VERSION:2.0
BEGIN:VEVENT
UID:event-1@example.com
DTSTAMP:20260401T080000Z
DTSTART:20260410T090000Z
DTEND:20260410T100000Z
SUMMARY:Calendar Event
SEQUENCE:1
STATUS:CONFIRMED
END:VEVENT
END:VCALENDAR]]></cal:calendar-data>
    </d:prop></d:propstat>
  </d:response>
</d:multistatus>
"""


class FakeResponse:
    def __init__(self, text: str, status_code: int = 207):
        self.text = text
        self.status_code = status_code


class FakeClient:
    def propfind(self, url, depth=1, body=None):
        return FakeResponse(DISCOVERY_XML)

    def report(self, url, body):
        return FakeResponse(REPORT_XML)

    def put(self, url, body, etag=None):
        return FakeResponse("", status_code=201)

    def delete(self, url, etag=None):
        return FakeResponse("", status_code=204)

    def mkcalendar(self, url, name):
        return FakeResponse("", status_code=201)


def test_discover_and_list_upcoming():
    provider = RadicaleCalendarProvider(
        RadicaleSettings(
            base_url="https://calendar.example.com/user/",
            username="user",
            password="pass",
            default_calendar="default",
        )
    )
    provider._client = FakeClient()
    calendars = provider.discover()
    assert calendars[0].name == "default"
    events = provider.list_upcoming_events(30)
    assert events[0].uid == "event-1@example.com"


def test_connector_info_uses_public_ics_url():
    provider = RadicaleCalendarProvider(
        RadicaleSettings(
            base_url="https://calendar.example.com/user/",
            username="user",
            password="pass",
            default_calendar="default",
        ),
        ics_public_base_url="https://calendar.example.com/public/",
    )
    provider._client = FakeClient()
    info = provider.get_connector_info()
    assert info.ics_url == "https://calendar.example.com/public/default.ics"
