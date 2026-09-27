# ADR 0003: Taskiq for background jobs

- **Status:** Accepted
- **Date:** 2026-09-26
- **Replaces:** the original "ARQ, not Celery"

## Context
Embedding snippets and notes, backfills and the weekly GitHub insight must not run inside
a request: they are slow, can fail transiently, and must be retried. The backend is fully
async (FastAPI, SQLAlchemy async, httpx). The original plan chose ARQ for being small and
async-native, but ARQ's README now states it is in **maintenance-only mode** (issue #510).

## Decision
- **Taskiq** with a Redis broker (`taskiq-redis`).
- Two processes from the API's image: a **worker** and a **scheduler** (cron for the
  weekly insight). Exactly one scheduler runs, or every cron job fires twice.
- Tasks are `async def` and reuse the same services and repositories as the API.
- Jobs are enqueued **after** the database transaction commits.
- Retries with backoff (up to 3) for transient failures; tasks are idempotent (content
  hashes, upserts) because a retried or duplicated job must be harmless.
- Enqueuing goes through a small dispatcher protocol so tests record jobs instead of
  needing a broker.

## Consequences
- No `asyncio.run` bridge inside sync tasks (the workaround ReviewPilot needs with Celery).
- A newer, smaller ecosystem than Celery: fewer answers online, no Flower. Worker health
  is observed through logs and `embedding_status` columns.
- **Broker (settled in Phase 4):** `RedisStreamBroker`. A message is acknowledged only after
  its task finishes; one left unacknowledged (the worker died) is redelivered after
  `idle_timeout`. At-least-once, so tasks are idempotent — content hashes skip unchanged
  text, and a conditional update never overwrites a newer edit.
- **Retries** are an explicit loop in the task (3 attempts, then `failed`), not middleware:
  the final failure has to be recorded, and a loop makes that obvious.
- **A young library moves fast:** taskiq 0.13.0 broke taskiq-redis the day before Phase 4,
  so taskiq is pinned `<0.13`. CI imports the tasks, so a bad upgrade fails the build.

## Alternatives considered
- **ARQ**: fits well technically, but choosing a maintenance-only library for new work is
  hard to defend.
- **Celery**: the most common choice and already used in ReviewPilot, but sync-first —
  every task would wrap async code in `asyncio.run`. Using a different queue here also
  gives Om a comparison to talk about.
- **FastAPI `BackgroundTasks`**: runs in the web process; lost on restart, no retries, no
  schedule.
