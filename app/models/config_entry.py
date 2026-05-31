import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Enum, ForeignKey, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.user import Base, GUID


class ConfigValueTypeEnum(str, enum.Enum):
    bool = "bool"
    string = "string"
    int = "int"
    double = "double"
    json = "json"


class ConfigEntry(Base):
    __tablename__ = "config_entries"
    __table_args__ = (
        UniqueConstraint("project_id", "mode_id", "key", name="uq_config_entry_key"),
    )

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    mode_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("project_modes.id", ondelete="CASCADE"), nullable=False
    )
    key: Mapped[str] = mapped_column(String(255), nullable=False)
    value_type: Mapped[ConfigValueTypeEnum] = mapped_column(Enum(ConfigValueTypeEnum), nullable=False)
    default_value: Mapped[dict] = mapped_column(JSON, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
