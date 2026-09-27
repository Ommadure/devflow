"""How the API hands work to the worker, behind a protocol (ADR 0003).

Services call `dispatcher.embed_snippet(id)` after committing; they don't know about
Taskiq. Tests swap in a recorder, so no test needs Redis streams or a running worker.
"""

from typing import Protocol
from uuid import UUID

import structlog

log = structlog.get_logger()


class JobDispatcher(Protocol):
    async def embed_snippet(self, snippet_id: UUID) -> None: ...


class TaskiqDispatcher:
    async def embed_snippet(self, snippet_id: UUID) -> None:
        # Imported here so the API (and scripts like the OpenAPI export) only load the
        # broker when they actually enqueue something.
        from app.workers.tasks import embed_snippet_task

        try:
            await embed_snippet_task.kiq(str(snippet_id))
        except Exception:
            # The snippet is already saved. If Redis is down, don't fail the user's request:
            # the row stays "pending" and the scheduled sweep embeds it later.
            log.exception("jobs.enqueue_failed", task="embed_snippet", snippet_id=str(snippet_id))


def get_dispatcher() -> JobDispatcher:
    return TaskiqDispatcher()
