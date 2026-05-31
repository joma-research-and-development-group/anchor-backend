import uuid

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.user import Base, GUID


class OnboardingSlide(Base):
    __tablename__ = "onboarding_slides"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    flow_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("onboarding_flows.id", ondelete="CASCADE"), nullable=False)
    order: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text(), nullable=False)
    image_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    bg_color: Mapped[str | None] = mapped_column(String(20), nullable=True)
    action_label: Mapped[str | None] = mapped_column(String(100), nullable=True)
    action_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
