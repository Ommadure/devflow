"""Typed dependency aliases, so routes read `session: SessionDep` instead of Depends(...)."""

from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.errors import RateLimitedError
from app.core.pagination import PageParams, page_params
from app.core.passwords import PasswordHasher, get_password_hasher
from app.core.rate_limit import RateLimiter, RedisRateLimiter, Rule
from app.core.redis import get_redis
from app.core.security import CurrentUser, get_current_user
from app.db.session import get_session
from app.services.ai.embeddings import EmbeddingProvider, get_embedding_provider
from app.services.auth import AuthService
from app.services.notes import NoteService
from app.services.pomodoro import PomodoroService
from app.services.search import SearchService
from app.services.snippets import SnippetService
from app.workers.dispatch import JobDispatcher, get_dispatcher


def get_rate_limiter() -> RateLimiter:
    return RedisRateLimiter(get_redis())


SessionDep = Annotated[AsyncSession, Depends(get_session)]
SettingsDep = Annotated[Settings, Depends(get_settings)]
CurrentUserDep = Annotated[CurrentUser, Depends(get_current_user)]
RateLimiterDep = Annotated[RateLimiter, Depends(get_rate_limiter)]
HasherDep = Annotated[PasswordHasher, Depends(get_password_hasher)]


def get_auth_service(session: SessionDep, hasher: HasherDep, settings: SettingsDep) -> AuthService:
    return AuthService(session, hasher, settings)


AuthServiceDep = Annotated[AuthService, Depends(get_auth_service)]


def client_ip(request: Request) -> str:
    # Behind Caddy/Vercel, uvicorn's --proxy-headers puts the real client here.
    return request.client.host if request.client else "unknown"


async def enforce(limiter: RateLimiter, key: str, rule: Rule) -> None:
    decision = await limiter.hit(key, rule)
    if not decision.allowed:
        raise RateLimitedError(decision.retry_after)


# ---- resource services: always built for the signed-in user ----

DispatcherDep = Annotated[JobDispatcher, Depends(get_dispatcher)]
EmbeddingsDep = Annotated[EmbeddingProvider, Depends(get_embedding_provider)]


def get_snippet_service(
    session: SessionDep, current: CurrentUserDep, dispatcher: DispatcherDep, provider: EmbeddingsDep
) -> SnippetService:
    return SnippetService(session, current.id, dispatcher, provider.model_name)


def get_search_service(
    session: SessionDep, current: CurrentUserDep, provider: EmbeddingsDep, settings: SettingsDep
) -> SearchService:
    return SearchService(session, current.id, provider, get_redis(), settings)


def get_note_service(session: SessionDep, current: CurrentUserDep) -> NoteService:
    return NoteService(session, current.id)


def get_pomodoro_service(session: SessionDep, current: CurrentUserDep) -> PomodoroService:
    return PomodoroService(session, current.id)


SnippetServiceDep = Annotated[SnippetService, Depends(get_snippet_service)]
SearchServiceDep = Annotated[SearchService, Depends(get_search_service)]
NoteServiceDep = Annotated[NoteService, Depends(get_note_service)]
PomodoroServiceDep = Annotated[PomodoroService, Depends(get_pomodoro_service)]
PageParamsDep = Annotated[PageParams, Depends(page_params)]
