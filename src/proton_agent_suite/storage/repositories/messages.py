from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime

from sqlalchemy import or_, select
from sqlalchemy.orm import Session, selectinload

from proton_agent_suite.domain.enums import ErrorCode
from proton_agent_suite.domain.errors import make_error
from proton_agent_suite.storage.schema import MessageLabelRow, MessageRow
from proton_agent_suite.utils.ids import stable_ref
from proton_agent_suite.utils.time import utc_now


class MessagesRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def upsert_message(
        self,
        *,
        folder_name: str,
        imap_uid: int,
        message_id_header: str | None,
        subject: str | None,
        from_address: str | None,
        to_addresses: list[str],
        cc_addresses: list[str],
        date_utc: datetime | None,
        internal_date_utc: datetime | None,
        is_read: bool,
        text_body: str | None,
        html_body: str | None,
        raw_rfc822: bytes | None,
        has_attachments: bool,
        invite_hint: bool,
        checksum: str | None,
    ) -> MessageRow:
        row = self.session.scalar(
            select(MessageRow).where(
                MessageRow.folder_name == folder_name,
                MessageRow.imap_uid == imap_uid,
            )
        )
        if row is None:
            row = MessageRow(
                id=stable_ref("msg", folder_name, imap_uid),
                folder_name=folder_name,
                imap_uid=imap_uid,
            )
            self.session.add(row)
        row.message_id_header = message_id_header
        row.subject = subject
        row.from_address = from_address
        row.to_addresses = "\n".join(to_addresses)
        row.cc_addresses = "\n".join(cc_addresses)
        row.date_utc = date_utc
        row.internal_date_utc = internal_date_utc
        row.is_read = is_read
        row.text_body = text_body
        row.html_body = html_body
        row.raw_rfc822 = raw_rfc822
        row.has_attachments = has_attachments
        row.invite_hint = invite_hint
        row.checksum = checksum
        row.last_seen_utc = utc_now()
        self.session.flush()
        return row

    def get(self, message_ref: str) -> MessageRow:
        row = self.session.scalar(
            select(MessageRow)
            .options(selectinload(MessageRow.attachments), selectinload(MessageRow.labels))
            .where(MessageRow.id == message_ref)
        )
        if row is None:
            raise make_error(ErrorCode.MESSAGE_NOT_FOUND, "Message not found", {"message_ref": message_ref})
        return row

    def list_messages(self, folder_name: str | None = None, limit: int = 50) -> list[MessageRow]:
        stmt = (
            select(MessageRow)
            .options(selectinload(MessageRow.labels), selectinload(MessageRow.attachments))
            .order_by(MessageRow.date_utc.desc().nullslast())
        )
        if folder_name:
            stmt = stmt.where(MessageRow.folder_name == folder_name)
        return list(self.session.scalars(stmt.limit(limit)))

    def unread(self, limit: int = 20) -> list[MessageRow]:
        stmt = (
            select(MessageRow)
            .options(selectinload(MessageRow.labels))
            .where(MessageRow.is_read.is_(False))
            .order_by(MessageRow.date_utc.desc().nullslast())
            .limit(limit)
        )
        return list(self.session.scalars(stmt))

    def search(self, query: str, limit: int = 50) -> list[MessageRow]:
        token = f"%{query.lower()}%"
        stmt = (
            select(MessageRow)
            .options(selectinload(MessageRow.labels))
            .where(
                or_(
                    MessageRow.subject.ilike(token),
                    MessageRow.from_address.ilike(token),
                    MessageRow.text_body.ilike(token),
                    MessageRow.html_body.ilike(token),
                )
            )
            .order_by(MessageRow.date_utc.desc().nullslast())
            .limit(limit)
        )
        return list(self.session.scalars(stmt))

    def set_read(self, message_ref: str, is_read: bool) -> MessageRow:
        row = self.get(message_ref)
        row.is_read = is_read
        self.session.flush()
        return row

    def set_folder(self, message_ref: str, folder_name: str) -> MessageRow:
        row = self.get(message_ref)
        row.folder_name = folder_name
        self.session.flush()
        return row

    def add_label(self, message_ref: str, label_name: str) -> None:
        row = self.get(message_ref)
        existing = self.session.scalar(
            select(MessageLabelRow).where(
                MessageLabelRow.message_id == row.id,
                MessageLabelRow.label_name == label_name,
            )
        )
        if existing is None:
            self.session.add(MessageLabelRow(message_id=row.id, label_name=label_name))
            self.session.flush()

    def remove_label(self, message_ref: str, label_name: str) -> None:
        label = self.session.scalar(
            select(MessageLabelRow).where(
                MessageLabelRow.message_id == message_ref,
                MessageLabelRow.label_name == label_name,
            )
        )
        if label is not None:
            self.session.delete(label)
            self.session.flush()

    def changed_since(self, since: datetime) -> list[MessageRow]:
        stmt = select(MessageRow).where(MessageRow.updated_at >= since).order_by(MessageRow.updated_at.asc())
        return list(self.session.scalars(stmt))
