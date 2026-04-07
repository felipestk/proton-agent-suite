from __future__ import annotations

from pathlib import Path
import sys

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from proton_agent_suite.storage.db import create_session_factory, create_sqlite_engine


@pytest.fixture()
def session_factory(tmp_path: Path):
    engine = create_sqlite_engine(tmp_path / "test.sqlite3")
    return create_session_factory(engine)


@pytest.fixture()
def fixtures_dir() -> Path:
    return REPO_ROOT / "tests" / "fixtures"
