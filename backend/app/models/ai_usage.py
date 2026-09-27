import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    Text,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

FEATURES = ("explain_code", "auto_tag", "ask_notes", "explain_http_error", "github_insights")
STATUSES = ("success", "error", "quota_exceeded")


class AiUsage(Base):
    """One row per LLM call — successful or not, because failed calls can still cost
    money. Feeds the daily quota, the usage indicator and cost reporting."""

    __tablename__ = "ai_usage"
    __table_args__ = (
        CheckConstraint(f"feature IN {FEATURES}", name="feature_valid"),
        CheckConstraint(f"status IN {STATUSES}", name="status_valid"),
        # "This user's calls today" — the quota check on every AI request.
        Index("ix_ai_usage_user_id_created_at", "user_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()")
    )
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    feature: Mapped[str] = mapped_column(Text)
    provider: Mapped[str] = mapped_column(Text)
    model: Mapped[str] = mapped_column(Text)
    prompt_version: Mapped[str | None] = mapped_column(Text)
    input_tokens: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    output_tokens: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    cost_usd: Mapped[Decimal] = mapped_column(Numeric(10, 6), server_default=text("0"))
    latency_ms: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    status: Mapped[str] = mapped_column(Text)
    error_code: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
