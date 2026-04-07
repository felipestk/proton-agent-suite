from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from proton_agent_suite.storage.schema import AccountRow
from proton_agent_suite.utils.ids import stable_ref


class AccountsRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_or_create(self, profile: str, provider: str, email_address: str | None = None) -> AccountRow:
        existing = self.session.scalar(select(AccountRow).where(AccountRow.profile == profile))
        if existing is not None:
            if email_address and existing.email_address != email_address:
                existing.email_address = email_address
            return existing
        row = AccountRow(
            id=stable_ref("acct", profile, provider),
            profile=profile,
            provider=provider,
            email_address=email_address,
        )
        self.session.add(row)
        self.session.flush()
        return row
