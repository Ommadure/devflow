"""Data access for completed focus sessions, always scoped to one user (ADR 0002)."""

from datetime import date, datetime
from uuid import UUID

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.pagination import PageParams, keyset
from app.models import PomodoroSession


async def add(session: AsyncSession, user_id: UUID, *, duration_seconds: int) -> PomodoroSession:
    record = PomodoroSession(user_id=user_id, duration_seconds=duration_seconds)
    session.add(record)
    await session.flush()
    return record


async def list_page(
    session: AsyncSession, user_id: UUID, params: PageParams
) -> list[PomodoroSession]:
    stmt = select(PomodoroSession).where(PomodoroSession.user_id == user_id)
    result = await session.scalars(
        keyset(stmt, PomodoroSession.completed_at, PomodoroSession.id, params)
    )
    return list(result)


async def count(session: AsyncSession, user_id: UUID, *, since: datetime | None = None) -> int:
    stmt = (
        select(func.count()).select_from(PomodoroSession).where(PomodoroSession.user_id == user_id)
    )
    if since is not None:
        stmt = stmt.where(PomodoroSession.completed_at >= since)
    return await session.scalar(stmt) or 0


# ---- statistics (spec §11.7), computed in SQL in the user's timezone ----

_DAILY = text(
    """
    WITH days AS (
        SELECT generate_series(
            (CAST(:now AS timestamptz) AT TIME ZONE :tz)::date - (:days - 1),
            (CAST(:now AS timestamptz) AT TIME ZONE :tz)::date,
            interval '1 day'
        )::date AS day
    ),
    per_day AS (
        SELECT (completed_at AT TIME ZONE :tz)::date AS day,
               count(*) AS sessions,
               sum(duration_seconds) AS seconds
        FROM pomodoro_sessions
        WHERE user_id = :user_id
          AND completed_at >= CAST(:now AS timestamptz) - make_interval(days => :days + 1)
        GROUP BY 1
    )
    SELECT days.day, coalesce(per_day.sessions, 0), coalesce(per_day.seconds, 0)
    FROM days LEFT JOIN per_day USING (day)
    ORDER BY days.day
    """
)

# Gaps and islands: for consecutive days, (day - row_number) is constant, so grouping by it
# yields one row per unbroken run. "Current" is the run that reaches today or yesterday —
# a streak isn't broken just because today's session hasn't happened yet.
_STREAKS = text(
    """
    WITH active AS (
        SELECT DISTINCT (completed_at AT TIME ZONE :tz)::date AS day
        FROM pomodoro_sessions WHERE user_id = :user_id
    ),
    runs AS (
        SELECT count(*) AS length, max(day) AS last_day
        FROM (SELECT day, day - CAST(row_number() OVER (ORDER BY day) AS int) AS run
              FROM active) numbered
        GROUP BY run
    )
    SELECT coalesce(max(length), 0),
           coalesce(max(length) FILTER (
               WHERE last_day >= (CAST(:now AS timestamptz) AT TIME ZONE :tz)::date - 1
           ), 0)
    FROM runs
    """
)


async def daily_totals(
    session: AsyncSession, user_id: UUID, *, days: int, tz: str, now: datetime
) -> list[tuple[date, int, int]]:
    """(day, sessions, seconds) for each of the last `days` days in `tz`, zeros included."""
    rows = await session.execute(_DAILY, {"user_id": user_id, "days": days, "tz": tz, "now": now})
    return [(day, int(sessions), int(seconds)) for day, sessions, seconds in rows]


async def streaks(
    session: AsyncSession, user_id: UUID, *, tz: str, now: datetime
) -> tuple[int, int]:
    """(best, current) runs of consecutive days with at least one session."""
    best, current = (
        await session.execute(_STREAKS, {"user_id": user_id, "tz": tz, "now": now})
    ).one()
    return int(best), int(current)
