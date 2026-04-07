from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from proton_agent_suite.storage.schema import SettingRow


class SettingsRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get(self, key: str) -> dict[str, object] | None:
        row = self.session.scalar(select(SettingRow).where(SettingRow.key == key))
        return None if row is None else row.value_json

    def set(self, key: str, value: dict[str, object]) -> None:
        row = self.session.scalar(select(SettingRow).where(SettingRow.key == key))
        if row is None:
            row = SettingRow(key=key, value_json=value)
            self.session.add(row)
        else:
            row.value_json = value
        self.session.flush()
