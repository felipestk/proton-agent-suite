from __future__ import annotations

from collections.abc import Callable
from time import sleep
from typing import TypeVar

T = TypeVar("T")


def retry(operation: Callable[[], T], retries: int = 2, delay_seconds: float = 0.25) -> T:
    last_error: Exception | None = None
    for attempt in range(retries + 1):
        try:
            return operation()
        except Exception as exc:  # pragma: no cover - trivial helper
            last_error = exc
            if attempt >= retries:
                raise
            sleep(delay_seconds)
    assert last_error is not None
    raise last_error
