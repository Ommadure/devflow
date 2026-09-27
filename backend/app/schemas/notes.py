from datetime import datetime
from typing import Annotated, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

# Notes may be untitled while being written ("" shows as "Untitled" in the UI).
NoteTitle = Annotated[str, StringConstraints(strip_whitespace=True, max_length=200)]
NoteContent = Annotated[str, Field(max_length=200_000)]


class NoteCreate(BaseModel):
    title: NoteTitle = ""
    content: NoteContent = ""


class NoteUpdate(BaseModel):
    title: NoteTitle | None = None
    content: NoteContent | None = None

    @model_validator(mode="after")
    def _no_nulls(self) -> Self:
        for name in self.model_fields_set:
            if getattr(self, name) is None:
                raise ValueError(f"{name} cannot be null")
        return self


class NoteOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    content: str
    created_at: datetime
    updated_at: datetime
