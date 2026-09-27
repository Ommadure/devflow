"""Cursor (keyset) pagination: `?limit=20&cursor=<opaque>` → `{items, next_cursor}`.

Offset pagination (`?page=3`) re-counts every skipped row on each request and shifts when
rows are added or deleted between pages. A cursor instead remembers the last row seen —
its sort value and id — and the next page asks for rows strictly "after" it, which an
index answers directly however deep the page.
"""

import base64
import binascii
import json
from dataclasses import dataclass
from datetime import datetime
from typing import Annotated, Any
from uuid import UUID

from fastapi import Query
from pydantic import BaseModel
from sqlalchemy import Select, tuple_
from sqlalchemy.orm import InstrumentedAttribute

from app.core.errors import ValidationFailedError

DEFAULT_LIMIT = 20
MAX_LIMIT = 100


@dataclass(frozen=True)
class Cursor:
    at: datetime  # the sort column's value on the last row of the previous page
    id: UUID  # tie-breaker: two rows can share a timestamp

    def encode(self) -> str:
        raw = json.dumps({"at": self.at.isoformat(), "id": str(self.id)}).encode()
        return base64.urlsafe_b64encode(raw).decode().rstrip("=")

    @classmethod
    def decode(cls, value: str) -> "Cursor":
        try:
            padded = value + "=" * (-len(value) % 4)
            data = json.loads(base64.urlsafe_b64decode(padded))
            return cls(at=datetime.fromisoformat(data["at"]), id=UUID(data["id"]))
        except (binascii.Error, ValueError, KeyError, TypeError) as exc:
            raise ValidationFailedError("Invalid cursor.", code="INVALID_CURSOR") from exc


class Page[T](BaseModel):
    items: list[T]
    next_cursor: str | None


@dataclass(frozen=True)
class PageParams:
    limit: int
    cursor: Cursor | None


def page_params(
    limit: Annotated[int, Query(ge=1, le=MAX_LIMIT)] = DEFAULT_LIMIT,
    cursor: Annotated[str | None, Query(description="next_cursor from the previous page")] = None,
) -> PageParams:
    return PageParams(limit=limit, cursor=Cursor.decode(cursor) if cursor else None)


def keyset[S: Select[Any]](
    stmt: S,
    sort_column: InstrumentedAttribute[datetime],
    id_column: InstrumentedAttribute[UUID],
    params: PageParams,
) -> S:
    """Newest first, continuing after the cursor. Fetches one extra row to learn whether a
    next page exists without a COUNT query."""
    if params.cursor is not None:
        stmt = stmt.where(
            tuple_(sort_column, id_column) < tuple_(params.cursor.at, params.cursor.id)
        )
    return stmt.order_by(sort_column.desc(), id_column.desc()).limit(params.limit + 1)


def paginate[M](rows: list[M], params: PageParams, sort_key: str) -> tuple[list[M], str | None]:
    """Split the limit+1 rows from `keyset` into this page and the cursor for the next."""
    if len(rows) <= params.limit:
        return rows, None
    page = rows[: params.limit]
    last = page[-1]
    return page, Cursor(at=getattr(last, sort_key), id=last.id).encode()  # type: ignore[attr-defined]
