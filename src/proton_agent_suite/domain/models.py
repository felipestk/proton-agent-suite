from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from proton_agent_suite.domain.enums import EventStatus, InviteStatus, MailboxKind


class HealthCheckResult(BaseModel):
    status: str
    checks: dict[str, Any] = Field(default_factory=dict)


class FolderInfo(BaseModel):
    ref: str
    name: str
    kind: MailboxKind = MailboxKind.FOLDER


class AttachmentInfo(BaseModel):
    ref: str
    filename: str | None = None
    content_type: str | None = None
    size_bytes: int | None = None


class MessageSummary(BaseModel):
    ref: str
    folder: str
    subject: str | None = None
    from_address: str | None = None
    to_addresses: list[str] = Field(default_factory=list)
    date_utc: datetime | None = None
    is_read: bool = False
    invite_hint: bool = False
    labels: list[str] = Field(default_factory=list)


class MessageDetail(MessageSummary):
    text_body: str | None = None
    html_body: str | None = None
    message_id_header: str | None = None
    attachments: list[AttachmentInfo] = Field(default_factory=list)


class DraftModel(BaseModel):
    ref: str
    to_addresses: list[str]
    cc_addresses: list[str] = Field(default_factory=list)
    bcc_addresses: list[str] = Field(default_factory=list)
    subject: str
    body_text: str
    source_message_ref: str | None = None
    created_at: datetime
    sent_at: datetime | None = None


class InviteRecordView(BaseModel):
    ref: str
    uid: str
    organizer: str | None = None
    recurrence_id: str | None = None
    sequence: int = 0
    method: str | None = None
    status: InviteStatus = InviteStatus.PENDING
    summary: str | None = None
    start_utc: datetime | None = None
    end_utc: datetime | None = None
    source_message_ref: str | None = None
    warning_flags: list[str] = Field(default_factory=list)
    reason_codes: list[str] = Field(default_factory=list)
    latest: bool = False


class CalendarInfo(BaseModel):
    ref: str
    name: str
    href: str
    description: str | None = None
    etag: str | None = None
    color: str | None = None
    is_default: bool = False


class EventInfo(BaseModel):
    ref: str
    calendar_ref: str | None = None
    uid: str
    href: str | None = None
    etag: str | None = None
    title: str
    start_utc: datetime
    end_utc: datetime
    timezone_name: str | None = None
    status: EventStatus = EventStatus.CONFIRMED
    sequence: int = 0
    organizer: str | None = None
    recurrence_id: str | None = None
    attendees: list[dict[str, Any]] = Field(default_factory=list)
    updated_at: datetime | None = None


class ConnectorInfo(BaseModel):
    provider: str
    caldav_base_url: str
    username: str
    default_calendar: str | None = None
    calendar_path: str | None = None
    ics_url: str | None = None
    notes: list[str] = Field(default_factory=list)


class SyncStatus(BaseModel):
    scope: str
    last_success_utc: datetime | None = None
    last_error_code: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)


class Snapshot(BaseModel):
    generated_at: datetime
    unread_messages: list[MessageSummary] = Field(default_factory=list)
    pending_invites: list[InviteRecordView] = Field(default_factory=list)
    upcoming_events: list[EventInfo] = Field(default_factory=list)
    sync_status: list[SyncStatus] = Field(default_factory=list)
    recent_failures: list[dict[str, Any]] = Field(default_factory=list)
    connector_info: ConnectorInfo | None = None
    changed_refs: dict[str, list[str]] = Field(default_factory=dict)
