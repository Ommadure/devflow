"""Note use cases (see services/snippets.py for the pattern)."""

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundError
from app.core.pagination import Page, PageParams, paginate
from app.models import Note
from app.repositories import notes
from app.schemas.notes import NoteCreate, NoteOut, NoteUpdate
from app.workers.dispatch import JobDispatcher


def _not_found() -> NotFoundError:
    return NotFoundError("Note not found.", code="NOTE_NOT_FOUND")


class NoteService:
    def __init__(self, session: AsyncSession, user_id: UUID, dispatcher: JobDispatcher) -> None:
        self._session = session
        self._user_id = user_id
        self._dispatcher = dispatcher

    async def page(self, params: PageParams, *, q: str | None = None) -> Page[NoteOut]:
        rows = await notes.list_page(self._session, self._user_id, params, q=q)
        items, next_cursor = paginate(rows, params, "updated_at")
        return Page(items=[NoteOut.model_validate(n) for n in items], next_cursor=next_cursor)

    async def get(self, note_id: UUID) -> Note:
        note = await notes.get(self._session, self._user_id, note_id)
        if note is None:
            raise _not_found()
        return note

    async def create(self, data: NoteCreate) -> Note:
        note = await notes.add(self._session, self._user_id, title=data.title, content=data.content)
        await self._session.commit()
        if note.content.strip():
            await self._dispatcher.embed_note(note.id)
        return note

    async def update(self, note_id: UUID, changes: NoteUpdate) -> Note:
        note = await self.get(note_id)
        before = (note.title, note.content)
        for field, value in changes.model_dump(exclude_unset=True).items():
            setattr(note, field, value)
        await self._session.commit()
        # The job itself re-embeds only changed passages; this skips no-op saves entirely.
        if (note.title, note.content) != before:
            await self._dispatcher.embed_note(note.id)
        return note

    async def delete(self, note_id: UUID) -> None:
        if not await notes.delete_one(self._session, self._user_id, note_id):
            raise _not_found()
        await self._session.commit()
