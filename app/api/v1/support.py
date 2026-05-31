from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.sdk_auth import get_sdk_session
from app.core.sdk_device import get_or_create_session_device
from app.models.support_conversation import SupportConversation
from app.models.support_message import SenderTypeEnum, SupportMessage

router = APIRouter()


class ConversationCreateBody(BaseModel):
    subject: str
    message: str


class MessageBody(BaseModel):
    body: str


def _conv_to_dict(conv: SupportConversation) -> dict:
    """SDK Conversation.fromMap expects: id, subject, status, unread_count, created_at, updated_at"""
    return {
        "id": str(conv.id),
        "subject": conv.subject,
        "status": conv.status.value,
        "unread_count": 0,
        "created_at": conv.created_at.isoformat(),
        "updated_at": conv.updated_at.isoformat(),
    }


def _msg_to_dict(msg: SupportMessage) -> dict:
    """SDK Message.fromMap expects: id, conversation_id, body, sender, created_at"""
    return {
        "id": str(msg.id),
        "conversation_id": str(msg.conversation_id),
        "body": msg.body,
        "sender": msg.sender_type.value,
        "created_at": msg.created_at.isoformat(),
    }


@router.get("/support/conversations")
async def list_conversations(
    session: dict[str, Any] = Depends(get_sdk_session),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    """SDK: GET /v1/support/conversations"""
    device = await get_or_create_session_device(db, session)
    result = await db.execute(
        select(SupportConversation).where(
            SupportConversation.device_id == device.id,
            SupportConversation.project_id == session["project_id"],
        ).order_by(SupportConversation.updated_at.desc())
    )
    return [_conv_to_dict(c) for c in result.scalars().all()]


@router.post("/support/conversations", status_code=201)
async def create_conversation(
    body: ConversationCreateBody,
    session: dict[str, Any] = Depends(get_sdk_session),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """SDK: POST /v1/support/conversations with {subject, message}"""
    device = await get_or_create_session_device(db, session)
    conv = SupportConversation(
        project_id=session["project_id"],
        mode_id=session["mode_id"],
        device_id=device.id,
        subject=body.subject,
    )
    db.add(conv)
    await db.flush()
    # Create first message
    msg = SupportMessage(
        conversation_id=conv.id,
        sender_type=SenderTypeEnum.user,
        body=body.message,
    )
    db.add(msg)
    await db.flush()
    return _conv_to_dict(conv)


@router.get("/support/conversations/{conv_id}/messages")
async def list_messages(
    conv_id: UUID,
    session: dict[str, Any] = Depends(get_sdk_session),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    """SDK: GET /v1/support/conversations/{conv_id}/messages"""
    device = await get_or_create_session_device(db, session)
    result = await db.execute(
        select(SupportConversation).where(
            SupportConversation.id == conv_id,
            SupportConversation.device_id == device.id,
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Conversation not found")
    result = await db.execute(
        select(SupportMessage).where(SupportMessage.conversation_id == conv_id).order_by(SupportMessage.created_at.asc())
    )
    return [_msg_to_dict(m) for m in result.scalars().all()]


@router.post("/support/conversations/{conv_id}/messages", status_code=201)
async def send_message(
    conv_id: UUID,
    body: MessageBody,
    session: dict[str, Any] = Depends(get_sdk_session),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """SDK: POST /v1/support/conversations/{conv_id}/messages with {body}"""
    device = await get_or_create_session_device(db, session)
    result = await db.execute(
        select(SupportConversation).where(
            SupportConversation.id == conv_id,
            SupportConversation.device_id == device.id,
        )
    )
    conv = result.scalar_one_or_none()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    msg = SupportMessage(
        conversation_id=conv_id,
        sender_type=SenderTypeEnum.user,
        body=body.body,
    )
    db.add(msg)
    conv.updated_at = datetime.now(timezone.utc)
    await db.flush()
    return _msg_to_dict(msg)


@router.get("/support/unread")
async def get_unread_count(
    session: dict[str, Any] = Depends(get_sdk_session),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """SDK: GET /v1/support/unread → {"count": int}"""
    device = await get_or_create_session_device(db, session)
    # Count admin messages not yet read (messages from admin in device's conversations)
    result = await db.execute(
        select(func.count(SupportMessage.id)).where(
            SupportMessage.conversation_id.in_(
                select(SupportConversation.id).where(SupportConversation.device_id == device.id)
            ),
            SupportMessage.sender_type == SenderTypeEnum.admin,
        )
    )
    count = result.scalar() or 0
    return {"count": count}
