from __future__ import annotations

from proton_agent_suite.providers.radicale_calendar.ics import CalendarIcsCodec


def test_recurring_ics_with_exception_parses_multiple_events(fixtures_dir):
    codec = CalendarIcsCodec()
    ics_text = (fixtures_dir / "ics" / "recurring_with_exception.ics").read_text()
    events = codec.parse_events(ics_text, calendar_ref="cal_default")
    assert len(events) == 2
    assert {event.uid for event in events} == {"series-1@example.com"}
    assert any(event.recurrence_id for event in events)
