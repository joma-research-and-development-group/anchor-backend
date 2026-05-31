from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.sdk_auth import get_sdk_session
from app.core.sdk_device import get_or_create_session_device
from app.models.banner import BannerCampaign
from app.models.banner_impression import BannerImpression
from app.schemas.banner import BannerResponse

router = APIRouter()


@router.get("/banners", response_model=list[BannerResponse])
async def list_banners(
    session: dict[str, Any] = Depends(get_sdk_session),
    db: AsyncSession = Depends(get_db),
) -> list[BannerCampaign]:
    now = datetime.now(timezone.utc)
    device = await get_or_create_session_device(db, session)
    result = await db.execute(
        select(BannerCampaign).where(
            BannerCampaign.project_id == session["project_id"],
            BannerCampaign.mode_id == session["mode_id"],
            BannerCampaign.is_active.is_(True),
            BannerCampaign.starts_at <= now,
            or_(BannerCampaign.ends_at.is_(None), BannerCampaign.ends_at > now),
        ).order_by(BannerCampaign.priority.desc())
    )
    banners = list(result.scalars().all())
    eligible = []
    for banner in banners:
        imp_count = await db.execute(
            select(func.count()).select_from(BannerImpression).where(
                BannerImpression.banner_id == banner.id,
                BannerImpression.device_id == device.id,
            )
        )
        if (imp_count.scalar() or 0) < banner.frequency_cap:
            eligible.append(banner)
    return eligible


@router.post("/banners/{banner_id}/impression")
async def record_impression(
    banner_id: UUID,
    session: dict[str, Any] = Depends(get_sdk_session),
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    device = await get_or_create_session_device(db, session)
    result = await db.execute(
        select(BannerCampaign).where(
            BannerCampaign.id == banner_id, BannerCampaign.project_id == session["project_id"]
        )
    )
    banner = result.scalar_one_or_none()
    if not banner:
        raise HTTPException(status_code=404, detail="Banner not found")
    db.add(BannerImpression(banner_id=banner_id, device_id=device.id))
    banner.total_impressions += 1
    await db.flush()
    return {"status": "recorded"}


@router.post("/banners/{banner_id}/click")
async def record_click(
    banner_id: UUID,
    session: dict[str, Any] = Depends(get_sdk_session),
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    device = await get_or_create_session_device(db, session)
    result = await db.execute(
        select(BannerImpression).where(
            BannerImpression.banner_id == banner_id,
            BannerImpression.device_id == device.id,
            BannerImpression.clicked_at.is_(None),
        ).order_by(BannerImpression.shown_at.desc())
    )
    impression = result.scalars().first()
    if impression:
        impression.clicked_at = datetime.now(timezone.utc)
    result = await db.execute(
        select(BannerCampaign).where(
            BannerCampaign.id == banner_id, BannerCampaign.project_id == session["project_id"]
        )
    )
    banner = result.scalar_one_or_none()
    if not banner:
        raise HTTPException(status_code=404, detail="Banner not found")
    banner.total_clicks += 1
    await db.flush()
    return {"status": "clicked"}
