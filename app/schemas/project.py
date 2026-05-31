from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class ProjectCreate(BaseModel):
    name: str
    slug: str
    bundle_id_ios: str | None = None
    bundle_id_android: str | None = None


class ProjectUpdate(BaseModel):
    name: str | None = None
    slug: str | None = None
    bundle_id_ios: str | None = None
    bundle_id_android: str | None = None


class ModeCreate(BaseModel):
    name: str
    is_default: bool = False


class ModeResponse(BaseModel):
    id: UUID
    project_id: UUID
    name: str
    is_default: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class ProjectResponse(BaseModel):
    id: UUID
    org_id: UUID
    name: str
    slug: str
    bundle_id_ios: str | None = None
    bundle_id_android: str | None = None
    icon_url: str | None = None
    created_by: UUID
    created_at: datetime
    modes: list[ModeResponse] = []

    model_config = {"from_attributes": True}
