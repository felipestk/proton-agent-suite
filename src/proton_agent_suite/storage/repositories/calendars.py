from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from proton_agent_suite.domain.enums import ErrorCode
from proton_agent_suite.domain.errors import make_error
from proton_agent_suite.storage.schema import CalendarRow
from proton_agent_suite.utils.ids import stable_ref


class CalendarsRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def upsert(self, *, provider: str, name: str, href: str, url: str | None, etag: str | None, color: str | None, description: str | None, is_default: bool) -> CalendarRow:
        row = self.session.scalar(select(CalendarRow).where(CalendarRow.href == href))
        if row is None:
            row = CalendarRow(id=stable_ref("cal", href), provider=provider, href=href, name=name)
            self.session.add(row)
        row.name = name
        row.url = url
        row.etag = etag
        row.color = color
        row.description = description
        row.is_default = is_default
        self.session.flush()
        return row

    def list_all(self) -> list[CalendarRow]:
        return list(self.session.scalars(select(CalendarRow).order_by(CalendarRow.name.asc())))

    def get(self, calendar_ref: str) -> CalendarRow:
        row = self.session.scalar(select(CalendarRow).where(CalendarRow.id == calendar_ref))
        if row is None:
            raise make_error(ErrorCode.CALENDAR_NOT_FOUND, "Calendar not found", {"calendar_ref": calendar_ref})
        return row

    def get_default(self) -> CalendarRow | None:
        return self.session.scalar(select(CalendarRow).where(CalendarRow.is_default.is_(True)))
