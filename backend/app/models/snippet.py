import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Computed,
    DateTime,
    ForeignKey,
    Index,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

# Changing this means a new migration (the column type) and re-embedding every snippet.
EMBEDDING_DIM = 384

# Weighted full-text document: a word in the title (A) outranks one in the description or
# tags (B), which outranks one in the code (C). Prose uses the English config (stemming:
# "debouncing" matches "debounce"); code uses "simple" (identifiers stay as written).
# search_words() adds a camelCase-split copy, so "debounce" also finds `useDebounce`.
SEARCH_TSV = (
    "setweight(to_tsvector('english', search_words(title)), 'A') || "
    "setweight(to_tsvector('english', coalesce(description, '')), 'B') || "
    "setweight(to_tsvector('english', snippet_tags_text(tags)), 'B') || "
    "setweight(to_tsvector('simple', search_words(code)), 'C')"
)


class Snippet(Base):
    __tablename__ = "snippets"
    __table_args__ = (
        # Serves the list's keyset pagination: one user's rows, newest first.
        Index("ix_snippets_user_id_created_at_id", "user_id", "created_at", "id"),
        CheckConstraint(
            "embedding_status IN ('pending', 'ready', 'failed')", name="embedding_status_valid"
        ),
        # Approximate nearest-neighbour index for cosine distance (the `<=>` operator).
        Index(
            "ix_snippets_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
        Index("ix_snippets_search_tsv", "search_tsv", postgresql_using="gin"),
    )
    # Fetch server-generated values (created_at, updated_at) with RETURNING on write, so
    # reading them afterwards doesn't need a second, lazy query (not allowed in async).
    __mapper_args__ = {"eager_defaults": True}  # noqa: RUF012

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()")
    )
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    title: Mapped[str] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)
    code: Mapped[str] = mapped_column(Text)
    language: Mapped[str | None] = mapped_column(Text)
    # Postgres' own ARRAY type: it supports `@>` (contains), which the tag filter uses.
    tags: Mapped[list[str]] = mapped_column(ARRAY(Text), server_default=text("'{}'"))
    favorite: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # ---- search (Phase 4) ----
    # Hash of the text the stored embedding was made from; equal hash + "ready" = skip.
    content_hash: Mapped[str | None] = mapped_column(Text)
    # deferred + raiseload: lists never drag 384 floats per row out of the database, and
    # touching the attribute without loading it on purpose fails loudly instead of lazily.
    embedding: Mapped[list[float] | None] = mapped_column(
        Vector(EMBEDDING_DIM), deferred=True, deferred_raiseload=True
    )
    embedding_status: Mapped[str] = mapped_column(Text, server_default=text("'pending'"))
    embedded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    search_tsv: Mapped[str] = mapped_column(
        TSVECTOR, Computed(SEARCH_TSV, persisted=True), deferred=True, deferred_raiseload=True
    )
