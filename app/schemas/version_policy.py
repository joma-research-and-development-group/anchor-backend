from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from app.models.app_version import PlatformEnum


class VersionPolicyUpsert(BaseModel):
    platform: PlatformEnum
    mode_id: UUID
    min_supported_semver: str | None = None
    latest_semver: str | None = None
    store_url: str | None = None
    message_force: str | None = None
    message_soft: str | None = None


class VersionPolicyResponse(BaseModel):
    id: UUID
    project_id: UUID
    mode_id: UUID
    platform: PlatformEnum
    min_supported_semver: str | None = None
    latest_semver: str | None = None
    store_url: str | None = None
    message_force: str | None = None
    message_soft: str | None = None
    updated_at: datetime

    model_config = {"from_attributes": True}
