from __future__ import annotations

import os
import stat
from pathlib import Path


def permissions_are_insecure(path: Path) -> bool:
    if not path.exists():
        return False
    mode = stat.S_IMODE(path.stat().st_mode)
    return bool(mode & (stat.S_IRWXG | stat.S_IRWXO))


def describe_permissions(path: Path) -> str:
    if not path.exists():
        return "missing"
    return oct(stat.S_IMODE(os.stat(path).st_mode))
