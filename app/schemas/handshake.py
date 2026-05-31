from datetime import datetime
from typing import Any

from pydantic import BaseModel

from app.models.app_version import PlatformEnum


class HandshakeRequest(BaseModel):
    app_version: str
    build_number: int
    platform: PlatformEnum
    os_version: str | None = None
    device_model: str | None = None
    locale: str | None = None
    timezone: str | None = None
    anchor_sdk_version: str | None = None


class SessionInfo(BaseModel):
    jwt: str
    token: str
    expires_at: datetime
    project_id: str
    mode_id: str
    version_id: str
    platform: str


class VersionInfo(BaseModel):
    action: str  # ok, soft_update, force_update
    store_url: str | None = None
    message: str | None = None
    latest: str | None = None


class MaintenanceInfo(BaseModel):
    active: bool
    title: str | None = None
    message: str | None = None


class HandshakeResponse(BaseModel):
    session: SessionInfo
    version: VersionInfo
    maintenance: MaintenanceInfo
    config_etag: str | None = None
