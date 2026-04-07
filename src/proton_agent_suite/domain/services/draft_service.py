from __future__ import annotations

from sqlalchemy.orm import Session, sessionmaker

from proton_agent_suite.domain.services.mail_service import MailService


class DraftService:
    def __init__(self, session_factory: sessionmaker[Session], mail_service: MailService) -> None:
        self.session_factory = session_factory
        self.mail_service = mail_service

    def draft(self, **kwargs: object) -> dict[str, object]:
        return self.mail_service.create_draft(**kwargs)
