from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class EventCreate(BaseModel):
    name: str
    properties: dict | None = None
    session_id: str | None = None
    created_at: datetime | None = None


class EventBatchCreate(BaseModel):
    install_id: str
    events: list[EventCreate]


class SessionAction(BaseModel):
    install_id: str
    session_id: str
    action: str  # "start" or "end"


class EventResponse(BaseModel):
    id: int
    project_id: UUID
    mode_id: UUID
    device_id: UUID | None = None
    name: str
    properties: dict | None = None
    session_id: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class EventAggregation(BaseModel):
    name: str
    count: int


class EventDailyCount(BaseModel):
    date: str
    count: int
