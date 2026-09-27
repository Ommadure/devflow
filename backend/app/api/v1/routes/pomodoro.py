from typing import Annotated, Literal

from fastapi import APIRouter, Query, status

from app.api.deps import PageParamsDep, PomodoroServiceDep
from app.core.pagination import Page
from app.schemas.pomodoro import PomodoroSessionCreate, PomodoroSessionOut, PomodoroStats
from app.services.pomodoro import parse_timezone

router = APIRouter(prefix="/pomodoro", tags=["pomodoro"])


@router.post("/sessions", status_code=status.HTTP_201_CREATED)
async def record_session(
    body: PomodoroSessionCreate, pomodoro: PomodoroServiceDep
) -> PomodoroSessionOut:
    """Record that a focus session just finished; the server stamps the time."""
    return PomodoroSessionOut.model_validate(await pomodoro.record(body.duration_seconds))


@router.get("/sessions")
async def list_sessions(
    pomodoro: PomodoroServiceDep, page: PageParamsDep
) -> Page[PomodoroSessionOut]:
    return await pomodoro.page(page)


@router.get("/stats", responses={422: {"description": "Unknown timezone"}})
async def stats(
    pomodoro: PomodoroServiceDep,
    range_: Annotated[Literal["7d", "30d"], Query(alias="range")] = "7d",
    tz: Annotated[str, Query(max_length=64, description="IANA name, e.g. Asia/Kolkata")] = (
        "Asia/Kolkata"
    ),
) -> PomodoroStats:
    """Focus minutes per day (the user's days, in `tz`), totals, and streaks."""
    return await pomodoro.stats(range_, parse_timezone(tz))
