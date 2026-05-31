from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from app.models.support_conversation import ConversationStatusEnum
from app.models.support_message import SenderTypeEnum


class ConversationCreate(BaseModel):
    subject: str
    message: str
    install_id: str | None = None


class ConversationResponse(BaseModel):
    id: UUID
    project_id: UUID
    mode_id: UUID
    device_id: UUID
    subject: str
    status: ConversationStatusEnum
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class MessageCreate(BaseModel):
    body: str
    attachment_url: str | None = None


class MessageResponse(BaseModel):
    id: UUID
    conversation_id: UUID
    sender_type: SenderTypeEnum
    sender_id: UUID | None = None
    body: str
    attachment_url: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}
