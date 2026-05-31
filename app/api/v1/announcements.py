from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.sdk_auth import get_sdk_session
from app.core.sdk_device import get_or_create_session_device
from app.models.announcement import Announcement
from app.models.announcement_view import AnnouncementView
from app.schemas.announcement import AnnouncementResponse

router = APIRouter()


@router.get("/announcements", response_model=list[AnnouncementResponse])
async def list_announcements(
    session: dict[str, Any] = Depends(get_sdk_session),
    db: AsyncSession = Depends(get_db),
) -> list[Announcement]:
    now = datetime.now(timezone.utc)
    result = await db.execute(
        select(Announcement).where(
            Announcement.project_id == session["project_id"],
            Announcement.mode_id == session["mode_id"],
            Announcement.is_active.is_(True),
            Announcement.starts_at <= now,
            or_(Announcement.ends_at.is_(None), Announcement.ends_at > now),
        ).order_by(Announcement.priority.desc(), Announcement.created_at.desc())
    )
    return list(result.scalars().all())


@router.post("/announcements/{ann_id}/seen")
async def mark_seen(
    ann_id: UUID,
    session: dict[str, Any] = Depends(get_sdk_session),
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    device = await get_or_create_session_device(db, session)
    result = await db.execute(
        select(AnnouncementView).where(
            AnnouncementView.announcement_id == ann_id,
            AnnouncementView.device_id == device.id,
        )
    )
    if not result.scalar_one_or_none():
        db.add(AnnouncementView(announcement_id=ann_id, device_id=device.id))
        await db.flush()
    return {"status": "seen"}


@router.post("/announcements/{ann_id}/dismiss")
async def dismiss(
    ann_id: UUID,
    session: dict[str, Any] = Depends(get_sdk_session),
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    device = await get_or_create_session_device(db, session)
    result = await db.execute(
        select(AnnouncementView).where(
            AnnouncementView.announcement_id == ann_id,
            AnnouncementView.device_id == device.id,
        )
    )
    view = result.scalar_one_or_none()
    now = datetime.now(timezone.utc)
    if view:
        view.dismissed_at = now
    else:
        db.add(AnnouncementView(announcement_id=ann_id, device_id=device.id, dismissed_at=now))
    await db.flush()
    return {"status": "dismissed"}
