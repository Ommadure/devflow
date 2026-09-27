"""Pomodoro stats in SQL: days in the user's timezone, streaks across gaps and midnights."""

import uuid
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import httpx
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models import PomodoroSession
from app.services.pomodoro import PomodoroService
from tests.integration.conftest import Headers

Sessions = async_sessionmaker[AsyncSession]
# Sunday 27 Sept 2026, 15:30 in India: "today" there is the 27th.
NOW = datetime(2026, 9, 27, 10, 0, tzinfo=UTC)
IST = ZoneInfo("Asia/Kolkata")


async def user_id(api: httpx.AsyncClient, headers: Headers) -> uuid.UUID:
    return uuid.UUID((await api.get("/api/v1/me", headers=headers)).json()["id"])


async def add(sessions: Sessions, owner: uuid.UUID, *moments: datetime, minutes: int = 25) -> None:
    async with sessions() as session:
        session.add_all(
            PomodoroSession(user_id=owner, completed_at=moment, duration_seconds=minutes * 60)
            for moment in moments
        )
        await session.commit()


def ist_day(days_ago: int, hour: int = 12) -> datetime:
    local = datetime(2026, 9, 27, hour, 0, tzinfo=IST) - timedelta(days=days_ago)
    return local.astimezone(UTC)


async def stats(sessions: Sessions, owner: uuid.UUID, range_: str = "7d", tz: ZoneInfo = IST):  # type: ignore[no-untyped-def]
    async with sessions() as session:
        return await PomodoroService(session, owner).stats(range_, tz, now=NOW)  # type: ignore[arg-type]


async def test_daily_minutes_include_empty_days(
    api: httpx.AsyncClient, alice: Headers, sessionmaker: Sessions
) -> None:
    owner = await user_id(api, alice)
    await add(sessionmaker, owner, ist_day(0), ist_day(0, 18), ist_day(2))

    result = await stats(sessionmaker, owner)

    assert [d.date.isoformat() for d in result.days] == [f"2026-09-{day}" for day in range(21, 28)]
    assert [(d.sessions, d.minutes) for d in result.days][-3:] == [(1, 25), (0, 0), (2, 50)]
    assert (result.total_sessions, result.total_minutes) == (3, 75)
    assert len((await stats(sessionmaker, owner, "30d")).days) == 30


async def test_streaks_across_a_gap(
    api: httpx.AsyncClient, alice: Headers, sessionmaker: Sessions
) -> None:
    owner = await user_id(api, alice)
    # 10, 9, 8, 7 days ago (a run of 4), a gap, then 2, 1, 0 days ago (a run of 3).
    await add(sessionmaker, owner, *[ist_day(n) for n in (10, 9, 8, 7, 2, 1, 0)])
    result = await stats(sessionmaker, owner)
    assert (result.best_streak, result.current_streak) == (4, 3)


async def test_several_sessions_in_a_day_count_once_for_the_streak(
    api: httpx.AsyncClient, alice: Headers, sessionmaker: Sessions
) -> None:
    owner = await user_id(api, alice)
    await add(sessionmaker, owner, ist_day(1, 9), ist_day(1, 13), ist_day(1, 20), ist_day(0))
    assert (await stats(sessionmaker, owner)).current_streak == 2


async def test_a_streak_survives_until_today_is_over(
    api: httpx.AsyncClient, alice: Headers, sessionmaker: Sessions
) -> None:
    owner = await user_id(api, alice)
    await add(sessionmaker, owner, ist_day(2), ist_day(1))  # nothing yet today
    assert (await stats(sessionmaker, owner)).current_streak == 2
    await add(sessionmaker, owner, ist_day(4))
    other = await user_id(api, alice)
    assert (await stats(sessionmaker, other)).best_streak == 2


async def test_a_missed_day_breaks_the_current_streak(
    api: httpx.AsyncClient, alice: Headers, sessionmaker: Sessions
) -> None:
    owner = await user_id(api, alice)
    await add(sessionmaker, owner, ist_day(4), ist_day(3), ist_day(2))  # yesterday missed
    result = await stats(sessionmaker, owner)
    assert (result.best_streak, result.current_streak) == (3, 0)


async def test_the_same_instant_is_a_different_day_in_another_timezone(
    api: httpx.AsyncClient, alice: Headers, sessionmaker: Sessions
) -> None:
    owner = await user_id(api, alice)
    # 20:00 UTC on the 26th = 01:30 on the 27th in India, 16:00 on the 26th in New York.
    await add(sessionmaker, owner, datetime(2026, 9, 26, 20, 0, tzinfo=UTC))

    india = await stats(sessionmaker, owner, tz=IST)
    new_york = await stats(sessionmaker, owner, tz=ZoneInfo("America/New_York"))

    assert (india.days[-1].date.day, india.days[-1].sessions) == (27, 1)
    assert (new_york.days[-1].date.day, new_york.days[-1].sessions) == (27, 0)
    assert (new_york.days[-2].date.day, new_york.days[-2].sessions) == (26, 1)


async def test_stats_are_per_user(
    api: httpx.AsyncClient, alice: Headers, bob: Headers, sessionmaker: Sessions
) -> None:
    await add(sessionmaker, await user_id(api, alice), ist_day(0), ist_day(1))
    result = await stats(sessionmaker, await user_id(api, bob))
    assert (result.total_sessions, result.best_streak, result.current_streak) == (0, 0, 0)


async def test_the_route(api: httpx.AsyncClient, alice: Headers) -> None:
    await api.post("/api/v1/pomodoro/sessions", json={"duration_seconds": 1500}, headers=alice)
    response = await api.get(
        "/api/v1/pomodoro/stats", params={"range": "30d", "tz": "Europe/London"}, headers=alice
    )
    body = response.json()
    assert (body["range"], body["timezone"], len(body["days"])) == ("30d", "Europe/London", 30)
    assert (body["total_sessions"], body["current_streak"]) == (1, 1)
    bad = await api.get("/api/v1/pomodoro/stats", params={"range": "1y"}, headers=alice)
    assert bad.status_code == 422
