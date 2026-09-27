from fastapi import APIRouter, status

from app.api.deps import PageParamsDep, PomodoroServiceDep
from app.core.pagination import Page
from app.schemas.pomodoro import PomodoroSessionCreate, PomodoroSessionOut

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
