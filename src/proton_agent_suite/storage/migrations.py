from __future__ import annotations

from sqlalchemy.engine import Engine

from proton_agent_suite.storage.schema import Base


def migrate(engine: Engine) -> None:
    Base.metadata.create_all(engine)
