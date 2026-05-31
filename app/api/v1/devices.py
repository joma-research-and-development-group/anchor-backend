from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.sdk_auth import get_sdk_session
from app.core.sdk_device import get_or_create_session_device
from app.models.device import Device
from app.models.push_credential import PushProviderEnum
from app.schemas.push import DeviceResponse

router = APIRouter()


@router.post("/devices/register", response_model=DeviceResponse)
async def register_device(
    body: dict[str, Any],
    session: dict[str, Any] = Depends(get_sdk_session),
    db: AsyncSession = Depends(get_db),
) -> Device:
    device = await get_or_create_session_device(db, session)
    now = datetime.now(timezone.utc)
    device.last_seen_at = now
    device.last_active_at = now
    if body.get("platform"):
        device.platform = body["platform"]
    if body.get("token"):
        device.push_token = body["token"]
        device.push_provider = PushProviderEnum.fcm
    await db.flush()
    return device


@router.post("/devices/heartbeat", response_model=DeviceResponse)
async def heartbeat(
    body: dict[str, str],
    session: dict[str, Any] = Depends(get_sdk_session),
    db: AsyncSession = Depends(get_db),
) -> Device:
    device = await get_or_create_session_device(db, session)
    device.last_active_at = datetime.now(timezone.utc)
    await db.flush()
    return device
