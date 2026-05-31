from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class OrgCreate(BaseModel):
    name: str
    slug: str


class OrgUpdate(BaseModel):
    name: str | None = None
    slug: str | None = None


class OrgResponse(BaseModel):
    id: UUID
    name: str
    slug: str
    created_by: UUID
    created_at: datetime

    model_config = {"from_attributes": True}


class OrgListResponse(BaseModel):
    items: list[OrgResponse]
