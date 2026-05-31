from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.sdk_auth import get_sdk_session
from app.core.sdk_device import get_or_create_session_device
from app.models.rating_event import RatingActionEnum, RatingEvent
from app.models.rating_rule import RatingRule
from app.schemas.rating import RatingCheckResponse, RatingEventResponse

router = APIRouter()


@router.get("/rating/check", response_model=RatingCheckResponse)
async def check_rating(
    session: dict[str, Any] = Depends(get_sdk_session),
    db: AsyncSession = Depends(get_db),
) -> RatingCheckResponse:
    device = await get_or_create_session_device(db, session)
    now = datetime.now(timezone.utc)

    result = await db.execute(
        select(RatingRule).where(
            RatingRule.project_id == session["project_id"],
            RatingRule.mode_id == session["mode_id"],
            RatingRule.is_active.is_(True),
        )
    )
    rule = result.scalar_one_or_none()
    if not rule:
        return RatingCheckResponse(should_show=False)

    if (now - device.first_seen_at).days < rule.min_days_since_install:
        return RatingCheckResponse(should_show=False)

    result = await db.execute(
        select(RatingEvent).where(
            RatingEvent.device_id == device.id,
            RatingEvent.project_id == session["project_id"],
        ).order_by(RatingEvent.created_at.desc()).limit(1)
    )
    last_event = result.scalar_one_or_none()
    if last_event:
        if last_event.action == RatingActionEnum.accepted:
            return RatingCheckResponse(should_show=False)
        if last_event.action == RatingActionEnum.declined and rule.exclude_negative_events:
            return RatingCheckResponse(should_show=False)
        if now < last_event.created_at + timedelta(days=rule.cooldown_days):
            return RatingCheckResponse(should_show=False)

    platform = session.get("platform", "")
    store_url = rule.store_url_ios if platform == "ios" else rule.store_url_android
    return RatingCheckResponse(should_show=True, store_url=store_url)


@router.post("/rating/event", response_model=RatingEventResponse, status_code=201)
async def create_rating_event(
    body: dict[str, str],
    session: dict[str, Any] = Depends(get_sdk_session),
    db: AsyncSession = Depends(get_db),
) -> RatingEvent:
    device = await get_or_create_session_device(db, session)
    action = RatingActionEnum(body.get("action", "shown"))
    event = RatingEvent(device_id=device.id, project_id=session["project_id"], action=action)
    db.add(event)
    await db.flush()
    return event
