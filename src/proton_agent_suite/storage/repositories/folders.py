from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from proton_agent_suite.domain.enums import ErrorCode, MailboxKind
from proton_agent_suite.domain.errors import make_error
from proton_agent_suite.storage.schema import FolderRow
from proton_agent_suite.utils.ids import stable_ref


class FoldersRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def upsert(self, name: str, kind: MailboxKind = MailboxKind.FOLDER) -> FolderRow:
        row = self.session.scalar(select(FolderRow).where(FolderRow.remote_name == name))
        if row is None:
            row = FolderRow(
                id=stable_ref("fld", name),
                remote_name=name,
                display_name=name,
                kind=kind.value,
            )
            self.session.add(row)
            self.session.flush()
            return row
        row.kind = kind.value
        row.display_name = name
        return row

    def list_all(self) -> list[FolderRow]:
        return list(self.session.scalars(select(FolderRow).order_by(FolderRow.display_name.asc())))

    def get(self, name: str) -> FolderRow:
        row = self.session.scalar(select(FolderRow).where(FolderRow.remote_name == name))
        if row is None:
            raise make_error(ErrorCode.MAIL_FOLDER_NOT_FOUND, "Folder not found", {"folder": name})
        return row

    def rename(self, old_name: str, new_name: str) -> FolderRow:
        row = self.get(old_name)
        row.remote_name = new_name
        row.display_name = new_name
        self.session.flush()
        return row

    def delete(self, name: str) -> None:
        row = self.get(name)
        self.session.delete(row)
        self.session.flush()
