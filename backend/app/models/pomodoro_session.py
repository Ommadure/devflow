import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class PomodoroSession(Base):
    """One completed focus session. History, not a counter: Phase 6 computes daily
    minutes and streaks from these rows in SQL."""

    __tablename__ = "pomodoro_sessions"
    __table_args__ = (
        CheckConstraint("duration_seconds > 0", name="duration_positive"),
        Index("ix_pomodoro_sessions_user_id_completed_at_id", "user_id", "completed_at", "id"),
    )
    __mapper_args__ = {"eager_defaults": True}  # noqa: RUF012  (see Snippet)

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()")
    )
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    # Stamped by the server: the client says "a session finished", never when.
    completed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    duration_seconds: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
