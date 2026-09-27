import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Text, func, text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Snippet(Base):
    __tablename__ = "snippets"
    __table_args__ = (
        # Serves the list's keyset pagination: one user's rows, newest first.
        Index("ix_snippets_user_id_created_at_id", "user_id", "created_at", "id"),
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
