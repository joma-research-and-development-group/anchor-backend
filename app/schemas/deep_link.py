from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class DeepLinkCreate(BaseModel):
    mode_id: UUID
    slug: str
    title: str
    ios_url: str | None = None
    android_url: str | None = None
    web_url: str | None = None
    fallback_url: str
    utm_source: str | None = None
    utm_medium: str | None = None
    utm_campaign: str | None = None


class DeepLinkUpdate(BaseModel):
    title: str | None = None
    ios_url: str | None = None
    android_url: str | None = None
    web_url: str | None = None
    fallback_url: str | None = None
    utm_source: str | None = None
    utm_medium: str | None = None
    utm_campaign: str | None = None


class DeepLinkResponse(BaseModel):
    id: UUID
    project_id: UUID
    mode_id: UUID
    slug: str
    title: str
    ios_url: str | None = None
    android_url: str | None = None
    web_url: str | None = None
    fallback_url: str
    utm_source: str | None = None
    utm_medium: str | None = None
    utm_campaign: str | None = None
    clicks: int
    created_by: UUID
    created_at: datetime

    model_config = {"from_attributes": True}
