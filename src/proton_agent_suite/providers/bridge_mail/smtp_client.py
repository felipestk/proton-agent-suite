from __future__ import annotations

import smtplib
from datetime import UTC, datetime
from email.message import EmailMessage
from email.utils import format_datetime, make_msgid

from proton_agent_suite.domain.enums import ErrorCode
from proton_agent_suite.domain.errors import make_error
from proton_agent_suite.domain.value_objects import BridgeSettings, MailSendRequest


class BridgeSmtpClient:
    def __init__(self, settings: BridgeSettings) -> None:
        self.settings = settings

    def send_message(self, request: MailSendRequest) -> dict[str, str]:
        message = EmailMessage()
        message["From"] = self.settings.username or ""
        message["To"] = ", ".join(request.to_addresses)
        if request.cc_addresses:
            message["Cc"] = ", ".join(request.cc_addresses)
        if request.bcc_addresses:
            message["Bcc"] = ", ".join(request.bcc_addresses)
        message["Subject"] = request.subject
        if request.in_reply_to:
            message["In-Reply-To"] = request.in_reply_to
        if request.references:
            message["References"] = " ".join(request.references)
        for name, value in request.headers.items():
            message[name] = value
        if "Message-ID" not in message:
            message["Message-ID"] = make_msgid()
        message["Date"] = format_datetime(datetime.now(UTC))
        message.set_content(request.body_text)
        for attachment in request.attachments:
            maintype, subtype = attachment.content_type.split("/", 1)
            add_kwargs = {
                "maintype": maintype,
                "subtype": subtype,
                "filename": attachment.filename,
                "disposition": attachment.disposition,
            }
            if attachment.content_id is not None:
                add_kwargs["cid"] = attachment.content_id
            if attachment.params:
                add_kwargs["params"] = attachment.params
            message.add_attachment(attachment.content, **add_kwargs)
        try:
            with smtplib.SMTP(self.settings.host, self.settings.smtp_port, timeout=10) as smtp:
                smtp.login(self.settings.username or "", self.settings.password or "")
                smtp.send_message(message)
        except smtplib.SMTPAuthenticationError as exc:
            raise make_error(ErrorCode.BRIDGE_AUTH_FAILED, "Bridge SMTP authentication failed") from exc
        except OSError as exc:
            raise make_error(ErrorCode.BRIDGE_SMTP_UNAVAILABLE, "Bridge SMTP is unavailable", {"reason": str(exc)}) from exc
        except smtplib.SMTPException as exc:
            raise make_error(ErrorCode.SMTP_SEND_FAILED, "Failed to send email", {"reason": str(exc)}) from exc
        return {
            "status": "sent",
            "message_id": str(message["Message-ID"]),
            "sent_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        }
