from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class LocalizationEntryCreate(BaseModel):
    mode_id: UUID
    key: str
    locale: str
    value: str


class LocalizationEntryUpdate(BaseModel):
    value: str


class LocalizationEntryResponse(BaseModel):
    id: UUID
    project_id: UUID
    mode_id: UUID
    key: str
    locale: str
    value: str
    updated_at: datetime

    model_config = {"from_attributes": True}


class LocalizationBulkItem(BaseModel):
    key: str
    locale: str
    value: str


class LocalizationBulkUpsert(BaseModel):
    mode_id: UUID
    entries: list[LocalizationBulkItem]
