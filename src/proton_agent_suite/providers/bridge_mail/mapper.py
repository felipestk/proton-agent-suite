from __future__ import annotations

from proton_agent_suite.domain.models import AttachmentInfo, MessageDetail, MessageSummary
from proton_agent_suite.storage.schema import MessageRow


class MailMapper:
    @staticmethod
    def summary_from_row(row: MessageRow) -> MessageSummary:
        return MessageSummary(
            ref=row.id,
            folder=row.folder_name,
            subject=row.subject,
            from_address=row.from_address,
            to_addresses=[value for value in row.to_addresses.split("\n") if value],
            date_utc=row.date_utc,
            is_read=row.is_read,
            invite_hint=row.invite_hint,
            labels=[label.label_name for label in getattr(row, "labels", [])],
        )

    @staticmethod
    def detail_from_row(row: MessageRow) -> MessageDetail:
        return MessageDetail(
            **MailMapper.summary_from_row(row).model_dump(),
            text_body=row.text_body,
            html_body=row.html_body,
            message_id_header=row.message_id_header,
            attachments=[
                AttachmentInfo(
                    ref=attachment.id,
                    filename=attachment.filename,
                    content_type=attachment.content_type,
                    size_bytes=attachment.size_bytes,
                )
                for attachment in getattr(row, "attachments", [])
            ],
        )
