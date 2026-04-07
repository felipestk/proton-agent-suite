from __future__ import annotations

from hashlib import sha256

from sqlalchemy import select
from sqlalchemy.orm import Session

from proton_agent_suite.domain.enums import ErrorCode
from proton_agent_suite.domain.errors import make_error
from proton_agent_suite.storage.schema import AttachmentRow
from proton_agent_suite.utils.ids import stable_ref


class AttachmentsRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def replace_for_message(self, message_id: str, attachments: list[dict[str, object]]) -> None:
        existing = list(self.session.scalars(select(AttachmentRow).where(AttachmentRow.message_id == message_id)))
        for row in existing:
            self.session.delete(row)
        for index, attachment in enumerate(attachments):
            content = attachment.get("content")
            self.session.add(
                AttachmentRow(
                    id=stable_ref("att", message_id, index, attachment.get("filename") or "attachment"),
                    message_id=message_id,
                    filename=str(attachment.get("filename") or "") or None,
                    content_type=str(attachment.get("content_type") or "") or None,
                    size_bytes=int(attachment.get("size_bytes") or 0) or None,
                    sha256=sha256(content).hexdigest() if isinstance(content, bytes) else None,
                    content=content if isinstance(content, bytes) else None,
                    content_id=str(attachment.get("content_id") or "") or None,
                    disposition=str(attachment.get("disposition") or "") or None,
                    part_id=str(attachment.get("part_id") or "") or None,
                )
            )
        self.session.flush()

    def list_for_message(self, message_id: str) -> list[AttachmentRow]:
        stmt = select(AttachmentRow).where(AttachmentRow.message_id == message_id).order_by(AttachmentRow.filename.asc())
        return list(self.session.scalars(stmt))

    def get(self, attachment_ref: str) -> AttachmentRow:
        row = self.session.scalar(select(AttachmentRow).where(AttachmentRow.id == attachment_ref))
        if row is None:
            raise make_error(ErrorCode.ATTACHMENT_NOT_FOUND, "Attachment not found", {"attachment_ref": attachment_ref})
        return row
