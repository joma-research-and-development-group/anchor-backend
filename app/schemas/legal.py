from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from app.models.legal_document import LegalDocTypeEnum


class LegalDocCreate(BaseModel):
    mode_id: UUID
    type: LegalDocTypeEnum
    title: str
    content: str
    version: int = 1
    locale: str
    is_active: bool = True
    requires_acceptance: bool = False
    published_at: datetime | None = None


class LegalDocUpdate(BaseModel):
    title: str | None = None
    content: str | None = None
    is_active: bool | None = None
    requires_acceptance: bool | None = None
    published_at: datetime | None = None


class LegalDocResponse(BaseModel):
    id: UUID
    project_id: UUID
    mode_id: UUID
    type: LegalDocTypeEnum
    title: str
    content: str
    version: int
    locale: str
    is_active: bool
    requires_acceptance: bool
    published_at: datetime | None = None
    created_by: UUID
    created_at: datetime

    model_config = {"from_attributes": True}


class LegalAcceptanceResponse(BaseModel):
    id: UUID
    document_id: UUID
    device_id: UUID
    accepted_at: datetime
    ip: str | None = None

    model_config = {"from_attributes": True}
