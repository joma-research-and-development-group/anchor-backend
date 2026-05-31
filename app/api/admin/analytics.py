from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import cast, Date, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.deps import require_role
from app.models.event import Event
from app.models.org_member import OrgMember, RoleEnum
from app.models.organization import Organization
from app.models.project import Project
from app.schemas.event import EventAggregation, EventDailyCount

router = APIRouter()


async def _get_project(db: AsyncSession, org_slug: str, proj_slug: str) -> Project:
    result = await db.execute(select(Organization).where(Organization.slug == org_slug))
    org = result.scalar_one_or_none()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    result = await db.execute(select(Project).where(Project.org_id == org.id, Project.slug == proj_slug))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.get("/{org_slug}/projects/{proj_slug}/analytics/events", response_model=list[EventAggregation])
async def event_counts_by_name(
    org_slug: str,
    proj_slug: str,
    days: int = Query(default=30, ge=1, le=365),
    _member: OrgMember = Depends(require_role(RoleEnum.viewer)),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    project = await _get_project(db, org_slug, proj_slug)
    since = datetime.now(timezone.utc) - timedelta(days=days)
    result = await db.execute(
        select(Event.name, func.count().label("count"))
        .where(Event.project_id == project.id, Event.created_at >= since)
        .group_by(Event.name)
        .order_by(func.count().desc())
    )
    return [{"name": r[0], "count": r[1]} for r in result.all()]


@router.get("/{org_slug}/projects/{proj_slug}/analytics/events/daily", response_model=list[EventDailyCount])
async def event_counts_by_day(
    org_slug: str,
    proj_slug: str,
    days: int = Query(default=30, ge=1, le=365),
    _member: OrgMember = Depends(require_role(RoleEnum.viewer)),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    project = await _get_project(db, org_slug, proj_slug)
    since = datetime.now(timezone.utc) - timedelta(days=days)
    result = await db.execute(
        select(cast(Event.created_at, Date).label("date"), func.count().label("count"))
        .where(Event.project_id == project.id, Event.created_at >= since)
        .group_by(cast(Event.created_at, Date))
        .order_by(cast(Event.created_at, Date))
    )
    return [{"date": str(r[0]), "count": r[1]} for r in result.all()]


@router.get("/{org_slug}/projects/{proj_slug}/analytics/sessions")
async def session_stats(
    org_slug: str,
    proj_slug: str,
    _member: OrgMember = Depends(require_role(RoleEnum.viewer)),
    db: AsyncSession = Depends(get_db),
) -> dict:
    project = await _get_project(db, org_slug, proj_slug)
    now = datetime.now(timezone.utc)
    day_ago = now - timedelta(days=1)
    month_ago = now - timedelta(days=30)

    dau_result = await db.execute(
        select(func.count(func.distinct(Event.device_id)))
        .where(Event.project_id == project.id, Event.created_at >= day_ago)
    )
    mau_result = await db.execute(
        select(func.count(func.distinct(Event.device_id)))
        .where(Event.project_id == project.id, Event.created_at >= month_ago)
    )
    return {"dau": dau_result.scalar() or 0, "mau": mau_result.scalar() or 0}
