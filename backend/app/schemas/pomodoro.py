from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class PomodoroSessionCreate(BaseModel):
    """ "A focus session just finished." The server stamps the time; the client only says
    how long it was (bounded, so a buggy or hostile client can't log a 10-year session)."""

    duration_seconds: int = Field(ge=60, le=4 * 60 * 60)


class PomodoroSessionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    completed_at: datetime
    duration_seconds: int


class DashboardSummary(BaseModel):
    snippets: int
    notes: int
    focus_sessions: int
    focus_sessions_today: int = Field(description="Since midnight in the requested timezone.")
