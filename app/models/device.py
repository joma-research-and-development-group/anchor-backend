import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.push_credential import PushProviderEnum
from app.models.user import Base, GUID


class Device(Base):
    __tablename__ = "devices"
    __table_args__ = (
        UniqueConstraint("project_id", "mode_id", "install_id", name="uq_device_install"),
    )

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    mode_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("project_modes.id", ondelete="CASCADE"), nullable=False)
    install_id: Mapped[str] = mapped_column(String(255), nullable=False)
    user_ref: Mapped[str | None] = mapped_column(String(255), nullable=True)
    push_token: Mapped[str | None] = mapped_column(String(512), nullable=True)
    push_provider: Mapped[PushProviderEnum | None] = mapped_column(Enum(PushProviderEnum), nullable=True)
    platform: Mapped[str] = mapped_column(String(50), nullable=False)
    os_version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    device_model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    app_version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    build_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    locale: Mapped[str | None] = mapped_column(String(20), nullable=True)
    timezone: Mapped[str | None] = mapped_column(String(100), nullable=True)
    country: Mapped[str | None] = mapped_column(String(10), nullable=True)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    last_active_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    attributes: Mapped[dict | None] = mapped_column(JSON, nullable=True)
