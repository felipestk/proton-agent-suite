from __future__ import annotations

import imaplib
from datetime import UTC, datetime

from imapclient import IMAPClient

from proton_agent_suite.domain.enums import ErrorCode, MailboxKind
from proton_agent_suite.domain.errors import make_error
from proton_agent_suite.domain.models import FolderInfo, HealthCheckResult, MessageDetail
from proton_agent_suite.domain.value_objects import BridgeSettings, MailSendRequest
from proton_agent_suite.providers.bridge_mail.health import tcp_check
from proton_agent_suite.providers.bridge_mail.parser import MessageParser
from proton_agent_suite.providers.bridge_mail.smtp_client import BridgeSmtpClient
from proton_agent_suite.utils.ids import stable_ref
from proton_agent_suite.utils.time import ensure_utc


class BridgeMailProvider:
    _SYSTEM_FOLDERS = {
        "all mail",
        "archive",
        "drafts",
        "important",
        "inbox",
        "junk",
        "sent",
        "sent mail",
        "spam",
        "starred",
        "trash",
    }

    def __init__(self, settings: BridgeSettings) -> None:
        self.settings = settings
        self._parser = MessageParser()
        self._smtp = BridgeSmtpClient(settings)

    def _is_label_mailbox(self, name: str) -> bool:
        return name == self.settings.label_prefix or name.startswith(f"{self.settings.label_prefix}/")

    def _is_custom_folder_mailbox(self, name: str) -> bool:
        return name == self.settings.folder_prefix or name.startswith(f"{self.settings.folder_prefix}/")

    def _is_system_mailbox(self, name: str) -> bool:
        return name.lower() in self._SYSTEM_FOLDERS

    def _normalize_folder_name(self, name: str) -> str:
        value = name.strip()
        if not value:
            return value
        if self._is_label_mailbox(value) or self._is_custom_folder_mailbox(value) or self._is_system_mailbox(value):
            return value
        return f"{self.settings.folder_prefix}/{value}"

    def _logical_folder_name(self, remote_name: str) -> str:
        prefix = f"{self.settings.folder_prefix}/"
        if remote_name.startswith(prefix):
            return remote_name[len(prefix) :]
        return remote_name

    def _logical_label_name(self, remote_name: str) -> str:
        prefix = f"{self.settings.label_prefix}/"
        if remote_name.startswith(prefix):
            return remote_name[len(prefix) :]
        return remote_name

    def normalize_folder_name(self, name: str) -> str:
        return self._normalize_folder_name(name)

    def _folder_info(self, remote_name: str) -> FolderInfo:
        if self._is_label_mailbox(remote_name):
            return FolderInfo(
                ref=stable_ref("fld", remote_name),
                name=self._logical_label_name(remote_name),
                remote_name=remote_name,
                kind=MailboxKind.LABEL,
            )
        return FolderInfo(
            ref=stable_ref("fld", remote_name),
            name=self._logical_folder_name(remote_name),
            remote_name=remote_name,
            kind=MailboxKind.FOLDER,
        )

    def _connect(self) -> IMAPClient:
        try:
            client = IMAPClient(
                host=self.settings.host,
                port=self.settings.imap_port,
                use_uid=True,
                ssl=False,
            )
            client.login(self.settings.username or "", self.settings.password or "")
            return client
        except imaplib.IMAP4.error as exc:
            raise make_error(ErrorCode.BRIDGE_AUTH_FAILED, "Bridge IMAP authentication failed") from exc
        except ConnectionRefusedError as exc:
            code = (
                ErrorCode.BRIDGE_NOT_RUNNING
                if self.settings.host in {"127.0.0.1", "localhost"}
                else ErrorCode.BRIDGE_UNREACHABLE
            )
            raise make_error(
                code,
                "Bridge IMAP is not reachable",
                {"host": self.settings.host, "port": self.settings.imap_port},
            ) from exc
        except OSError as exc:
            raise make_error(
                ErrorCode.BRIDGE_UNREACHABLE,
                "Bridge IMAP is not reachable",
                {"reason": str(exc)},
            ) from exc

    def healthcheck(self) -> HealthCheckResult:
        checks = {
            "imap_tcp": tcp_check(self.settings.host, self.settings.imap_port),
            "smtp_tcp": tcp_check(self.settings.host, self.settings.smtp_port),
        }
        if not checks["imap_tcp"]["ok"]:
            code = (
                ErrorCode.BRIDGE_NOT_RUNNING
                if self.settings.host in {"127.0.0.1", "localhost"}
                else ErrorCode.BRIDGE_UNREACHABLE
            )
            raise make_error(code, "Bridge IMAP port is not reachable", checks)
        with self._connect() as client:
            checks["imap_login"] = {
                "ok": True,
                "capabilities": sorted(
                    cap.decode() if isinstance(cap, bytes) else str(cap)
                    for cap in client.capabilities()
                ),
            }
        if not checks["smtp_tcp"]["ok"]:
            raise make_error(ErrorCode.BRIDGE_SMTP_UNAVAILABLE, "Bridge SMTP port is not reachable", checks)
        return HealthCheckResult(status="ok", checks=checks)

    def list_folders(self) -> list[FolderInfo]:
        with self._connect() as client:
            folders = client.list_folders()
        results = [self._folder_info(name) for _flags, _delimiter, name in folders]
        return sorted(results, key=lambda item: item.name.lower())

    def sync_folder(self, folder: str, since: datetime) -> list[MessageDetail]:
        remote_folder = self._normalize_folder_name(folder)
        with self._connect() as client:
            try:
                client.select_folder(remote_folder, readonly=True)
            except imaplib.IMAP4.error as exc:
                raise make_error(
                    ErrorCode.MAIL_FOLDER_NOT_FOUND,
                    "Folder not found",
                    {"folder": folder, "remote_folder": remote_folder},
                ) from exc
            uids = client.search(["SINCE", since.date()])
            if not uids:
                return []
            fetch_data = client.fetch(uids, [b"RFC822", b"FLAGS", b"INTERNALDATE"])
        items: list[MessageDetail] = []
        for uid in sorted(fetch_data):
            raw_bytes = fetch_data[uid][b"RFC822"]
            parsed = self._parser.parse_bytes(raw_bytes)
            flags = fetch_data[uid].get(b"FLAGS", tuple())
            is_read = b"\\Seen" in flags or "\\Seen" in flags
            detail = MessageDetail(
                ref=stable_ref("msg", folder, uid),
                folder=folder,
                subject=parsed.subject,
                from_address=parsed.from_address,
                to_addresses=parsed.to_addresses,
                date_utc=parsed.date_utc,
                is_read=is_read,
                invite_hint=parsed.invite_hint,
                labels=[],
                text_body=parsed.text_body,
                html_body=parsed.html_body,
                message_id_header=parsed.message_id_header,
                attachments=[],
            )
            detail.__dict__["_raw_bytes"] = raw_bytes
            detail.__dict__["_attachments_payload"] = parsed.attachments
            detail.__dict__["_checksum"] = parsed.checksum
            detail.__dict__["_internal_date"] = (
                ensure_utc(fetch_data[uid].get(b"INTERNALDATE"))
                if fetch_data[uid].get(b"INTERNALDATE")
                else None
            )
            detail.__dict__["_uid"] = uid
            items.append(detail)
        return items

    def fetch_message(self, folder: str, uid: int) -> MessageDetail:
        messages = self.sync_folder(folder, datetime(1970, 1, 1, tzinfo=UTC))
        for message in messages:
            if message.ref == stable_ref("msg", folder, uid):
                return message
        raise make_error(ErrorCode.MESSAGE_NOT_FOUND, "Message not found", {"folder": folder, "uid": uid})

    def fetch_raw_message(self, folder: str, uid: int) -> bytes:
        remote_folder = self._normalize_folder_name(folder)
        with self._connect() as client:
            client.select_folder(remote_folder, readonly=True)
            fetch_data = client.fetch([uid], [b"RFC822"])
            raw = fetch_data.get(uid, {}).get(b"RFC822")
            if raw is None:
                raise make_error(ErrorCode.MESSAGE_NOT_FOUND, "Message not found", {"folder": folder, "uid": uid})
            return raw

    def send_message(self, request: MailSendRequest) -> dict[str, str]:
        return self._smtp.send_message(request)

    def mark_read(self, folder: str, uid: int) -> None:
        remote_folder = self._normalize_folder_name(folder)
        with self._connect() as client:
            client.select_folder(remote_folder)
            client.add_flags([uid], [b"\\Seen"])

    def mark_unread(self, folder: str, uid: int) -> None:
        remote_folder = self._normalize_folder_name(folder)
        with self._connect() as client:
            client.select_folder(remote_folder)
            client.remove_flags([uid], [b"\\Seen"])

    def move_message(self, source_folder: str, uid: int, target_folder: str) -> None:
        remote_source = self._normalize_folder_name(source_folder)
        remote_target = self._normalize_folder_name(target_folder)
        with self._connect() as client:
            client.select_folder(remote_source)
            try:
                client.move([uid], remote_target)
            except Exception:
                client.copy([uid], remote_target)
                client.delete_messages([uid])
                client.expunge()

    def archive_message(self, source_folder: str, uid: int) -> None:
        self.move_message(source_folder, uid, "Archive")

    def list_labels(self) -> list[str]:
        labels = [folder.name for folder in self.list_folders() if folder.kind == MailboxKind.LABEL]
        return labels

    def add_label(self, source_folder: str, uid: int, label_name: str) -> None:
        target = f"{self.settings.label_prefix}/{label_name}"
        remote_source = self._normalize_folder_name(source_folder)
        with self._connect() as client:
            client.select_folder(remote_source)
            client.copy([uid], target)

    def remove_label(self, message_id_header: str, label_name: str) -> None:
        target = f"{self.settings.label_prefix}/{label_name}"
        with self._connect() as client:
            client.select_folder(target)
            uids = client.search(["HEADER", "Message-ID", message_id_header])
            if not uids:
                raise make_error(
                    ErrorCode.MESSAGE_NOT_FOUND,
                    "Message not found in label mailbox",
                    {"label": label_name},
                )
            client.delete_messages(uids)
            client.expunge()

    def create_folder(self, name: str) -> FolderInfo:
        remote_name = self._normalize_folder_name(name)
        with self._connect() as client:
            try:
                client.create_folder(remote_name)
            except imaplib.IMAP4.error as exc:
                raise make_error(
                    ErrorCode.VALIDATION_ERROR,
                    "Failed to create folder",
                    {"folder": name, "remote_folder": remote_name, "reason": str(exc)},
                ) from exc
        return self._folder_info(remote_name)

    def rename_folder(self, old_name: str, new_name: str) -> FolderInfo:
        remote_old_name = self._normalize_folder_name(old_name)
        remote_new_name = self._normalize_folder_name(new_name)
        with self._connect() as client:
            try:
                client.rename_folder(remote_old_name, remote_new_name)
            except imaplib.IMAP4.error as exc:
                raise make_error(
                    ErrorCode.VALIDATION_ERROR,
                    "Failed to rename folder",
                    {
                        "from": old_name,
                        "to": new_name,
                        "remote_from": remote_old_name,
                        "remote_to": remote_new_name,
                        "reason": str(exc),
                    },
                ) from exc
        return self._folder_info(remote_new_name)

    def delete_folder(self, name: str) -> None:
        remote_name = self._normalize_folder_name(name)
        with self._connect() as client:
            try:
                client.delete_folder(remote_name)
            except imaplib.IMAP4.error as exc:
                raise make_error(
                    ErrorCode.VALIDATION_ERROR,
                    "Failed to delete folder",
                    {"folder": name, "remote_folder": remote_name, "reason": str(exc)},
                ) from exc
