import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.user import Base, GUID


class RatingRule(Base):
    __tablename__ = "rating_rules"
    __table_args__ = (
        UniqueConstraint("project_id", "mode_id", name="uq_rating_rule_project_mode"),
    )

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    mode_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("project_modes.id", ondelete="CASCADE"), nullable=False)
    min_sessions: Mapped[int] = mapped_column(Integer, default=5, nullable=False)
    min_days_since_install: Mapped[int] = mapped_column(Integer, default=7, nullable=False)
    cooldown_days: Mapped[int] = mapped_column(Integer, default=30, nullable=False)
    exclude_negative_events: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    store_url_ios: Mapped[str | None] = mapped_column(String(512), nullable=True)
    store_url_android: Mapped[str | None] = mapped_column(String(512), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
