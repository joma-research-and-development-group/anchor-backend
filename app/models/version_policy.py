import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Enum, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.user import Base, GUID
from app.models.app_version import PlatformEnum


class VersionPolicy(Base):
    __tablename__ = "version_policies"
    __table_args__ = (
        UniqueConstraint("project_id", "mode_id", "platform", name="uq_version_policy"),
    )

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    mode_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("project_modes.id", ondelete="CASCADE"), nullable=False
    )
    platform: Mapped[PlatformEnum] = mapped_column(Enum(PlatformEnum), nullable=False)
    min_supported_semver: Mapped[str | None] = mapped_column(String(50), nullable=True)
    latest_semver: Mapped[str | None] = mapped_column(String(50), nullable=True)
    store_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    message_force: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    message_soft: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
