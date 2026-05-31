from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from app.models.announcement import AnnouncementTypeEnum


class AnnouncementCreate(BaseModel):
    mode_id: UUID
    title: str
    body: str
    type: AnnouncementTypeEnum
    action_url: str | None = None
    image_url: str | None = None
    target_conditions: dict | None = None
    starts_at: datetime
    ends_at: datetime | None = None
    priority: int = 0
    is_active: bool = True


class AnnouncementUpdate(BaseModel):
    title: str | None = None
    body: str | None = None
    type: AnnouncementTypeEnum | None = None
    action_url: str | None = None
    image_url: str | None = None
    target_conditions: dict | None = None
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    priority: int | None = None
    is_active: bool | None = None


class AnnouncementResponse(BaseModel):
    id: UUID
    project_id: UUID
    mode_id: UUID
    title: str
    body: str
    type: AnnouncementTypeEnum
    action_url: str | None = None
    image_url: str | None = None
    target_conditions: dict | None = None
    starts_at: datetime
    ends_at: datetime | None = None
    priority: int
    is_active: bool
    created_by: UUID
    created_at: datetime

    model_config = {"from_attributes": True}


class AnnouncementViewResponse(BaseModel):
    id: UUID
    announcement_id: UUID
    device_id: UUID
    seen_at: datetime
    dismissed_at: datetime | None = None

    model_config = {"from_attributes": True}
