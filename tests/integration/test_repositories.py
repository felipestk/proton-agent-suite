from __future__ import annotations

from proton_agent_suite.storage.repositories.attachments import AttachmentsRepository
from proton_agent_suite.storage.repositories.messages import MessagesRepository


def test_message_and_attachment_repositories(session_factory):
    with session_factory() as session:
        messages = MessagesRepository(session)
        attachments = AttachmentsRepository(session)
        row = messages.upsert_message(
            folder_name="Inbox",
            imap_uid=42,
            message_id_header="<repo-test@example.com>",
            subject="Repository test",
            from_address="alice@example.com",
            to_addresses=["bob@example.com"],
            cc_addresses=[],
            date_utc=None,
            internal_date_utc=None,
            is_read=False,
            text_body="body",
            html_body=None,
            raw_rfc822=b"raw",
            has_attachments=True,
            invite_hint=False,
            checksum="abc",
        )
        attachments.replace_for_message(
            row.id,
            [
                {
                    "filename": "demo.txt",
                    "content_type": "text/plain",
                    "size_bytes": 4,
                    "content": b"demo",
                    "disposition": "attachment",
                }
            ],
        )
        session.commit()

    with session_factory() as session:
        rows = MessagesRepository(session).search("repository")
        assert len(rows) == 1
        listed = AttachmentsRepository(session).list_for_message(rows[0].id)
        assert listed[0].filename == "demo.txt"
        assert listed[0].content == b"demo"
