from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy.orm import Session, sessionmaker

from proton_agent_suite.domain.services.calendar_service import CalendarService
from proton_agent_suite.domain.services.invite_service import InviteService
from proton_agent_suite.domain.services.mail_service import MailService
from proton_agent_suite.storage.repositories.sync_state import SyncStateRepository
from proton_agent_suite.utils.time import utc_now


class SyncService:
    def __init__(
        self,
        session_factory: sessionmaker[Session],
        mail_service: MailService,
        invite_service: InviteService,
        calendar_service: CalendarService,
    ) -> None:
        self.session_factory = session_factory
        self.mail_service = mail_service
        self.invite_service = invite_service
        self.calendar_service = calendar_service

    def sync_mail(self, folder: str = "Inbox", since: datetime | None = None) -> dict[str, object]:
        since = since or (utc_now() - timedelta(days=30))
        result = self.mail_service.sync(folder, since)
        with self.session_factory() as session:
            SyncStateRepository(session).record_success("mail", folder, {"synced": result["synced"]})
            session.commit()
        return result

    def sync_invites(self) -> dict[str, object]:
        result = self.invite_service.scan()
        with self.session_factory() as session:
            SyncStateRepository(session).record_success("invites", "default", {"scanned": result["scanned"]})
            session.commit()
        return result

    def sync_calendar(self, days: int = 30) -> dict[str, object]:
        events = self.calendar_service.upcoming(days)
        with self.session_factory() as session:
            SyncStateRepository(session).record_success("calendar", "default", {"events": len(events)})
            session.commit()
        return {"events": len(events)}

    def sync_all(self) -> dict[str, object]:
        return {
            "mail": self.sync_mail(),
            "invites": self.sync_invites(),
            "calendar": self.sync_calendar(),
        }
