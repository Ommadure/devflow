from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Query, status

from app.api.deps import NoteServiceDep, PageParamsDep
from app.core.pagination import Page
from app.schemas.notes import NoteCreate, NoteOut, NoteUpdate

router = APIRouter(prefix="/notes", tags=["notes"])

NOT_FOUND: dict[int | str, dict[str, Any]] = {404: {"description": "Note not found (or not yours)"}}


@router.get("")
async def list_notes(
    notes: NoteServiceDep,
    page: PageParamsDep,
    q: Annotated[
        str | None, Query(max_length=200, description="Substring of title or content")
    ] = None,
) -> Page[NoteOut]:
    return await notes.page(page, q=q)


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_note(body: NoteCreate, notes: NoteServiceDep) -> NoteOut:
    return NoteOut.model_validate(await notes.create(body))


@router.get("/{note_id}", responses=NOT_FOUND)
async def get_note(note_id: UUID, notes: NoteServiceDep) -> NoteOut:
    return NoteOut.model_validate(await notes.get(note_id))


@router.patch("/{note_id}", responses=NOT_FOUND)
async def update_note(note_id: UUID, body: NoteUpdate, notes: NoteServiceDep) -> NoteOut:
    return NoteOut.model_validate(await notes.update(note_id, body))


@router.delete("/{note_id}", status_code=status.HTTP_204_NO_CONTENT, responses=NOT_FOUND)
async def delete_note(note_id: UUID, notes: NoteServiceDep) -> None:
    await notes.delete(note_id)
