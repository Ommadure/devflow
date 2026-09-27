import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Computed,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.snippet import EMBEDDING_DIM

# The heading a passage sits under outweighs the passage itself.
CHUNK_TSV = (
    "setweight(to_tsvector('english', coalesce(heading, '')), 'A') || "
    "setweight(to_tsvector('english', content), 'B')"
)


class NoteChunk(Base):
    """A passage of a note (~300 tokens, split at headings), embedded for "ask your notes".

    Whole notes are too long and too mixed to embed usefully; passages can be retrieved and
    cited ("[2]") precisely. Only changed passages are re-embedded when a note is edited.
    """

    __tablename__ = "note_chunks"
    __table_args__ = (
        UniqueConstraint("note_id", "chunk_index"),
        Index("ix_note_chunks_user_id", "user_id"),
        Index(
            "ix_note_chunks_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
        Index("ix_note_chunks_search_tsv", "search_tsv", postgresql_using="gin"),
    )
    __mapper_args__ = {"eager_defaults": True}  # noqa: RUF012

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()")
    )
    note_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("notes.id", ondelete="CASCADE"))
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    chunk_index: Mapped[int] = mapped_column(Integer)
    heading: Mapped[str | None] = mapped_column(Text)
    content: Mapped[str] = mapped_column(Text)
    content_hash: Mapped[str] = mapped_column(Text)
    token_count: Mapped[int] = mapped_column(Integer)
    embedding: Mapped[list[float]] = mapped_column(
        Vector(EMBEDDING_DIM), deferred=True, deferred_raiseload=True
    )
    search_tsv: Mapped[str] = mapped_column(
        TSVECTOR, Computed(CHUNK_TSV, persisted=True), deferred=True, deferred_raiseload=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
