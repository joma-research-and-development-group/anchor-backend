from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class MaintenanceCreate(BaseModel):
    title: str
    message: str
    starts_at: datetime
    ends_at: datetime | None = None
    allow_read_only: bool = False
    mode_id: UUID


class MaintenanceUpdate(BaseModel):
    title: str | None = None
    message: str | None = None
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    allow_read_only: bool | None = None
    active: bool | None = None


class MaintenanceResponse(BaseModel):
    id: UUID
    project_id: UUID
    mode_id: UUID
    title: str
    message: str
    starts_at: datetime
    ends_at: datetime | None = None
    allow_read_only: bool
    active: bool
    created_by: UUID
    created_at: datetime

    model_config = {"from_attributes": True}
