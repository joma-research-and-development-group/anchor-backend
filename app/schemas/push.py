from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from app.models.push_credential import PushProviderEnum
from app.models.push_campaign import CampaignStatusEnum


class PushCredentialCreate(BaseModel):
    mode_id: UUID
    platform: str
    provider: PushProviderEnum
    name: str
    credentials: dict
    is_default: bool = False


class PushCredentialResponse(BaseModel):
    id: UUID
    project_id: UUID
    mode_id: UUID
    platform: str
    provider: PushProviderEnum
    name: str
    is_default: bool
    created_by: UUID
    created_at: datetime

    model_config = {"from_attributes": True}


class DeviceRegister(BaseModel):
    install_id: str
    platform: str
    os_version: str | None = None
    device_model: str | None = None
    app_version: str | None = None
    build_number: int | None = None
    locale: str | None = None
    timezone: str | None = None
    country: str | None = None
    user_ref: str | None = None
    push_token: str | None = None
    push_provider: PushProviderEnum | None = None
    attributes: dict | None = None


class DeviceResponse(BaseModel):
    id: UUID
    project_id: UUID
    mode_id: UUID
    install_id: str
    user_ref: str | None = None
    push_token: str | None = None
    push_provider: PushProviderEnum | None = None
    platform: str
    os_version: str | None = None
    device_model: str | None = None
    app_version: str | None = None
    build_number: int | None = None
    locale: str | None = None
    timezone: str | None = None
    country: str | None = None
    first_seen_at: datetime
    last_seen_at: datetime
    last_active_at: datetime
    attributes: dict | None = None

    model_config = {"from_attributes": True}


class PushCampaignCreate(BaseModel):
    mode_id: UUID
    title: str
    body: str
    data: dict | None = None
    target_type: str = "all"
    target_value: str | None = None
    scheduled_at: datetime | None = None


class PushCampaignResponse(BaseModel):
    id: UUID
    project_id: UUID
    mode_id: UUID
    title: str
    body: str
    data: dict | None = None
    status: CampaignStatusEnum
    target_type: str
    target_value: str | None = None
    scheduled_at: datetime | None = None
    sent_at: datetime | None = None
    total_sent: int
    total_opened: int
    created_by: UUID
    created_at: datetime

    model_config = {"from_attributes": True}


class PushTokenUpdate(BaseModel):
    install_id: str
    push_token: str
    push_provider: PushProviderEnum


class TopicAction(BaseModel):
    install_id: str
    topic: str
