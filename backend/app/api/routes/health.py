"""Liveness and readiness probes (spec §8.5).

/health answers "is the process alive?" and never touches dependencies, so a database
outage can't make the platform restart a healthy process in a loop. /ready answers "can
this instance do useful work right now?" by checking Postgres and Redis.
"""

import asyncio
from collections.abc import Awaitable, Callable
from typing import Annotated, Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import text

from app.core.errors import ServiceUnavailableError
from app.core.redis import get_redis
from app.db.session import get_engine

router = APIRouter(tags=["infrastructure"])

ReadinessCheck = Callable[[], Awaitable[object]]
CHECK_TIMEOUT_SECONDS = 2.0


async def check_database() -> None:
    async with get_engine().connect() as conn:
        await conn.execute(text("SELECT 1"))


async def check_redis() -> None:
    await get_redis().ping()


def get_readiness_checks() -> dict[str, ReadinessCheck]:
    """A dependency, so tests can swap in fakes instead of real Postgres/Redis."""
    return {"database": check_database, "redis": check_redis}


class HealthOut(BaseModel):
    status: Literal["ok"] = "ok"


class ReadyOut(BaseModel):
    status: Literal["ok"] = "ok"
    checks: dict[str, str]


@router.get("/health")
async def health() -> HealthOut:
    return HealthOut()


@router.get("/ready", responses={503: {"description": "A dependency is unavailable"}})
async def ready(
    checks: Annotated[dict[str, ReadinessCheck], Depends(get_readiness_checks)],
) -> ReadyOut:
    async def run(check: ReadinessCheck) -> str:
        try:
            await asyncio.wait_for(check(), timeout=CHECK_TIMEOUT_SECONDS)
        except Exception:
            return "error"
        return "ok"

    # In parallel: a hanging Redis shouldn't double the time to report a hanging database.
    outcomes = await asyncio.gather(*(run(check) for check in checks.values()))
    results = dict(zip(checks, outcomes, strict=True))
    if any(result != "ok" for result in results.values()):
        raise ServiceUnavailableError("Not ready.", code="NOT_READY", details={"checks": results})
    return ReadyOut(checks=results)
