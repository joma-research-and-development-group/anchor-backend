from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from app.models.rating_event import RatingActionEnum


class RatingRuleUpsert(BaseModel):
    mode_id: UUID
    min_sessions: int = 5
    min_days_since_install: int = 7
    cooldown_days: int = 30
    exclude_negative_events: bool = True
    is_active: bool = True
    store_url_ios: str | None = None
    store_url_android: str | None = None


class RatingRuleResponse(BaseModel):
    id: UUID
    project_id: UUID
    mode_id: UUID
    min_sessions: int
    min_days_since_install: int
    cooldown_days: int
    exclude_negative_events: bool
    is_active: bool
    store_url_ios: str | None = None
    store_url_android: str | None = None
    updated_at: datetime

    model_config = {"from_attributes": True}


class RatingEventCreate(BaseModel):
    install_id: str
    action: RatingActionEnum


class RatingEventResponse(BaseModel):
    id: UUID
    device_id: UUID
    project_id: UUID
    action: RatingActionEnum
    created_at: datetime

    model_config = {"from_attributes": True}


class RatingCheckResponse(BaseModel):
    should_show: bool
    store_url: str | None = None
