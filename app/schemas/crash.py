from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class CrashReportCreate(BaseModel):
    install_id: str
    error_type: str
    error_message: str
    stacktrace: str
    app_version: str
    build_number: str
    platform: str
    os_version: str
    device_model: str
    extra: dict | None = None


class CrashReportResponse(BaseModel):
    id: UUID
    project_id: UUID
    mode_id: UUID
    device_id: UUID | None = None
    group_id: UUID | None = None
    error_type: str
    error_message: str
    stacktrace: str
    app_version: str
    build_number: str
    platform: str
    os_version: str
    device_model: str
    extra: dict | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class CrashGroupResponse(BaseModel):
    id: UUID
    project_id: UUID
    mode_id: UUID
    fingerprint: str
    title: str
    first_seen_at: datetime
    last_seen_at: datetime
    count: int
    status: str
    assigned_to: UUID | None = None

    model_config = {"from_attributes": True}


class CrashGroupUpdate(BaseModel):
    status: str | None = None
    assigned_to: UUID | None = None
