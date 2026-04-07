from __future__ import annotations

import hashlib
from email import policy
from email.header import decode_header, make_header
from email.message import Message
from email.parser import BytesParser
from email.utils import getaddresses, parsedate_to_datetime
from typing import Any

from proton_agent_suite.utils.time import ensure_utc


class ParsedMail:
    def __init__(
        self,
        *,
        subject: str | None,
        from_address: str | None,
        to_addresses: list[str],
        cc_addresses: list[str],
        date_utc: object,
        message_id_header: str | None,
        text_body: str | None,
        html_body: str | None,
        attachments: list[dict[str, Any]],
        invite_hint: bool,
        checksum: str,
    ) -> None:
        self.subject = subject
        self.from_address = from_address
        self.to_addresses = to_addresses
        self.cc_addresses = cc_addresses
        self.date_utc = date_utc
        self.message_id_header = message_id_header
        self.text_body = text_body
        self.html_body = html_body
        self.attachments = attachments
        self.invite_hint = invite_hint
        self.checksum = checksum


class MessageParser:
    def parse_bytes(self, raw_bytes: bytes) -> ParsedMail:
        message = BytesParser(policy=policy.default).parsebytes(raw_bytes)
        subject = decode_mime_header(message.get("Subject"))
        from_address = first_address(message.get_all("From", []))
        to_addresses = addresses(message.get_all("To", []))
        cc_addresses = addresses(message.get_all("Cc", []))
        date_header = message.get("Date")
        date_utc = None
        if date_header:
            try:
                date_utc = ensure_utc(parsedate_to_datetime(date_header))
            except Exception:
                date_utc = None
        attachments: list[dict[str, Any]] = []
        text_body: str | None = None
        html_body: str | None = None
        invite_hint = False
        for part in iterate_leaf_parts(message):
            content_type = part.get_content_type()
            filename = part.get_filename()
            disposition = part.get_content_disposition()
            payload_bytes = part.get_payload(decode=True) or b""
            if content_type == "text/plain" and disposition != "attachment" and text_body is None:
                text_body = decode_payload(part, payload_bytes)
            elif content_type == "text/html" and disposition != "attachment" and html_body is None:
                html_body = decode_payload(part, payload_bytes)
            elif filename or disposition == "attachment" or content_type == "text/calendar":
                attachments.append(
                    {
                        "filename": decode_mime_header(filename) if filename else None,
                        "content_type": content_type,
                        "size_bytes": len(payload_bytes),
                        "content": payload_bytes,
                        "content_id": part.get("Content-ID"),
                        "disposition": disposition,
                        "part_id": None,
                    }
                )
            if content_type == "text/calendar" or (filename and filename.lower().endswith(".ics")):
                invite_hint = True
        if message.get("Content-Class") == "urn:content-classes:calendarmessage":
            invite_hint = True
        body_joined = "\n".join(filter(None, [subject or "", text_body or "", html_body or ""]))
        lowered = body_joined.lower()
        if "meeting invitation" in lowered or "accepted:" in lowered or "tentative:" in lowered:
            invite_hint = True
        return ParsedMail(
            subject=subject,
            from_address=from_address,
            to_addresses=to_addresses,
            cc_addresses=cc_addresses,
            date_utc=date_utc,
            message_id_header=message.get("Message-ID"),
            text_body=text_body,
            html_body=html_body,
            attachments=attachments,
            invite_hint=invite_hint,
            checksum=hashlib.sha256(raw_bytes).hexdigest(),
        )


def decode_payload(part: Message, payload_bytes: bytes) -> str:
    charset = part.get_content_charset() or "utf-8"
    try:
        return payload_bytes.decode(charset, errors="replace")
    except LookupError:
        return payload_bytes.decode("utf-8", errors="replace")


def iterate_leaf_parts(message: Message):
    if message.is_multipart():
        for part in message.iter_parts():
            yield from iterate_leaf_parts(part)
    else:
        yield message


def decode_mime_header(value: str | None) -> str | None:
    if value is None:
        return None
    return str(make_header(decode_header(value)))


def addresses(values: list[str]) -> list[str]:
    return [addr for _, addr in getaddresses(values) if addr]


def first_address(values: list[str]) -> str | None:
    parsed = addresses(values)
    return parsed[0] if parsed else None
