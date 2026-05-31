from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from app.models.api_key import ApiKeyStatusEnum


class ApiKeyCreate(BaseModel):
    name: str


class ApiKeyResponse(BaseModel):
    id: UUID
    project_id: UUID
    mode_id: UUID
    version_id: UUID
    name: str
    key_prefix: str
    status: ApiKeyStatusEnum
    created_at: datetime
    revoked_at: datetime | None = None

    model_config = {"from_attributes": True}


class ApiKeyCreatedResponse(ApiKeyResponse):
    raw_secret: str


class ApiKeyRevoke(BaseModel):
    reason: str | None = None
