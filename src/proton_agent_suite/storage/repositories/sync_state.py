from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from proton_agent_suite.storage.schema import SyncStateRow
from proton_agent_suite.utils.ids import stable_ref


class SyncStateRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def record_success(self, scope: str, remote_key: str, details: dict[str, object]) -> SyncStateRow:
        row = self.session.scalar(
            select(SyncStateRow).where(
                SyncStateRow.scope == scope,
                SyncStateRow.remote_key == remote_key,
            )
        )
        if row is None:
            row = SyncStateRow(id=stable_ref("syn", scope, remote_key), scope=scope, remote_key=remote_key)
            self.session.add(row)
        row.last_success_utc = datetime.now(UTC)
        row.last_error_code = None
        row.details_json = details
        self.session.flush()
        return row

    def record_error(
        self,
        scope: str,
        remote_key: str,
        error_code: str,
        details: dict[str, object],
    ) -> SyncStateRow:
        row = self.session.scalar(
            select(SyncStateRow).where(
                SyncStateRow.scope == scope,
                SyncStateRow.remote_key == remote_key,
            )
        )
        if row is None:
            row = SyncStateRow(id=stable_ref("syn", scope, remote_key), scope=scope, remote_key=remote_key)
            self.session.add(row)
        row.last_error_code = error_code
        row.last_error_at = datetime.now(UTC)
        row.details_json = details
        self.session.flush()
        return row

    def list_all(self) -> list[SyncStateRow]:
        stmt = select(SyncStateRow).order_by(SyncStateRow.scope.asc(), SyncStateRow.remote_key.asc())
        return list(self.session.scalars(stmt))
