from __future__ import annotations

from datetime import UTC, datetime, timedelta
import re

_DURATION_RE = re.compile(r"^(?P<value>\d+)(?P<unit>[smhdw])$")


def utc_now() -> datetime:
    return datetime.now(UTC)


def ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def parse_timestamp(value: str) -> datetime:
    normalized = value.replace("Z", "+00:00")
    dt = datetime.fromisoformat(normalized)
    return ensure_utc(dt)


def parse_since(value: str) -> datetime:
    match = _DURATION_RE.match(value.strip())
    if match:
        amount = int(match.group("value"))
        unit = match.group("unit")
        delta = {
            "s": timedelta(seconds=amount),
            "m": timedelta(minutes=amount),
            "h": timedelta(hours=amount),
            "d": timedelta(days=amount),
            "w": timedelta(weeks=amount),
        }[unit]
        return utc_now() - delta
    return parse_timestamp(value)


def to_iso_z(value: datetime | None) -> str | None:
    if value is None:
        return None
    return ensure_utc(value).isoformat().replace("+00:00", "Z")
