import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.models.user import Base, GUID


class BannerImpression(Base):
    __tablename__ = "banner_impressions"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    banner_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("banner_campaigns.id", ondelete="CASCADE"), nullable=False)
    device_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("devices.id", ondelete="CASCADE"), nullable=False)
    shown_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    clicked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
