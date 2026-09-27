"""Taskiq tasks: thin wrappers that give the jobs in services/ai/indexing.py a database
session, the embedding model, retries and logs."""

import asyncio
import uuid
from datetime import UTC, datetime

import structlog
from sqlalchemy import select
from taskiq import TaskiqEvents, TaskiqState

from app.core.config import get_settings
from app.core.logging import configure_logging, new_context
from app.core.observability import init_sentry
from app.core.redis import get_redis
from app.db.session import get_sessionmaker
from app.models import User
from app.services.ai import indexing
from app.services.ai.embeddings import check_embedding_config, get_embedding_provider
from app.services.ai.llm.factory import get_llm_provider
from app.services.ai.usage import AiUsageService
from app.services.github.client import build_github_client
from app.services.github.insights import InsightService, last_week_start
from app.workers.broker import broker

log = structlog.get_logger()

MAX_ATTEMPTS = 3


@broker.on_event(TaskiqEvents.WORKER_STARTUP)
async def _startup(_: TaskiqState) -> None:
    settings = get_settings()
    configure_logging(settings.app_env, settings.log_level)
    init_sentry(settings, component="worker")
    check_embedding_config(settings)
    # Load the model now, not on the first job, so the first save isn't slow.
    await get_embedding_provider().embed_query("warm up")
    log.info("worker.startup", model=get_embedding_provider().model_name)


def backoff_seconds(attempt: int) -> float:
    return float(2**attempt)  # 2 s, 4 s between the three attempts


@broker.task(task_name="embed_snippet")
async def embed_snippet_task(snippet_id: str) -> None:
    new_context(task="embed_snippet", snippet_id=snippet_id)
    sid = uuid.UUID(snippet_id)
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            async with get_sessionmaker()() as session:
                await indexing.embed_snippet(session, get_embedding_provider(), sid)
            return
        except Exception:
            log.warning("embedding.attempt_failed", attempt=attempt, exc_info=True)
            if attempt == MAX_ATTEMPTS:
                break
            await asyncio.sleep(backoff_seconds(attempt))
    # Out of attempts: record it, so the UI can say so and the backfill can retry later.
    log.error("embedding.failed", snippet_id=snippet_id)
    async with get_sessionmaker()() as session:
        await indexing.mark_failed(session, sid)


@broker.task(task_name="embed_note")
async def embed_note_task(note_id: str) -> None:
    new_context(task="embed_note", note_id=note_id)
    nid = uuid.UUID(note_id)
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            async with get_sessionmaker()() as session:
                await indexing.embed_note(session, get_embedding_provider(), nid)
            return
        except Exception:
            log.warning("note_index.attempt_failed", attempt=attempt, exc_info=True)
            if attempt < MAX_ATTEMPTS:
                await asyncio.sleep(backoff_seconds(attempt))
    # No "failed" state for notes: indexed_at stays behind updated_at, so the sweep retries.
    log.error("note_index.failed", note_id=note_id)


# Every 10 minutes: embed snippets left "pending" and notes left un-indexed for over 5 minutes
# — their job was lost
# (Redis restarted, enqueue failed). Self-healing instead of relying on every enqueue.
@broker.task(task_name="sweep_pending_embeddings", schedule=[{"cron": "*/10 * * * *"}])
async def sweep_pending_embeddings_task() -> None:
    new_context(task="sweep_pending_embeddings")
    cutoff = indexing.sweep_cutoff(datetime.now(UTC))
    async with get_sessionmaker()() as session:
        counts = await indexing.embed_pending(session, get_embedding_provider(), older_than=cutoff)
        note_counts = await indexing.embed_stale_notes(
            session, get_embedding_provider(), older_than=cutoff
        )
    log.info("embedding.sweep", **counts, notes=note_counts)


# Mondays 00:30 UTC = 06:00 in India: last week's recap is ready at the start of the week.
@broker.task(task_name="weekly_github_insights", schedule=[{"cron": "30 0 * * 1"}])
async def weekly_github_insights_task() -> None:
    new_context(task="weekly_github_insights")
    settings = get_settings()
    start = last_week_start()
    redis = get_redis()
    done = failed = 0
    async with get_sessionmaker()() as session:
        user_ids = list(
            await session.scalars(select(User.id).where(User.github_username.is_not(None)))
        )
    for user_id in user_ids:
        # One user's failure (GitHub 404, a flaky model) mustn't stop everyone else's.
        try:
            async with get_sessionmaker()() as session:
                usage = AiUsageService(get_sessionmaker(), user_id, settings)
                service = InsightService(
                    session, build_github_client(settings, redis), get_llm_provider(), usage
                )
                await service.generate(user_id, start)
            done += 1
        except Exception:
            failed += 1
            log.warning("github.insight_failed", user_id=str(user_id), exc_info=True)
    log.info("github.weekly_insights", week_start=start.isoformat(), done=done, failed=failed)
