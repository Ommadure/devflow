from datetime import UTC, datetime, timedelta

import httpx
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models import PomodoroSession
from tests.integration.conftest import Headers

SESSIONS = "/api/v1/pomodoro/sessions"
SUMMARY = "/api/v1/dashboard/summary"


async def test_record_and_list_sessions(api: httpx.AsyncClient, alice: Headers) -> None:
    before = datetime.now(UTC)
    response = await api.post(SESSIONS, json={"duration_seconds": 1500}, headers=alice)
    assert response.status_code == 201
    session = response.json()
    assert session["duration_seconds"] == 1500
    assert datetime.fromisoformat(session["completed_at"]) >= before - timedelta(seconds=1)

    listed = (await api.get(SESSIONS, headers=alice)).json()
    assert [item["id"] for item in listed["items"]] == [session["id"]]


async def test_the_client_cannot_choose_when_or_how_long(
    api: httpx.AsyncClient, alice: Headers
) -> None:
    too_short = await api.post(SESSIONS, json={"duration_seconds": 5}, headers=alice)
    too_long = await api.post(SESSIONS, json={"duration_seconds": 10**6}, headers=alice)
    assert too_short.status_code == too_long.status_code == 422
    backdated = await api.post(
        SESSIONS,
        json={"duration_seconds": 1500, "completed_at": "2020-01-01T00:00:00Z"},
        headers=alice,
    )
    assert backdated.json()["completed_at"].startswith(str(datetime.now(UTC).year))


async def test_dashboard_summary_counts_today_in_the_users_timezone(
    api: httpx.AsyncClient,
    alice: Headers,
    sessionmaker: async_sessionmaker[AsyncSession],
) -> None:
    await api.post("/api/v1/snippets", json={"title": "t", "code": "c"}, headers=alice)
    await api.post("/api/v1/notes", json={}, headers=alice)
    await api.post(SESSIONS, json={"duration_seconds": 1500}, headers=alice)
    old = (await api.post(SESSIONS, json={"duration_seconds": 1500}, headers=alice)).json()
    async with sessionmaker() as session:
        await session.execute(
            update(PomodoroSession)
            .where(PomodoroSession.id == old["id"])
            .values(completed_at=datetime.now(UTC) - timedelta(days=2))
        )
        await session.commit()

    summary = (await api.get(SUMMARY, params={"tz": "Asia/Kolkata"}, headers=alice)).json()
    assert summary == {"snippets": 1, "notes": 1, "focus_sessions": 2, "focus_sessions_today": 1}


async def test_unknown_timezone_is_422(api: httpx.AsyncClient, alice: Headers) -> None:
    response = await api.get(SUMMARY, params={"tz": "Mars/Olympus"}, headers=alice)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "INVALID_TIMEZONE"
