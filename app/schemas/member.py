from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr

from app.models.org_member import RoleEnum


class MemberResponse(BaseModel):
    org_id: UUID
    user_id: UUID
    role: RoleEnum
    joined_at: datetime
    email: str | None = None
    full_name: str | None = None

    model_config = {"from_attributes": True}


class MemberUpdate(BaseModel):
    role: RoleEnum


class InvitationCreate(BaseModel):
    email: EmailStr
    role: RoleEnum = RoleEnum.viewer


class InvitationResponse(BaseModel):
    id: UUID
    org_id: UUID
    email: str
    role: RoleEnum
    invited_by: UUID
    expires_at: datetime
    accepted_at: datetime | None = None
    created_at: datetime

    model_config = {"from_attributes": True}
