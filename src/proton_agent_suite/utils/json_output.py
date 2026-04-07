from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from proton_agent_suite.domain.errors import ProtonAgentError
from proton_agent_suite.utils.time import to_iso_z


def _default(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if is_dataclass(value):
        return asdict(value)
    if isinstance(value, datetime):
        return to_iso_z(value)
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Path):
        return str(value)
    raise TypeError(f"Object of type {type(value)!r} is not JSON serializable")


def success_payload(data: Any) -> dict[str, Any]:
    return {"ok": True, "data": data}


def error_payload(error: ProtonAgentError) -> dict[str, Any]:
    return {
        "ok": False,
        "error": {
            "code": error.code.value,
            "message": error.message,
            "details": error.details,
        },
    }


def dumps(data: Any) -> str:
    return json.dumps(data, default=_default, sort_keys=True, separators=(",", ":"))
