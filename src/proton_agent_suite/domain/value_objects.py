from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, HttpUrl, model_validator


class BridgeSettings(BaseModel):
    host: str = "127.0.0.1"
    imap_port: int = 1143
    smtp_port: int = 1025
    username: str | None = None
    password: str | None = None
    label_prefix: str = "Labels"
    allow_insecure_localhost: bool = True


class RadicaleSettings(BaseModel):
    base_url: str | None = None
    username: str | None = None
    password: str | None = None
    default_calendar: str | None = None
    allow_insecure: bool = False

    @model_validator(mode="after")
    def validate_url(self) -> "RadicaleSettings":
        if self.base_url is None:
            return self
        if not self.base_url.startswith(("http://", "https://")):
            raise ValueError("Radicale base URL must start with http:// or https://")
        return self


class AppSettings(BaseModel):
    profile: str = "default"
    db_path: Path = Path("./data/proton-agent.sqlite3")
    credentials_directory: Path | None = None
    bridge: BridgeSettings = Field(default_factory=BridgeSettings)
    radicale: RadicaleSettings = Field(default_factory=RadicaleSettings)
    ics_public_base_url: str | None = None

    def redacted_dict(self) -> dict[str, Any]:
        data = self.model_dump(mode="python")
        data["db_path"] = str(data["db_path"])
        if data.get("credentials_directory") is not None:
            data["credentials_directory"] = str(data["credentials_directory"])
        if data["bridge"].get("password"):
            data["bridge"]["password"] = "***REDACTED***"
        if data["radicale"].get("password"):
            data["radicale"]["password"] = "***REDACTED***"
        return data


class MailSendRequest(BaseModel):
    to_addresses: list[str]
    cc_addresses: list[str] = Field(default_factory=list)
    bcc_addresses: list[str] = Field(default_factory=list)
    subject: str
    body_text: str
    in_reply_to: str | None = None
    references: list[str] = Field(default_factory=list)
    headers: dict[str, str] = Field(default_factory=dict)
    attachments: list["MailAttachment"] = Field(default_factory=list)


class MailAttachment(BaseModel):
    filename: str
    content_type: str = "application/octet-stream"
    content: bytes
    disposition: str = "attachment"
    content_id: str | None = None
    params: dict[str, str] = Field(default_factory=dict)
