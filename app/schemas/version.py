from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from app.models.app_version import PlatformEnum


class AppVersionCreate(BaseModel):
    semver: str
    build_number: int
    platform: PlatformEnum
    mode_id: UUID
    released_at: datetime | None = None
    notes: str | None = None


class AppVersionResponse(BaseModel):
    id: UUID
    project_id: UUID
    mode_id: UUID
    platform: PlatformEnum
    semver: str
    build_number: int
    released_at: datetime | None = None
    notes: str | None = None
    created_by: UUID
    created_at: datetime

    model_config = {"from_attributes": True}
