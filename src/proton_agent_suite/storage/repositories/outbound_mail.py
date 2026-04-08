from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from proton_agent_suite.domain.enums import ErrorCode
from proton_agent_suite.domain.errors import make_error
from proton_agent_suite.storage.schema import OutboundMailRow
from proton_agent_suite.utils.ids import stable_ref


class OutboundMailRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create(
        self,
        *,
        subject: str | None,
        to_addresses: list[str],
        cc_addresses: list[str],
        bcc_addresses: list[str],
        source_message_ref: str | None,
        related_invite_uid: str | None,
        invite_sequence: int | None,
        method: str | None,
    ) -> OutboundMailRow:
        row = OutboundMailRow(
            id=stable_ref(
                "out",
                subject or "",
                "\n".join(sorted(to_addresses)),
                related_invite_uid or "",
                invite_sequence if invite_sequence is not None else "",
                datetime.now(UTC).isoformat(),
            ),
            subject=subject,
            to_addresses="\n".join(to_addresses),
            cc_addresses="\n".join(cc_addresses),
            bcc_addresses="\n".join(bcc_addresses),
            source_message_ref=source_message_ref,
            related_invite_uid=related_invite_uid,
            invite_sequence=invite_sequence,
            method=method,
            status="pending",
        )
        self.session.add(row)
        self.session.flush()
        return row

    def mark_sent(
        self,
        outbound_ref: str,
        *,
        message_id: str | None,
        response_json: dict[str, object],
    ) -> OutboundMailRow:
        row = self.get(outbound_ref)
        row.message_id_header = message_id
        row.response_json = response_json
        row.status = "sent"
        row.sent_at = datetime.now(UTC)
        self.session.flush()
        return row

    def get(self, outbound_ref: str) -> OutboundMailRow:
        row = self.session.scalar(select(OutboundMailRow).where(OutboundMailRow.id == outbound_ref))
        if row is None:
            raise make_error(ErrorCode.MESSAGE_NOT_FOUND, "Outbound message not found", {"outbound_ref": outbound_ref})
        return row

    def list_recent(self, limit: int = 50) -> list[OutboundMailRow]:
        stmt = select(OutboundMailRow).order_by(OutboundMailRow.created_at.desc()).limit(limit)
        return list(self.session.scalars(stmt))
