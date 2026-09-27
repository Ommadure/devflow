import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Text, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Note(Base):
    __tablename__ = "notes"
    __table_args__ = (
        # The notes list is sorted by last update; keyset pagination walks this index.
        Index("ix_notes_user_id_updated_at_id", "user_id", "updated_at", "id"),
    )
    __mapper_args__ = {"eager_defaults": True}  # noqa: RUF012  (see Snippet)

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()")
    )
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    title: Mapped[str] = mapped_column(Text, server_default=text("''"))
    content: Mapped[str] = mapped_column(Text, server_default=text("''"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    # The `updated_at` its chunks were built from. Behind `updated_at` (or null) = the
    # passages are out of date and the worker (or the sweep) must re-chunk the note.
    indexed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
