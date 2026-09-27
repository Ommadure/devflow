from fastapi import APIRouter

from app.api.v1.routes import auth, dashboard, me, notes, pomodoro, snippets

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth.router)
api_router.include_router(me.router)
api_router.include_router(snippets.router)
api_router.include_router(notes.router)
api_router.include_router(pomodoro.router)
api_router.include_router(dashboard.router)
