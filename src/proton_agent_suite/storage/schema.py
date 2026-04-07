from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import (
    JSON,
    BLOB,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


def utcnow() -> datetime:
    return datetime.now(UTC)


class AccountRow(Base):
    __tablename__ = "accounts"
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    profile: Mapped[str] = mapped_column(String(100), unique=True)
    provider: Mapped[str] = mapped_column(String(50))
    email_address: Mapped[str | None] = mapped_column(String(320), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class FolderRow(Base):
    __tablename__ = "folders"
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    account_id: Mapped[str | None] = mapped_column(ForeignKey("accounts.id"), nullable=True)
    remote_name: Mapped[str] = mapped_column(String(255), unique=True)
    display_name: Mapped[str] = mapped_column(String(255))
    kind: Mapped[str] = mapped_column(String(20), default="folder")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class MessageRow(Base):
    __tablename__ = "messages"
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    account_id: Mapped[str | None] = mapped_column(ForeignKey("accounts.id"), nullable=True)
    folder_name: Mapped[str] = mapped_column(String(255), index=True)
    imap_uid: Mapped[int] = mapped_column(Integer, index=True)
    message_id_header: Mapped[str | None] = mapped_column(String(998), nullable=True, index=True)
    subject: Mapped[str | None] = mapped_column(Text, nullable=True)
    from_address: Mapped[str | None] = mapped_column(String(320), nullable=True)
    to_addresses: Mapped[str] = mapped_column(Text, default="")
    cc_addresses: Mapped[str] = mapped_column(Text, default="")
    date_utc: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    internal_date_utc: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    thread_ref: Mapped[str | None] = mapped_column(String(32), nullable=True)
    text_body: Mapped[str | None] = mapped_column(Text, nullable=True)
    html_body: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_rfc822: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    has_attachments: Mapped[bool] = mapped_column(Boolean, default=False)
    invite_hint: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    checksum: Mapped[str | None] = mapped_column(String(64), nullable=True)
    last_seen_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    attachments: Mapped[list[AttachmentRow]] = relationship(back_populates="message", cascade="all, delete-orphan")
    labels: Mapped[list[MessageLabelRow]] = relationship(back_populates="message", cascade="all, delete-orphan")

    __table_args__ = (UniqueConstraint("folder_name", "imap_uid", name="uq_messages_folder_uid"),)


class AttachmentRow(Base):
    __tablename__ = "attachments"
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    message_id: Mapped[str] = mapped_column(ForeignKey("messages.id"), index=True)
    filename: Mapped[str | None] = mapped_column(Text, nullable=True)
    content_type: Mapped[str | None] = mapped_column(String(255), nullable=True)
    size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    content: Mapped[bytes | None] = mapped_column(BLOB, nullable=True)
    content_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    disposition: Mapped[str | None] = mapped_column(String(50), nullable=True)
    part_id: Mapped[str | None] = mapped_column(String(50), nullable=True)

    message: Mapped[MessageRow] = relationship(back_populates="attachments")


class MessageLabelRow(Base):
    __tablename__ = "message_labels"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    message_id: Mapped[str] = mapped_column(ForeignKey("messages.id"), index=True)
    label_name: Mapped[str] = mapped_column(String(255), index=True)

    message: Mapped[MessageRow] = relationship(back_populates="labels")

    __table_args__ = (UniqueConstraint("message_id", "label_name", name="uq_message_label"),)


class LocalDraftRow(Base):
    __tablename__ = "local_drafts"
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    to_addresses: Mapped[str] = mapped_column(Text)
    cc_addresses: Mapped[str] = mapped_column(Text, default="")
    bcc_addresses: Mapped[str] = mapped_column(Text, default="")
    subject: Mapped[str] = mapped_column(Text)
    body_text: Mapped[str] = mapped_column(Text)
    source_message_ref: Mapped[str | None] = mapped_column(String(32), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class InviteRecordRow(Base):
    __tablename__ = "invite_records"
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    uid: Mapped[str] = mapped_column(String(255), index=True)
    organizer: Mapped[str | None] = mapped_column(String(320), nullable=True, index=True)
    recurrence_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    sequence: Mapped[int] = mapped_column(Integer, default=0)
    method: Mapped[str | None] = mapped_column(String(50), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    start_utc: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    end_utc: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    timezone_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    source_message_ref: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    warning_flags: Mapped[list[str]] = mapped_column(JSON, default=list)
    reason_codes: Mapped[list[str]] = mapped_column(JSON, default=list)
    latest: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    raw_ics: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    __table_args__ = (UniqueConstraint("uid", "organizer", "recurrence_id", "sequence", name="uq_invite_record"),)


class InviteInstanceRow(Base):
    __tablename__ = "invite_instances"
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    uid: Mapped[str] = mapped_column(String(255), index=True)
    organizer: Mapped[str | None] = mapped_column(String(320), nullable=True, index=True)
    recurrence_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    latest_record_id: Mapped[str] = mapped_column(ForeignKey("invite_records.id"))
    current_status: Mapped[str] = mapped_column(String(20), default="pending")
    start_utc: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    end_utc: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    __table_args__ = (UniqueConstraint("uid", "organizer", "recurrence_id", name="uq_invite_instance"),)


class CalendarRow(Base):
    __tablename__ = "calendars"
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    provider: Mapped[str] = mapped_column(String(50), default="radicale")
    name: Mapped[str] = mapped_column(String(255))
    href: Mapped[str] = mapped_column(String(2048), unique=True)
    url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    etag: Mapped[str | None] = mapped_column(String(255), nullable=True)
    color: Mapped[str | None] = mapped_column(String(50), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class EventRow(Base):
    __tablename__ = "events"
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    calendar_id: Mapped[str | None] = mapped_column(ForeignKey("calendars.id"), nullable=True, index=True)
    uid: Mapped[str] = mapped_column(String(255), index=True)
    href: Mapped[str | None] = mapped_column(String(2048), nullable=True, unique=True)
    etag: Mapped[str | None] = mapped_column(String(255), nullable=True)
    title: Mapped[str] = mapped_column(Text)
    start_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    end_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    timezone_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="confirmed")
    sequence: Mapped[int] = mapped_column(Integer, default=0)
    organizer: Mapped[str | None] = mapped_column(String(320), nullable=True)
    recurrence_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    raw_ics: Mapped[str | None] = mapped_column(Text, nullable=True)
    deleted: Mapped[bool] = mapped_column(Boolean, default=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    attendees: Mapped[list[EventAttendeeRow]] = relationship(back_populates="event", cascade="all, delete-orphan")

    __table_args__ = (UniqueConstraint("uid", "recurrence_id", name="uq_event_uid_recurrence"),)


class EventAttendeeRow(Base):
    __tablename__ = "event_attendees"
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    event_id: Mapped[str] = mapped_column(ForeignKey("events.id"), index=True)
    email: Mapped[str] = mapped_column(String(320), index=True)
    common_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    partstat: Mapped[str | None] = mapped_column(String(50), nullable=True)
    role: Mapped[str | None] = mapped_column(String(50), nullable=True)
    rsvp: Mapped[bool | None] = mapped_column(Boolean, nullable=True)

    event: Mapped[EventRow] = relationship(back_populates="attendees")


class SyncStateRow(Base):
    __tablename__ = "sync_state"
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    scope: Mapped[str] = mapped_column(String(50), index=True)
    remote_key: Mapped[str] = mapped_column(String(255), index=True)
    cursor: Mapped[str | None] = mapped_column(String(255), nullable=True)
    last_success_utc: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    last_error_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    details_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)

    __table_args__ = (UniqueConstraint("scope", "remote_key", name="uq_sync_state_scope_remote_key"),)


class SettingRow(Base):
    __tablename__ = "settings"
    key: Mapped[str] = mapped_column(String(255), primary_key=True)
    value_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
