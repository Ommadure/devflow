"""Snippet use cases. Services own the unit of work (they commit) and turn "no row" into
a 404 — the same answer whether the snippet never existed or belongs to someone else."""

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundError
from app.core.pagination import Page, PageParams, paginate
from app.models import Snippet
from app.repositories import snippets
from app.schemas.snippets import SnippetCreate, SnippetOut, SnippetUpdate, TagCount
from app.services.ai.embedding_text import content_hash, embedding_text
from app.workers.dispatch import JobDispatcher


def _not_found() -> NotFoundError:
    return NotFoundError("Snippet not found.", code="SNIPPET_NOT_FOUND")


class SnippetService:
    def __init__(
        self,
        session: AsyncSession,
        user_id: UUID,
        dispatcher: JobDispatcher,
        embedding_model: str,
    ) -> None:
        self._session = session
        self._user_id = user_id
        self._dispatcher = dispatcher
        self._embedding_model = embedding_model

    async def page(
        self,
        params: PageParams,
        *,
        language: str | None = None,
        tag: str | None = None,
        favorite: bool | None = None,
    ) -> Page[SnippetOut]:
        rows = await snippets.list_page(
            self._session,
            self._user_id,
            params,
            language=language.lower() if language else None,
            tag=tag.lower() if tag else None,
            favorite=favorite,
        )
        items, next_cursor = paginate(rows, params, "created_at")
        return Page(items=[SnippetOut.model_validate(s) for s in items], next_cursor=next_cursor)

    async def get(self, snippet_id: UUID) -> Snippet:
        snippet = await snippets.get(self._session, self._user_id, snippet_id)
        if snippet is None:
            raise _not_found()
        return snippet

    async def create(self, data: SnippetCreate) -> Snippet:
        snippet = await snippets.add(self._session, self._user_id, **data.model_dump())
        await self._session.commit()
        # After the commit, never before: a worker fast enough to start before the
        # transaction commits wouldn't see the row yet.
        await self._dispatcher.embed_snippet(snippet.id)
        return snippet

    async def update(self, snippet_id: UUID, changes: SnippetUpdate) -> Snippet:
        snippet = await self.get(snippet_id)
        for field, value in changes.model_dump(exclude_unset=True).items():
            setattr(snippet, field, value)
        # Re-embed only when the embedded text changed: starring a snippet costs nothing.
        needs_embedding = (
            content_hash(embedding_text(snippet), self._embedding_model) != snippet.content_hash
        )
        if needs_embedding:
            snippet.embedding_status = "pending"
        await self._session.commit()
        if needs_embedding:
            await self._dispatcher.embed_snippet(snippet.id)
        return snippet

    async def delete(self, snippet_id: UUID) -> None:
        if not await snippets.delete_one(self._session, self._user_id, snippet_id):
            raise _not_found()
        await self._session.commit()

    async def tags(self) -> list[TagCount]:
        rows = await snippets.tag_counts(self._session, self._user_id)
        return [TagCount(tag=tag, count=count) for tag, count in rows]
