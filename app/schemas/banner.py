from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class BannerCreate(BaseModel):
    mode_id: UUID
    name: str
    title: str
    body: str
    image_url: str | None = None
    cta_label: str
    cta_url: str
    target_conditions: dict | None = None
    starts_at: datetime
    ends_at: datetime | None = None
    frequency_cap: int = 1
    priority: int = 0
    is_active: bool = True


class BannerUpdate(BaseModel):
    name: str | None = None
    title: str | None = None
    body: str | None = None
    image_url: str | None = None
    cta_label: str | None = None
    cta_url: str | None = None
    target_conditions: dict | None = None
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    frequency_cap: int | None = None
    priority: int | None = None
    is_active: bool | None = None


class BannerResponse(BaseModel):
    id: UUID
    project_id: UUID
    mode_id: UUID
    name: str
    title: str
    body: str
    image_url: str | None = None
    cta_label: str
    cta_url: str
    target_conditions: dict | None = None
    starts_at: datetime
    ends_at: datetime | None = None
    frequency_cap: int
    priority: int
    is_active: bool
    total_impressions: int
    total_clicks: int
    created_by: UUID
    created_at: datetime

    model_config = {"from_attributes": True}


class BannerImpressionCreate(BaseModel):
    install_id: str
