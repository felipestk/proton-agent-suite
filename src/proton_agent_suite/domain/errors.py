from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from proton_agent_suite.domain.enums import ErrorCode


@dataclass(slots=True)
class ProtonAgentError(Exception):
    code: ErrorCode
    message: str
    details: dict[str, Any] = field(default_factory=dict)
    exit_code: int = 1

    def __str__(self) -> str:
        return f"{self.code.value}: {self.message}"


ERROR_EXIT_CODES: dict[ErrorCode, int] = {
    ErrorCode.CONFIG_INVALID: 2,
    ErrorCode.SECRET_FILE_PERMISSIONS_INSECURE: 3,
    ErrorCode.SQLITE_UNAVAILABLE: 4,
    ErrorCode.BRIDGE_NOT_RUNNING: 10,
    ErrorCode.BRIDGE_UNREACHABLE: 11,
    ErrorCode.BRIDGE_AUTH_FAILED: 12,
    ErrorCode.BRIDGE_SMTP_UNAVAILABLE: 13,
    ErrorCode.CALENDAR_UNREACHABLE: 20,
    ErrorCode.CALENDAR_AUTH_FAILED: 21,
    ErrorCode.CALENDAR_DISCOVERY_FAILED: 22,
    ErrorCode.MESSAGE_NOT_FOUND: 30,
    ErrorCode.ATTACHMENT_NOT_FOUND: 31,
    ErrorCode.INVITE_NOT_FOUND: 32,
    ErrorCode.EVENT_NOT_FOUND: 33,
    ErrorCode.VALIDATION_ERROR: 40,
    ErrorCode.NOT_IMPLEMENTED_SAFE_FALLBACK: 50,
}


def make_error(code: ErrorCode, message: str, details: dict[str, Any] | None = None) -> ProtonAgentError:
    return ProtonAgentError(
        code=code,
        message=message,
        details=details or {},
        exit_code=ERROR_EXIT_CODES.get(code, 1),
    )
