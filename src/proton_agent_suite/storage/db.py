from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from proton_agent_suite.domain.enums import ErrorCode
from proton_agent_suite.domain.errors import make_error
from proton_agent_suite.storage.migrations import migrate
from proton_agent_suite.utils.fs import ensure_parent_dir


def create_sqlite_engine(db_path: Path) -> Engine:
    try:
        ensure_parent_dir(db_path)
        engine = create_engine(f"sqlite+pysqlite:///{db_path}", future=True)
        return engine
    except Exception as exc:  # pragma: no cover - defensive
        raise make_error(ErrorCode.SQLITE_UNAVAILABLE, "Unable to initialize SQLite", {"reason": str(exc)}) from exc


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    migrate(engine)
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, class_=Session)
