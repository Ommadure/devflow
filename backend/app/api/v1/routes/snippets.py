from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Query, status

from app.api.deps import PageParamsDep, SearchServiceDep, SnippetServiceDep
from app.core.pagination import Page
from app.repositories.search import Filters, Mode
from app.schemas.snippets import (
    SearchResults,
    SnippetCreate,
    SnippetOut,
    SnippetUpdate,
    TagCount,
)

router = APIRouter(prefix="/snippets", tags=["snippets"])

NOT_FOUND: dict[int | str, dict[str, Any]] = {
    404: {"description": "Snippet not found (or not yours)"}
}


@router.get("")
async def list_snippets(
    snippets: SnippetServiceDep,
    page: PageParamsDep,
    language: Annotated[str | None, Query(max_length=40)] = None,
    tag: Annotated[str | None, Query(max_length=40)] = None,
    favorite: bool | None = None,
) -> Page[SnippetOut]:
    return await snippets.page(page, language=language, tag=tag, favorite=favorite)


# Declared before /{snippet_id}, or "search" and "tags" would be parsed as ids.
@router.get("/search")
async def search_snippets(
    search: SearchServiceDep,
    q: Annotated[str, Query(min_length=1, max_length=200)],
    mode: Mode = "hybrid",
    language: Annotated[str | None, Query(max_length=40)] = None,
    tag: Annotated[str | None, Query(max_length=40)] = None,
    favorite: bool | None = None,
    limit: Annotated[int, Query(ge=1, le=50)] = 10,
) -> SearchResults:
    """Hybrid search: `keyword` (full text), `semantic` (meaning) or both fused (`hybrid`).
    Each item says how it matched."""
    filters = Filters(
        language=language.lower() if language else None,
        tag=tag.lower() if tag else None,
        favorite=favorite,
    )
    return await search.search(q.strip(), mode=mode, filters=filters, limit=limit)


@router.get("/tags")
async def list_tags(snippets: SnippetServiceDep) -> list[TagCount]:
    return await snippets.tags()


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_snippet(body: SnippetCreate, snippets: SnippetServiceDep) -> SnippetOut:
    return SnippetOut.model_validate(await snippets.create(body))


@router.get("/{snippet_id}", responses=NOT_FOUND)
async def get_snippet(snippet_id: UUID, snippets: SnippetServiceDep) -> SnippetOut:
    return SnippetOut.model_validate(await snippets.get(snippet_id))


@router.patch("/{snippet_id}", responses=NOT_FOUND)
async def update_snippet(
    snippet_id: UUID, body: SnippetUpdate, snippets: SnippetServiceDep
) -> SnippetOut:
    return SnippetOut.model_validate(await snippets.update(snippet_id, body))


@router.delete("/{snippet_id}", status_code=status.HTTP_204_NO_CONTENT, responses=NOT_FOUND)
async def delete_snippet(snippet_id: UUID, snippets: SnippetServiceDep) -> None:
    await snippets.delete(snippet_id)
