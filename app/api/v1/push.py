from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.sdk_auth import get_sdk_session
from app.core.sdk_device import get_or_create_session_device
from app.models.push_credential import PushProviderEnum

router = APIRouter()


@router.post("/push/token")
async def update_push_token(
    body: dict[str, Any],
    session: dict[str, Any] = Depends(get_sdk_session),
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    device = await get_or_create_session_device(db, session)
    token = body.get("token") or body.get("push_token")
    if token:
        device.push_token = token
        device.push_provider = PushProviderEnum.fcm
    if body.get("platform"):
        device.platform = body["platform"]
    await db.flush()
    return {"status": "ok", "token": token or "", "platform": device.platform}


async def _topic_update(db: AsyncSession, session: dict[str, Any], topic: str, add: bool) -> None:
    device = await get_or_create_session_device(db, session)
    attrs = dict(device.attributes or {})
    topics = list(attrs.get("topics", []))
    if add and topic not in topics:
        topics.append(topic)
    if not add and topic in topics:
        topics.remove(topic)
    attrs["topics"] = topics
    device.attributes = attrs
    await db.flush()


@router.post("/push/topics/subscribe")
async def subscribe_topic(
    body: dict[str, str],
    session: dict[str, Any] = Depends(get_sdk_session),
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    topic = body.get("topic", "")
    await _topic_update(db, session, topic, add=True)
    return {"status": "subscribed", "topic": topic}


@router.post("/push/topics/unsubscribe")
async def unsubscribe_topic(
    body: dict[str, str],
    session: dict[str, Any] = Depends(get_sdk_session),
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    topic = body.get("topic", "")
    await _topic_update(db, session, topic, add=False)
    return {"status": "unsubscribed", "topic": topic}
