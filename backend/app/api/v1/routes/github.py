from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from app.api.deps import (
    AiUsageDep,
    CurrentUserDep,
    GitHubDep,
    LLMDep,
    SessionDep,
    ai_rate_limit,
)
from app.schemas.github import GithubOverview, InsightOut
from app.services.github.insights import IST, InsightService, list_insights, week_start

router = APIRouter(prefix="/github", tags=["github"])


@router.get(
    "/overview",
    responses={
        404: {"description": "No such GitHub user"},
        422: {"description": "Not a valid GitHub username"},
        429: {"description": "GitHub's rate limit is used up (GITHUB_RATE_LIMITED)"},
    },
)
async def overview(
    github: GitHubDep, username: Annotated[str, Query(min_length=1, max_length=39)]
) -> GithubOverview:
    """A public profile and its six most recently updated repositories (cached 15 min)."""
    return GithubOverview.model_validate(await github.overview(username))


@router.get("/insights")
async def insights(
    current: CurrentUserDep, session: SessionDep, limit: Annotated[int, Query(ge=1, le=12)] = 4
) -> list[InsightOut]:
    """Stored weekly insights, newest week first."""
    return await list_insights(session, current.id, limit)


@router.post(
    "/insights/generate",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(ai_rate_limit)],
    responses={422: {"description": "No GitHub username set"}, 429: {"description": "Quota"}},
)
async def generate(
    current: CurrentUserDep, session: SessionDep, github: GitHubDep, llm: LLMDep, usage: AiUsageDep
) -> InsightOut:
    """(Re)generate this week's insight so far. Counts against the daily AI quota."""
    await usage.check_quota("github_insights")
    start = week_start(datetime.now(UTC).astimezone(IST).date())
    row = await InsightService(session, github, llm, usage).generate(current.id, start)
    return InsightOut.model_validate(row)
