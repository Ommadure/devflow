import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import Date, DateTime, ForeignKey, Text, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class GithubInsight(Base):
    """One week's GitHub activity for one user: the numbers, and the AI's summary of them.
    Unique per (user, week) — regenerating a week replaces it (an upsert), never duplicates."""

    __tablename__ = "github_insights"
    __table_args__ = (UniqueConstraint("user_id", "week_start"),)
    __mapper_args__ = {"eager_defaults": True}  # noqa: RUF012

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()")
    )
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    github_username: Mapped[str] = mapped_column(Text)
    week_start: Mapped[date] = mapped_column(Date)  # a Monday, in the user's timezone
    stats: Mapped[dict[str, Any]] = mapped_column(JSONB)
    summary: Mapped[dict[str, Any]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
