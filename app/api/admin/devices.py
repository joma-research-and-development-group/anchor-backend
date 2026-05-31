from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.deps import require_role
from app.models.device import Device
from app.models.org_member import OrgMember, RoleEnum
from app.models.organization import Organization
from app.models.project import Project
from app.schemas.push import DeviceResponse

router = APIRouter()


async def _get_project(db: AsyncSession, org_slug: str, proj_slug: str) -> tuple[Organization, Project]:
    result = await db.execute(select(Organization).where(Organization.slug == org_slug))
    org = result.scalar_one_or_none()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    result = await db.execute(select(Project).where(Project.org_id == org.id, Project.slug == proj_slug))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return org, project


@router.get("/{org_slug}/projects/{proj_slug}/devices", response_model=list[DeviceResponse])
async def list_devices(
    org_slug: str,
    proj_slug: str,
    mode_id: UUID | None = Query(None),
    platform: str | None = Query(None),
    cursor: UUID | None = Query(None),
    limit: int = Query(50, le=100),
    _member: OrgMember = Depends(require_role(RoleEnum.viewer)),
    db: AsyncSession = Depends(get_db),
) -> list[Device]:
    _, project = await _get_project(db, org_slug, proj_slug)
    stmt = select(Device).where(Device.project_id == project.id)
    if mode_id:
        stmt = stmt.where(Device.mode_id == mode_id)
    if platform:
        stmt = stmt.where(Device.platform == platform)
    if cursor:
        stmt = stmt.where(Device.id > cursor)
    stmt = stmt.order_by(Device.last_seen_at.desc()).limit(limit)
    result = await db.execute(stmt)
    return list(result.scalars().all())


@router.get("/{org_slug}/projects/{proj_slug}/devices/{device_id}", response_model=DeviceResponse)
async def get_device(
    org_slug: str,
    proj_slug: str,
    device_id: UUID,
    _member: OrgMember = Depends(require_role(RoleEnum.viewer)),
    db: AsyncSession = Depends(get_db),
) -> Device:
    _, project = await _get_project(db, org_slug, proj_slug)
    result = await db.execute(select(Device).where(Device.id == device_id, Device.project_id == project.id))
    device = result.scalar_one_or_none()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    return device
