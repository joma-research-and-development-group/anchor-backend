import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.user import Base, GUID


class PlatformEnum(str, enum.Enum):
    ios = "ios"
    android = "android"
    macos = "macos"
    windows = "windows"
    linux = "linux"
    web = "web"


class AppVersion(Base):
    __tablename__ = "app_versions"
    __table_args__ = (
        UniqueConstraint("project_id", "mode_id", "platform", "semver", "build_number", name="uq_app_version"),
    )

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    mode_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("project_modes.id", ondelete="CASCADE"), nullable=False
    )
    platform: Mapped[PlatformEnum] = mapped_column(Enum(PlatformEnum), nullable=False)
    semver: Mapped[str] = mapped_column(String(50), nullable=False)
    build_number: Mapped[int] = mapped_column(Integer, nullable=False)
    released_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("users.id"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
