"""Weekly GitHub insights (spec §11.8): aggregate a week of public events into numbers, ask
the model for a short recap of those numbers, store both — one row per user per week."""

from collections import Counter
from datetime import UTC, date, datetime, time, timedelta
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo

import structlog
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ValidationFailedError
from app.models import GithubInsight, User
from app.schemas.github import InsightOut, WeeklyInsight
from app.services.ai.assistant import structured_call
from app.services.ai.llm.base import LLMProvider, Message
from app.services.ai.prompts import load
from app.services.ai.usage import AiUsageService
from app.services.github.client import GitHubClient

log = structlog.get_logger()

PROMPT = "github_insights_v1"
IST = ZoneInfo("Asia/Kolkata")
QUIET_WEEK = WeeklyInsight(
    headline="A quiet week on GitHub.",
    highlights=["No public activity this week.", "Rest weeks count too."],
    suggestions=["Pick one small issue or README fix to get moving again."],
)


def week_start(day: date) -> date:
    """The Monday of the week containing `day`."""
    return day - timedelta(days=day.weekday())


def aggregate(events: list[dict[str, Any]], start: date, tz: ZoneInfo = IST) -> dict[str, Any]:
    """Numbers only — no commit messages or code — for [start, start + 7 days) in `tz`."""
    begin = datetime.combine(start, time(), tzinfo=tz)
    end = begin + timedelta(days=7)
    in_week = [
        event for event in events
        if begin <= datetime.fromisoformat(event["created_at"]).astimezone(tz) < end
    ]  # fmt: skip
    kinds = Counter(event["type"] for event in in_week)
    repos = Counter(event["repo"]["name"] for event in in_week)
    days = Counter(
        datetime.fromisoformat(event["created_at"]).astimezone(tz).strftime("%A")
        for event in in_week
    )
    commits = sum(
        int(event["payload"].get("size", len(event["payload"].get("commits", []))))
        for event in in_week
        if event["type"] == "PushEvent"
    )
    pulls = [e["payload"] for e in in_week if e["type"] == "PullRequestEvent"]
    return {
        "events": len(in_week),
        "commits": commits,
        "pull_requests_opened": sum(1 for p in pulls if p.get("action") == "opened"),
        "pull_requests_merged": sum(
            1
            for p in pulls
            if p.get("action") == "closed" and p.get("pull_request", {}).get("merged")
        ),
        "reviews": kinds.get("PullRequestReviewEvent", 0),
        "issues_opened": sum(
            1
            for e in in_week
            if e["type"] == "IssuesEvent" and e["payload"].get("action") == "opened"
        ),
        "repositories": [{"name": name, "events": n} for name, n in repos.most_common(5)],
        "active_days": len(days),
        "busiest_day": days.most_common(1)[0][0] if days else None,
    }


class InsightService:
    def __init__(
        self,
        session: AsyncSession,
        github: GitHubClient,
        llm: LLMProvider,
        usage: AiUsageService,
    ) -> None:
        self._session = session
        self._github = github
        self._llm = llm
        self._usage = usage

    async def generate(self, user_id: UUID, start: date) -> GithubInsight:
        user = await self._session.get(User, user_id)
        if user is None or not user.github_username:
            raise ValidationFailedError(
                "Set your GitHub username in Settings first.", code="GITHUB_USERNAME_MISSING"
            )
        stats = aggregate(await self._github.public_events(user.github_username), start)
        if stats["events"] == 0:
            summary = QUIET_WEEK  # nothing to summarise: no LLM call, no cost
        else:
            summary = await structured_call(
                self._llm,
                [
                    Message("system", load(PROMPT)),
                    Message("user", f"Week starting {start.isoformat()} (Monday):\n{stats}"),
                ],
                WeeklyInsight,
                feature="github_insights",
                prompt_version=PROMPT,
                usage=self._usage,
            )
        values = {
            "github_username": user.github_username,
            "stats": stats,
            "summary": summary.model_dump(),
        }
        # Upsert: regenerating a week (the cron re-running, or "Generate now" twice) replaces
        # that week's row instead of adding a second one.
        row: GithubInsight | None = await self._session.scalar(
            pg_insert(GithubInsight)
            .values(user_id=user_id, week_start=start, **values)
            .on_conflict_do_update(index_elements=["user_id", "week_start"], set_=values)
            .returning(GithubInsight)
        )
        await self._session.commit()
        if row is None:  # pragma: no cover  (RETURNING always yields the upserted row)
            raise RuntimeError("upsert returned no row")
        log.info(
            "github.insight",
            user_id=str(user_id),
            week_start=start.isoformat(),
            events=stats["events"],
        )
        return row


async def list_insights(session: AsyncSession, user_id: UUID, limit: int) -> list[InsightOut]:
    rows = await session.scalars(
        select(GithubInsight)
        .where(GithubInsight.user_id == user_id)
        .order_by(GithubInsight.week_start.desc())
        .limit(limit)
    )
    return [InsightOut.model_validate(row) for row in rows]


def last_week_start(now: datetime | None = None, tz: ZoneInfo = IST) -> date:
    today = (now or datetime.now(UTC)).astimezone(tz).date()
    return week_start(today) - timedelta(days=7)
