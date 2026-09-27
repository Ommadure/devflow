from datetime import date, datetime
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field, StringConstraints


class GithubProfile(BaseModel):
    login: str
    name: str | None = None
    avatar_url: str
    html_url: str
    bio: str | None = None
    company: str | None = None
    location: str | None = None
    blog: str | None = None
    followers: int = 0
    following: int = 0
    public_repos: int = 0


class GithubRepo(BaseModel):
    name: str
    html_url: str
    description: str | None = None
    language: str | None = None
    stargazers_count: int = 0
    forks_count: int = 0
    updated_at: datetime


class GithubOverview(BaseModel):
    profile: GithubProfile
    repos: list[GithubRepo]


Line = Annotated[str, StringConstraints(max_length=240)]


class WeeklyInsight(BaseModel):
    """What the model must return (spec §11.8)."""

    headline: Annotated[str, StringConstraints(min_length=1, max_length=140)]
    highlights: Annotated[list[Line], Field(min_length=2, max_length=4)]
    suggestions: Annotated[list[Line], Field(min_length=1, max_length=3)]


class InsightOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    week_start: date
    github_username: str
    stats: dict[str, Any]
    summary: WeeklyInsight
    created_at: datetime
