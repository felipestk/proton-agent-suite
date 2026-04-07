from __future__ import annotations

from datetime import datetime
from pathlib import Path

from sqlalchemy.orm import Session, sessionmaker

from proton_agent_suite.domain.models import AttachmentInfo, FolderInfo, HealthCheckResult, MessageDetail, MessageSummary
from proton_agent_suite.domain.protocols import MailProvider
from proton_agent_suite.domain.value_objects import MailSendRequest
from proton_agent_suite.providers.bridge_mail.mapper import MailMapper
from proton_agent_suite.storage.repositories.attachments import AttachmentsRepository
from proton_agent_suite.storage.repositories.folders import FoldersRepository
from proton_agent_suite.storage.repositories.messages import MessagesRepository
from proton_agent_suite.utils.fs import ensure_parent_dir


class MailService:
    def __init__(self, session_factory: sessionmaker[Session], provider: MailProvider) -> None:
        self.session_factory = session_factory
        self.provider = provider

    def health(self) -> HealthCheckResult:
        return self.provider.healthcheck()

    def folders(self) -> list[FolderInfo]:
        folders = self.provider.list_folders()
        with self.session_factory() as session:
            repo = FoldersRepository(session)
            for folder in folders:
                repo.upsert(folder.name, folder.kind)
            session.commit()
        return folders

    def sync(self, folder: str, since: datetime) -> dict[str, object]:
        messages = self.provider.sync_folder(folder, since)
        synced_refs: list[str] = []
        with self.session_factory() as session:
            folders_repo = FoldersRepository(session)
            folders_repo.upsert(folder)
            messages_repo = MessagesRepository(session)
            attachments_repo = AttachmentsRepository(session)
            for message in messages:
                row = messages_repo.upsert_message(
                    folder_name=folder,
                    imap_uid=int(message.__dict__["_uid"]),
                    message_id_header=message.message_id_header,
                    subject=message.subject,
                    from_address=message.from_address,
                    to_addresses=message.to_addresses,
                    cc_addresses=[],
                    date_utc=message.date_utc,
                    internal_date_utc=message.__dict__.get("_internal_date"),
                    is_read=message.is_read,
                    text_body=message.text_body,
                    html_body=message.html_body,
                    raw_rfc822=message.__dict__.get("_raw_bytes"),
                    has_attachments=bool(message.__dict__.get("_attachments_payload")),
                    invite_hint=message.invite_hint,
                    checksum=message.__dict__.get("_checksum"),
                )
                attachments_repo.replace_for_message(row.id, list(message.__dict__.get("_attachments_payload", [])))
                synced_refs.append(row.id)
            session.commit()
        return {"folder": folder, "synced": len(synced_refs), "message_refs": synced_refs}

    def list_messages(self, folder: str | None = None, limit: int = 50) -> list[MessageSummary]:
        with self.session_factory() as session:
            rows = MessagesRepository(session).list_messages(folder_name=folder, limit=limit)
            return [MailMapper.summary_from_row(row) for row in rows]

    def read(self, message_ref: str) -> MessageDetail:
        with self.session_factory() as session:
            row = MessagesRepository(session).get(message_ref)
            return MailMapper.detail_from_row(row)

    def raw(self, message_ref: str) -> bytes:
        with self.session_factory() as session:
            row = MessagesRepository(session).get(message_ref)
            return row.raw_rfc822 or b""

    def search(self, query: str, limit: int = 50) -> list[MessageSummary]:
        with self.session_factory() as session:
            rows = MessagesRepository(session).search(query, limit=limit)
            return [MailMapper.summary_from_row(row) for row in rows]

    def send(self, request: MailSendRequest) -> dict[str, str]:
        return self.provider.send_message(request)

    def create_draft(
        self,
        *,
        to_addresses: list[str],
        cc_addresses: list[str],
        bcc_addresses: list[str],
        subject: str,
        body_text: str,
        source_message_ref: str | None = None,
    ) -> dict[str, object]:
        from proton_agent_suite.storage.repositories.drafts import DraftsRepository

        with self.session_factory() as session:
            row = DraftsRepository(session).create(
                to_addresses=to_addresses,
                cc_addresses=cc_addresses,
                bcc_addresses=bcc_addresses,
                subject=subject,
                body_text=body_text,
                source_message_ref=source_message_ref,
            )
            session.commit()
            return {"ref": row.id, "subject": row.subject}

    def list_drafts(self) -> list[dict[str, object]]:
        from proton_agent_suite.storage.repositories.drafts import DraftsRepository

        with self.session_factory() as session:
            rows = DraftsRepository(session).list_all()
            return [
                {
                    "ref": row.id,
                    "to_addresses": [value for value in row.to_addresses.split("\n") if value],
                    "subject": row.subject,
                    "created_at": row.created_at,
                    "sent_at": row.sent_at,
                }
                for row in rows
            ]

    def send_draft(self, draft_ref: str) -> dict[str, object]:
        from proton_agent_suite.storage.repositories.drafts import DraftsRepository

        with self.session_factory() as session:
            repo = DraftsRepository(session)
            row = repo.get(draft_ref)
            result = self.send(
                MailSendRequest(
                    to_addresses=[value for value in row.to_addresses.split("\n") if value],
                    cc_addresses=[value for value in row.cc_addresses.split("\n") if value],
                    bcc_addresses=[value for value in row.bcc_addresses.split("\n") if value],
                    subject=row.subject,
                    body_text=row.body_text,
                )
            )
            repo.mark_sent(draft_ref)
            session.commit()
            return {"ref": row.id, **result}

    def reply(self, message_ref: str, body_text: str) -> dict[str, str]:
        with self.session_factory() as session:
            message = MessagesRepository(session).get(message_ref)
            recipients = [message.from_address] if message.from_address else []
            subject = message.subject or ""
            prefixed = subject if subject.lower().startswith("re:") else f"Re: {subject}"
            request = MailSendRequest(
                to_addresses=recipients,
                subject=prefixed,
                body_text=body_text,
                in_reply_to=message.message_id_header,
                references=[message.message_id_header] if message.message_id_header else [],
            )
        return self.provider.send_message(request)

    def attachments(self, message_ref: str) -> list[AttachmentInfo]:
        with self.session_factory() as session:
            rows = AttachmentsRepository(session).list_for_message(message_ref)
            return [
                AttachmentInfo(
                    ref=row.id,
                    filename=row.filename,
                    content_type=row.content_type,
                    size_bytes=row.size_bytes,
                )
                for row in rows
            ]

    def save_attachment(self, message_ref: str, attachment_ref: str, out_dir: Path) -> dict[str, object]:
        with self.session_factory() as session:
            attachment = AttachmentsRepository(session).get(attachment_ref)
            filename = attachment.filename or attachment.id
            target = out_dir / filename
            ensure_parent_dir(target)
            target.write_bytes(attachment.content or b"")
            return {
                "message_ref": message_ref,
                "attachment_ref": attachment_ref,
                "path": str(target),
                "size_bytes": len(attachment.content or b""),
            }

    def mark_read(self, message_ref: str, is_read: bool) -> dict[str, object]:
        with self.session_factory() as session:
            repo = MessagesRepository(session)
            row = repo.get(message_ref)
            if is_read:
                self.provider.mark_read(row.folder_name, row.imap_uid)
            else:
                self.provider.mark_unread(row.folder_name, row.imap_uid)
            row = repo.set_read(message_ref, is_read)
            session.commit()
            return {"ref": row.id, "is_read": row.is_read}

    def move(self, message_ref: str, folder: str) -> dict[str, object]:
        with self.session_factory() as session:
            repo = MessagesRepository(session)
            row = repo.get(message_ref)
            self.provider.move_message(row.folder_name, row.imap_uid, folder)
            row = repo.set_folder(message_ref, folder)
            session.commit()
            return {"ref": row.id, "folder": row.folder_name}

    def archive(self, message_ref: str) -> dict[str, object]:
        with self.session_factory() as session:
            repo = MessagesRepository(session)
            row = repo.get(message_ref)
            self.provider.archive_message(row.folder_name, row.imap_uid)
            row = repo.set_folder(message_ref, "Archive")
            session.commit()
            return {"ref": row.id, "folder": row.folder_name}

    def labels(self) -> list[str]:
        return self.provider.list_labels()

    def add_label(self, message_ref: str, label_name: str) -> dict[str, object]:
        with self.session_factory() as session:
            repo = MessagesRepository(session)
            row = repo.get(message_ref)
            self.provider.add_label(row.folder_name, row.imap_uid, label_name)
            repo.add_label(message_ref, label_name)
            session.commit()
            return {"ref": message_ref, "label": label_name}

    def remove_label(self, message_ref: str, label_name: str) -> dict[str, object]:
        with self.session_factory() as session:
            repo = MessagesRepository(session)
            row = repo.get(message_ref)
            if row.message_id_header:
                self.provider.remove_label(row.message_id_header, label_name)
            repo.remove_label(message_ref, label_name)
            session.commit()
            return {"ref": message_ref, "label": label_name}
