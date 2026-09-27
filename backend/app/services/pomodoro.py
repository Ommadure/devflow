"""Focus sessions and the dashboard's counts."""

from datetime import UTC, datetime
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ValidationFailedError
from app.core.pagination import Page, PageParams, paginate
from app.models import PomodoroSession
from app.repositories import notes, pomodoro_sessions, snippets
from app.schemas.pomodoro import DashboardSummary, PomodoroSessionOut


def parse_timezone(name: str) -> ZoneInfo:
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError) as exc:
        raise ValidationFailedError(
            f"Unknown timezone: {name[:64]}", code="INVALID_TIMEZONE"
        ) from exc


def start_of_today(tz: ZoneInfo, now: datetime | None = None) -> datetime:
    """Midnight today in `tz`, as an aware datetime. "Today" is the user's day, not UTC's:
    at 02:00 in India it is still yesterday in UTC."""
    local = (now or datetime.now(UTC)).astimezone(tz)
    return local.replace(hour=0, minute=0, second=0, microsecond=0)


class PomodoroService:
    def __init__(self, session: AsyncSession, user_id: UUID) -> None:
        self._session = session
        self._user_id = user_id

    async def record(self, duration_seconds: int) -> PomodoroSession:
        record = await pomodoro_sessions.add(
            self._session, self._user_id, duration_seconds=duration_seconds
        )
        await self._session.commit()
        return record

    async def page(self, params: PageParams) -> Page[PomodoroSessionOut]:
        rows = await pomodoro_sessions.list_page(self._session, self._user_id, params)
        items, next_cursor = paginate(rows, params, "completed_at")
        return Page(
            items=[PomodoroSessionOut.model_validate(r) for r in items], next_cursor=next_cursor
        )

    async def summary(self, tz: ZoneInfo) -> DashboardSummary:
        # Four small indexed counts; no need to fold them into one clever query.
        return DashboardSummary(
            snippets=await snippets.count(self._session, self._user_id),
            notes=await notes.count(self._session, self._user_id),
            focus_sessions=await pomodoro_sessions.count(self._session, self._user_id),
            focus_sessions_today=await pomodoro_sessions.count(
                self._session, self._user_id, since=start_of_today(tz)
            ),
        )
