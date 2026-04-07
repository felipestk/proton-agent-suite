from __future__ import annotations

from proton_agent_suite.domain.models import CalendarInfo
from proton_agent_suite.providers.radicale_calendar.discovery import DiscoveredCalendar
from proton_agent_suite.utils.ids import stable_ref


class RadicaleMapper:
    @staticmethod
    def calendar_info(item: DiscoveredCalendar, default_name: str | None) -> CalendarInfo:
        return CalendarInfo(
            ref=stable_ref("cal", item.href),
            name=item.display_name,
            href=item.href,
            description=item.description,
            etag=item.etag,
            color=item.color,
            is_default=default_name is not None and item.display_name == default_name,
        )
