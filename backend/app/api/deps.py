"""Typed dependency aliases, so routes read `session: SessionDep` instead of Depends(...)."""

from typing import Annotated

import httpx
from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import Settings, get_settings
from app.core.errors import RateLimitedError
from app.core.pagination import PageParams, page_params
from app.core.passwords import PasswordHasher, get_password_hasher
from app.core.rate_limit import RateLimiter, RedisRateLimiter, Rule, SlidingWindowRateLimiter
from app.core.redis import get_redis
from app.core.security import CurrentUser, get_current_user
from app.db.session import get_session, get_sessionmaker
from app.services.ai.embeddings import EmbeddingProvider, get_embedding_provider
from app.services.ai.llm.base import LLMProvider
from app.services.ai.llm.factory import get_llm_provider
from app.services.ai.usage import AiUsageService
from app.services.api_tester.proxy import proxy_http_client
from app.services.api_tester.ssrf import Resolver, system_resolver
from app.services.auth import AuthService
from app.services.github.client import GitHubClient, build_github_client
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


def get_note_service(
    session: SessionDep, current: CurrentUserDep, dispatcher: DispatcherDep
) -> NoteService:
    return NoteService(session, current.id, dispatcher)


def get_pomodoro_service(session: SessionDep, current: CurrentUserDep) -> PomodoroService:
    return PomodoroService(session, current.id)


SnippetServiceDep = Annotated[SnippetService, Depends(get_snippet_service)]
SearchServiceDep = Annotated[SearchService, Depends(get_search_service)]
NoteServiceDep = Annotated[NoteService, Depends(get_note_service)]
PomodoroServiceDep = Annotated[PomodoroService, Depends(get_pomodoro_service)]
PageParamsDep = Annotated[PageParams, Depends(page_params)]


# ---- rate limits (spec §8.8) and the AI features ----

GENERAL_LIMIT = Rule(limit=120, window_seconds=60)
AI_LIMIT = Rule(limit=10, window_seconds=60)


def get_sliding_limiter() -> RateLimiter:
    return SlidingWindowRateLimiter(get_redis())


SlidingLimiterDep = Annotated[RateLimiter, Depends(get_sliding_limiter)]
LLMDep = Annotated[LLMProvider, Depends(get_llm_provider)]
SessionFactoryDep = Annotated[async_sessionmaker[AsyncSession], Depends(get_sessionmaker)]


async def general_rate_limit(current: CurrentUserDep, limiter: SlidingLimiterDep) -> None:
    """120 requests a minute per user, on every authenticated route."""
    await enforce(limiter, f"api:user:{current.id}", GENERAL_LIMIT)


async def ai_rate_limit(current: CurrentUserDep, limiter: SlidingLimiterDep) -> None:
    """10 AI requests a minute per user, on top of the daily quota."""
    await enforce(limiter, f"ai:user:{current.id}", AI_LIMIT)


def get_ai_usage(
    sessions: SessionFactoryDep, current: CurrentUserDep, settings: SettingsDep
) -> AiUsageService:
    return AiUsageService(sessions, current.id, settings)


AiUsageDep = Annotated[AiUsageService, Depends(get_ai_usage)]


# ---- API tester ----

PROXY_LIMIT = Rule(limit=30, window_seconds=60)


def get_resolver() -> Resolver:
    """A dependency, so tests can answer DNS lookups without the network."""
    return system_resolver


async def proxy_rate_limit(current: CurrentUserDep, limiter: SlidingLimiterDep) -> None:
    """30 proxied requests a minute per user: the tester must not become a load generator."""
    await enforce(limiter, f"proxy:user:{current.id}", PROXY_LIMIT)


ProxyClientDep = Annotated[httpx.AsyncClient, Depends(proxy_http_client)]
ResolverDep = Annotated[Resolver, Depends(get_resolver)]


# ---- GitHub ----


def get_github(settings: SettingsDep) -> GitHubClient:
    return build_github_client(settings, get_redis())


GitHubDep = Annotated[GitHubClient, Depends(get_github)]
