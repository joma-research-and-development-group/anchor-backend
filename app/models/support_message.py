import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.user import Base, GUID


class SenderTypeEnum(str, enum.Enum):
    user = "user"
    admin = "admin"


class SupportMessage(Base):
    __tablename__ = "support_messages"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    conversation_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("support_conversations.id", ondelete="CASCADE"), nullable=False)
    sender_type: Mapped[SenderTypeEnum] = mapped_column(Enum(SenderTypeEnum), nullable=False)
    sender_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), nullable=True)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    attachment_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
