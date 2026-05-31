from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel

from app.models.config_entry import ConfigValueTypeEnum


class ConfigOverrideCreate(BaseModel):
    conditions: dict[str, Any]
    value: Any
    priority: int = 0


class ConfigOverrideUpdate(BaseModel):
    conditions: dict[str, Any] | None = None
    value: Any | None = None
    priority: int | None = None


class ConfigOverrideResponse(BaseModel):
    id: UUID
    entry_id: UUID
    conditions: dict[str, Any]
    value: Any
    priority: int
    created_at: datetime

    model_config = {"from_attributes": True}


class ConfigEntryCreate(BaseModel):
    key: str
    value_type: ConfigValueTypeEnum
    default_value: Any
    description: str | None = None
    mode_id: UUID


class ConfigEntryUpdate(BaseModel):
    default_value: Any | None = None
    description: str | None = None


class ConfigEntryResponse(BaseModel):
    id: UUID
    project_id: UUID
    mode_id: UUID
    key: str
    value_type: ConfigValueTypeEnum
    default_value: Any
    description: str | None = None
    updated_at: datetime
    overrides: list[ConfigOverrideResponse] = []

    model_config = {"from_attributes": True}
