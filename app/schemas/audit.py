from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from app.schemas.common import CursorPage


class AuditLogResponse(BaseModel):
    id: int
    org_id: UUID
    actor_user_id: UUID
    action: str
    resource_type: str
    resource_id: str | None = None
    meta: dict = {}
    ip: str | None = None
    user_agent: str | None = None
    at: datetime

    model_config = {"from_attributes": True}


class AuditListResponse(CursorPage[AuditLogResponse]):
    pass
