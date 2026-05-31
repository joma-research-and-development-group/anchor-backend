from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    slug: str = Field(min_length=1, max_length=100, pattern=r"^[a-z0-9][a-z0-9-]*$")
    bundle_id_ios: str | None = Field(default=None, max_length=255)
    bundle_id_android: str | None = Field(default=None, max_length=255)


class ProjectUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    slug: str | None = Field(default=None, min_length=1, max_length=100, pattern=r"^[a-z0-9][a-z0-9-]*$")
    bundle_id_ios: str | None = Field(default=None, max_length=255)
    bundle_id_android: str | None = Field(default=None, max_length=255)


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
