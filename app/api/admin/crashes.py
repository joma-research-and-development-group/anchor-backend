from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.deps import require_role
from app.models.crash_group import CrashGroup, CrashGroupStatusEnum
from app.models.crash_report import CrashReport
from app.models.org_member import OrgMember, RoleEnum
from app.models.organization import Organization
from app.models.project import Project
from app.schemas.crash import CrashGroupResponse, CrashGroupUpdate, CrashReportResponse

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


@router.get("/{org_slug}/projects/{proj_slug}/crashes", response_model=list[CrashGroupResponse])
async def list_crash_groups(
    org_slug: str,
    proj_slug: str,
    status: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    _member: OrgMember = Depends(require_role(RoleEnum.viewer)),
    db: AsyncSession = Depends(get_db),
) -> list[CrashGroup]:
    project = await _get_project(db, org_slug, proj_slug)
    q = select(CrashGroup).where(CrashGroup.project_id == project.id)
    if status:
        q = q.where(CrashGroup.status == CrashGroupStatusEnum(status))
    q = q.order_by(CrashGroup.last_seen_at.desc()).limit(limit).offset(offset)
    result = await db.execute(q)
    return list(result.scalars().all())


@router.get("/{org_slug}/projects/{proj_slug}/crashes/{group_id}", response_model=CrashGroupResponse)
async def get_crash_group(
    org_slug: str,
    proj_slug: str,
    group_id: UUID,
    _member: OrgMember = Depends(require_role(RoleEnum.viewer)),
    db: AsyncSession = Depends(get_db),
) -> CrashGroup:
    project = await _get_project(db, org_slug, proj_slug)
    result = await db.execute(select(CrashGroup).where(CrashGroup.id == group_id, CrashGroup.project_id == project.id))
    group = result.scalar_one_or_none()
    if not group:
        raise HTTPException(status_code=404, detail="Crash group not found")
    return group


@router.get("/{org_slug}/projects/{proj_slug}/crashes/{group_id}/reports", response_model=list[CrashReportResponse])
async def list_crash_reports(
    org_slug: str,
    proj_slug: str,
    group_id: UUID,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    _member: OrgMember = Depends(require_role(RoleEnum.viewer)),
    db: AsyncSession = Depends(get_db),
) -> list[CrashReport]:
    project = await _get_project(db, org_slug, proj_slug)
    result = await db.execute(
        select(CrashReport)
        .where(CrashReport.group_id == group_id, CrashReport.project_id == project.id)
        .order_by(CrashReport.created_at.desc())
        .limit(limit).offset(offset)
    )
    return list(result.scalars().all())


@router.patch("/{org_slug}/projects/{proj_slug}/crashes/{group_id}", response_model=CrashGroupResponse)
async def update_crash_group(
    org_slug: str,
    proj_slug: str,
    group_id: UUID,
    body: CrashGroupUpdate,
    _member: OrgMember = Depends(require_role(RoleEnum.editor)),
    db: AsyncSession = Depends(get_db),
) -> CrashGroup:
    project = await _get_project(db, org_slug, proj_slug)
    result = await db.execute(select(CrashGroup).where(CrashGroup.id == group_id, CrashGroup.project_id == project.id))
    group = result.scalar_one_or_none()
    if not group:
        raise HTTPException(status_code=404, detail="Crash group not found")
    for field, value in body.model_dump(exclude_unset=True).items():
        if field == "status":
            setattr(group, field, CrashGroupStatusEnum(value))
        else:
            setattr(group, field, value)
    await db.flush()
    return group
