from typing import Annotated

from fastapi import APIRouter, Query

from app.api.deps import PomodoroServiceDep
from app.schemas.pomodoro import DashboardSummary
from app.services.pomodoro import parse_timezone

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/summary", responses={422: {"description": "Unknown timezone"}})
async def summary(
    pomodoro: PomodoroServiceDep,
    tz: Annotated[str, Query(max_length=64, description="IANA name, e.g. Asia/Kolkata")] = (
        "Asia/Kolkata"
    ),
) -> DashboardSummary:
    """Counts for the dashboard tiles; "today" means since midnight in `tz`."""
    return await pomodoro.summary(parse_timezone(tz))
