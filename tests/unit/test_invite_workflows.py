from __future__ import annotations

from datetime import UTC, datetime, timedelta

from proton_agent_suite.domain.models import EventAttendee, EventInfo
from proton_agent_suite.domain.services.invite_service import InviteService
from proton_agent_suite.utils.ids import stable_ref


class FakeMailService:
    def __init__(self) -> None:
        self.sent: list[dict[str, object]] = []

    def send(
        self,
        request,
        *,
        source_message_ref=None,
        related_invite_uid=None,
        invite_sequence=None,
        method=None,
    ):
        sent_ref = f"out_{len(self.sent) + 1}"
        result = {
            "status": "sent",
            "sent_ref": sent_ref,
            "message_id": f"<{sent_ref}@example.com>",
            "sent_at": "2026-04-08T12:00:00Z",
        }
        self.sent.append(
            {
                "request": request,
                "source_message_ref": source_message_ref,
                "related_invite_uid": related_invite_uid,
                "invite_sequence": invite_sequence,
                "method": method,
                "result": result,
            }
        )
        return result


class FakeCalendarService:
    def __init__(self) -> None:
        self.events: dict[str, EventInfo] = {}
        self.deleted: list[str] = []

    def create(self, **kwargs) -> EventInfo:
        event = EventInfo(
            ref=stable_ref("evt", kwargs["uid"], ""),
            calendar_ref=kwargs["calendar_ref"],
            uid=kwargs["uid"],
            href=f"/cal/{kwargs['uid']}.ics",
            etag='"etag-0"',
            title=kwargs["title"],
            description=kwargs.get("description"),
            location=kwargs.get("location"),
            start_utc=kwargs["start"],
            end_utc=kwargs["end"],
            timezone_name=kwargs.get("timezone_name"),
            sequence=kwargs.get("sequence", 0),
            organizer=kwargs.get("organizer"),
            organizer_common_name=kwargs.get("organizer_common_name"),
            attendees=kwargs.get("attendees") or [],
        )
        self.events[event.ref] = event
        return event

    def update(self, event_ref: str, **kwargs) -> EventInfo:
        current = self.events[event_ref]
        updated = current.model_copy(
            update={
                "title": kwargs.get("title") or current.title,
                "description": kwargs.get("description")
                if kwargs.get("description") is not None
                else current.description,
                "location": kwargs.get("location")
                if kwargs.get("location") is not None
                else current.location,
                "start_utc": kwargs.get("start") or current.start_utc,
                "end_utc": kwargs.get("end") or current.end_utc,
                "timezone_name": kwargs.get("timezone_name") or current.timezone_name,
                "organizer": kwargs.get("organizer") or current.organizer,
                "organizer_common_name": kwargs.get("organizer_common_name")
                or current.organizer_common_name,
                "attendees": kwargs.get("attendees") if kwargs.get("attendees") is not None else current.attendees,
                "sequence": kwargs.get("sequence") if kwargs.get("sequence") is not None else current.sequence + 1,
                "status": kwargs.get("status") or current.status,
            }
        )
        self.events[event_ref] = updated
        return updated

    def delete(self, event_ref: str):
        self.deleted.append(event_ref)
        self.events.pop(event_ref, None)
        return {"event_ref": event_ref, "status": "deleted"}


def test_invite_create_persists_attendees_and_request_mail(session_factory):
    service = InviteService(session_factory, FakeMailService(), FakeCalendarService())
    start = datetime(2026, 4, 10, 9, 0, tzinfo=UTC)
    end = start + timedelta(hours=1)

    result = service.create(
        calendar_ref="default",
        title="Demo",
        start=start,
        end=end,
        organizer="felipe@nurami.ai",
        organizer_common_name="Felipe",
        attendees=[
            EventAttendee(
                email="felipestark@gmail.com",
                common_name="Felipe Stark",
                role="REQ-PARTICIPANT",
                partstat="NEEDS-ACTION",
                rsvp=True,
            )
        ],
        description="Planning session",
        location="Lisbon",
        timezone_name="Europe/Lisbon",
    )

    invite = service.get(result["invite"]["uid"])
    assert invite.method == "REQUEST"
    assert invite.organizer == "felipe@nurami.ai"
    assert invite.attendees[0].email == "felipestark@gmail.com"
    assert invite.attendees[0].rsvp is True


def test_invite_update_reuses_uid_and_increments_sequence(session_factory):
    mail_service = FakeMailService()
    calendar_service = FakeCalendarService()
    service = InviteService(session_factory, mail_service, calendar_service)
    start = datetime(2026, 4, 10, 9, 0, tzinfo=UTC)
    end = start + timedelta(hours=1)
    created = service.create(
        calendar_ref="default",
        title="Demo",
        start=start,
        end=end,
        organizer="felipe@nurami.ai",
        attendees=[EventAttendee(email="felipestark@gmail.com")],
    )

    updated = service.update(
        created["invite"]["uid"],
        start=start + timedelta(hours=2),
        end=end + timedelta(hours=2),
        location="Porto",
    )

    assert updated["invite"]["uid"] == created["invite"]["uid"]
    assert updated["invite"]["sequence"] == 1
    assert mail_service.sent[-1]["method"] == "REQUEST"


def test_invite_cancel_sends_cancel_and_deletes_local_event(session_factory):
    mail_service = FakeMailService()
    calendar_service = FakeCalendarService()
    service = InviteService(session_factory, mail_service, calendar_service)
    start = datetime(2026, 4, 10, 9, 0, tzinfo=UTC)
    end = start + timedelta(hours=1)
    created = service.create(
        calendar_ref="default",
        title="Demo",
        start=start,
        end=end,
        organizer="felipe@nurami.ai",
        attendees=[EventAttendee(email="felipestark@gmail.com")],
    )

    result = service.cancel(created["invite"]["uid"])

    invite = service.get(created["invite"]["uid"])
    assert result["local_calendar_action"] == "deleted"
    assert invite.method == "CANCEL"
    assert invite.status == "canceled"
    assert mail_service.sent[-1]["method"] == "CANCEL"
    assert stable_ref("evt", created["invite"]["uid"], "") in calendar_service.deleted
