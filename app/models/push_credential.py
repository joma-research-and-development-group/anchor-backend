import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, LargeBinary, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.user import Base, GUID


class PushProviderEnum(str, enum.Enum):
    fcm = "fcm"
    apns = "apns"


class PushCredential(Base):
    __tablename__ = "push_credentials"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    mode_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("project_modes.id", ondelete="CASCADE"), nullable=False)
    platform: Mapped[str] = mapped_column(String(50), nullable=False)
    provider: Mapped[PushProviderEnum] = mapped_column(Enum(PushProviderEnum), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    encrypted_creds: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_by: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
