from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import AfterValidator, BaseModel, Field, StringConstraints

from app.schemas.common import normalize_tags


class ExplainRequest(BaseModel):
    level: Literal["beginner", "intermediate", "expert"] = "intermediate"


class SnippetTagSuggestion(BaseModel):
    """What the model must return for auto-tagging; validated, then normalised."""

    language: Annotated[
        str, StringConstraints(strip_whitespace=True, to_lower=True, min_length=1, max_length=40)
    ]
    # Up to 10 accepted from the model, normalised (lowercase kebab-case, deduped), max 5 kept.
    tags: Annotated[
        list[str],
        Field(min_length=1, max_length=10),
        AfterValidator(lambda t: normalize_tags(t)[:5]),
    ]
    description: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=140)
    ]


class AskRequest(BaseModel):
    question: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]


class Source(BaseModel):
    """A numbered passage the answer may cite as [n]."""

    n: int
    note_id: UUID
    note_title: str
    heading: str | None
    excerpt: str


class AiUsageOut(BaseModel):
    used: int
    limit: int
    remaining: int
    resets_at: datetime
