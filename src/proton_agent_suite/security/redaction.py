from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

_SECRET_PATTERNS = [
    re.compile(r"(?i)(password=)([^\s]+)"),
    re.compile(r"(?i)(authorization: )(.*)"),
]


def redact_text(text: str) -> str:
    redacted = text
    for pattern in _SECRET_PATTERNS:
        redacted = pattern.sub(lambda m: f"{m.group(1)}***REDACTED***", redacted)
    return redacted


def redact_mapping(data: Mapping[str, Any]) -> dict[str, Any]:
    redacted: dict[str, Any] = {}
    for key, value in data.items():
        if "password" in key.lower() or "secret" in key.lower():
            redacted[key] = "***REDACTED***"
        elif isinstance(value, Mapping):
            redacted[key] = redact_mapping(value)
        else:
            redacted[key] = value
    return redacted
