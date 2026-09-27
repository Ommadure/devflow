"""AI usage: record every LLM call, and enforce the daily quota before making one."""

from dataclasses import dataclass
from datetime import UTC, datetime, time, timedelta
from decimal import Decimal
from typing import Literal
from uuid import UUID

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import Settings
from app.core.errors import QuotaExceededError
from app.models import AiUsage
from app.services.ai.llm.base import TokenUsage
from app.services.ai.pricing import cost_usd

log = structlog.get_logger()

Feature = Literal["explain_code", "auto_tag", "ask_notes", "explain_http_error", "github_insights"]
Status = Literal["success", "error", "quota_exceeded"]


@dataclass(frozen=True)
class QuotaStatus:
    used: int
    limit: int
    resets_at: datetime

    @property
    def remaining(self) -> int:
        return max(0, self.limit - self.used)


def next_utc_midnight(now: datetime) -> datetime:
    return datetime.combine(now.date() + timedelta(days=1), time(), tzinfo=UTC)


class AiUsageService:
    """Uses its own sessions (not the request's): a streamed answer is recorded after the
    route has returned, when the request's session is already closed."""

    def __init__(
        self, sessions: async_sessionmaker[AsyncSession], user_id: UUID, settings: Settings
    ) -> None:
        self._sessions = sessions
        self._user_id = user_id
        self._settings = settings

    async def quota(self, now: datetime | None = None) -> QuotaStatus:
        now = now or datetime.now(UTC)
        start = datetime.combine(now.date(), time(), tzinfo=UTC)
        async with self._sessions() as session:
            used = await session.scalar(
                select(func.count())
                .select_from(AiUsage)
                .where(
                    AiUsage.user_id == self._user_id,
                    AiUsage.created_at >= start,
                    # Refused requests don't count against the quota; attempts do.
                    AiUsage.status != "quota_exceeded",
                )
            )
        return QuotaStatus(
            used or 0, self._settings.ai_daily_quota_per_user, next_utc_midnight(now)
        )

    async def check_quota(self, feature: Feature) -> None:
        """Before any LLM call — and before a stream starts, so a 429 is a clean HTTP error
        rather than an error event halfway through an answer."""
        status = await self.quota()
        if status.remaining > 0:
            return
        await self.record(feature, provider="-", model="-", status="quota_exceeded")
        seconds = int((status.resets_at - datetime.now(UTC)).total_seconds())
        raise QuotaExceededError(
            retry_after=seconds,
            message=f"You've used all {status.limit} AI requests for today.",
        )

    async def record(
        self,
        feature: Feature,
        *,
        provider: str,
        model: str,
        status: Status,
        prompt_version: str | None = None,
        usage: TokenUsage | None = None,
        latency_ms: int = 0,
        error_code: str | None = None,
    ) -> None:
        usage = usage or TokenUsage()
        cost = cost_usd(model, usage, self._settings.llm_pricing)
        async with self._sessions() as session:
            session.add(
                AiUsage(
                    user_id=self._user_id,
                    feature=feature,
                    provider=provider,
                    model=model,
                    prompt_version=prompt_version,
                    input_tokens=usage.input_tokens,
                    output_tokens=usage.output_tokens,
                    cost_usd=Decimal(str(round(cost, 6))),
                    latency_ms=latency_ms,
                    status=status,
                    error_code=error_code,
                )
            )
            await session.commit()
        log.info(
            "ai.usage", feature=feature, model=model, status=status, prompt=prompt_version,
            input_tokens=usage.input_tokens, output_tokens=usage.output_tokens,
            cost_usd=round(cost, 6), latency_ms=latency_ms, error_code=error_code,
        )  # fmt: skip
