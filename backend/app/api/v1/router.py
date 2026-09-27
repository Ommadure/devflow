from fastapi import APIRouter, Depends

from app.api.deps import general_rate_limit
from app.api.v1.routes import (
    ai,
    api_tester,
    auth,
    dashboard,
    github,
    me,
    notes,
    pomodoro,
    snippets,
)

api_router = APIRouter(prefix="/api/v1")
# Auth has its own, stricter limits (per IP and per email) and no user yet.
api_router.include_router(auth.router)

# Every signed-in route shares the general limit: 120 requests a minute per user.
protected = APIRouter(dependencies=[Depends(general_rate_limit)])
protected.include_router(me.router)
protected.include_router(ai.router)  # before snippets/notes: /notes/ask vs /notes/{id}
protected.include_router(snippets.router)
protected.include_router(notes.router)
protected.include_router(pomodoro.router)
protected.include_router(dashboard.router)
protected.include_router(api_tester.router)
protected.include_router(github.router)
api_router.include_router(protected)
