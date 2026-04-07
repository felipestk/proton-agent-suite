from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from proton_agent_suite.domain.enums import ErrorCode
from proton_agent_suite.domain.errors import make_error
from proton_agent_suite.storage.schema import LocalDraftRow
from proton_agent_suite.utils.ids import new_ref
from proton_agent_suite.utils.time import utc_now


class DraftsRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create(
        self,
        *,
        to_addresses: list[str],
        cc_addresses: list[str],
        bcc_addresses: list[str],
        subject: str,
        body_text: str,
        source_message_ref: str | None = None,
    ) -> LocalDraftRow:
        row = LocalDraftRow(
            id=new_ref("drf"),
            to_addresses="\n".join(to_addresses),
            cc_addresses="\n".join(cc_addresses),
            bcc_addresses="\n".join(bcc_addresses),
            subject=subject,
            body_text=body_text,
            source_message_ref=source_message_ref,
        )
        self.session.add(row)
        self.session.flush()
        return row

    def list_all(self) -> list[LocalDraftRow]:
        return list(self.session.scalars(select(LocalDraftRow).order_by(LocalDraftRow.created_at.desc())))

    def get(self, draft_ref: str) -> LocalDraftRow:
        row = self.session.scalar(select(LocalDraftRow).where(LocalDraftRow.id == draft_ref))
        if row is None:
            raise make_error(ErrorCode.VALIDATION_ERROR, "Draft not found", {"draft_ref": draft_ref})
        return row

    def mark_sent(self, draft_ref: str) -> LocalDraftRow:
        row = self.get(draft_ref)
        row.sent_at = utc_now()
        self.session.flush()
        return row
