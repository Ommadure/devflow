from datetime import datetime
from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    model_validator,
)

from app.schemas.common import Language, Tags, Title, blank_to_none

Code = Annotated[str, Field(min_length=1, max_length=100_000)]
Description = Annotated[
    Annotated[str, StringConstraints(max_length=1_000)] | None, AfterValidator(blank_to_none)
]


class SnippetCreate(BaseModel):
    title: Title
    description: Description = None
    code: Code
    language: Language = None
    tags: Tags = []
    favorite: bool = False


class SnippetUpdate(BaseModel):
    """PATCH: only the fields sent are changed. Sending null clears description/language;
    the other fields can't be null."""

    title: Title | None = None
    description: Description = None
    code: Code | None = None
    language: Language = None
    tags: Tags | None = None
    favorite: bool | None = None

    @model_validator(mode="after")
    def _required_fields_are_not_null(self) -> Self:
        for name in ("title", "code", "tags", "favorite"):
            if name in self.model_fields_set and getattr(self, name) is None:
                raise ValueError(f"{name} cannot be null")
        return self


class SnippetOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    description: str | None
    code: str
    language: str | None
    tags: list[str]
    favorite: bool
    # pending until the worker has embedded it; only "ready" snippets show up in
    # semantic search (keyword search works immediately).
    embedding_status: Literal["pending", "ready", "failed"]
    created_at: datetime
    updated_at: datetime


class SearchHit(SnippetOut):
    score: float = Field(description="Reciprocal Rank Fusion score; higher is better")
    match_type: Literal["keyword", "semantic", "both"]


class SearchResults(BaseModel):
    items: list[SearchHit]


class TagCount(BaseModel):
    tag: str
    count: int
