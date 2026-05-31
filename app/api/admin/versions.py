from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import write_audit
from app.core.db import get_db
from app.core.deps import get_current_user, require_role
from app.models.app_version import AppVersion, PlatformEnum
from app.models.org_member import OrgMember, RoleEnum
from app.models.organization import Organization
from app.models.project import Project, ProjectMode
from app.models.user import User
from app.schemas.version import AppVersionCreate, AppVersionResponse

router = APIRouter()


async def _get_project(db: AsyncSession, org_slug: str, proj_slug: str) -> tuple[Organization, Project]:
    result = await db.execute(select(Organization).where(Organization.slug == org_slug))
    org = result.scalar_one_or_none()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    result = await db.execute(
        select(Project).where(Project.org_id == org.id, Project.slug == proj_slug)
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return org, project


@router.get("/{org_slug}/projects/{proj_slug}/versions", response_model=list[AppVersionResponse])
async def list_versions(
    org_slug: str,
    proj_slug: str,
    mode_id: UUID | None = Query(None),
    platform: PlatformEnum | None = Query(None),
    _member: OrgMember = Depends(require_role(RoleEnum.viewer)),
    db: AsyncSession = Depends(get_db),
) -> list[AppVersion]:
    _, project = await _get_project(db, org_slug, proj_slug)
    stmt = select(AppVersion).where(AppVersion.project_id == project.id)
    if mode_id:
        stmt = stmt.where(AppVersion.mode_id == mode_id)
    if platform:
        stmt = stmt.where(AppVersion.platform == platform)
    stmt = stmt.order_by(AppVersion.created_at.desc())
    result = await db.execute(stmt)
    return list(result.scalars().all())


@router.post("/{org_slug}/projects/{proj_slug}/versions", response_model=AppVersionResponse, status_code=201)
async def create_version(
    org_slug: str,
    proj_slug: str,
    body: AppVersionCreate,
    request: Request,
    current_user: User = Depends(get_current_user),
    _member: OrgMember = Depends(require_role(RoleEnum.editor)),
    db: AsyncSession = Depends(get_db),
) -> AppVersion:
    org, project = await _get_project(db, org_slug, proj_slug)
    # Verify mode belongs to project
    result = await db.execute(
        select(ProjectMode).where(ProjectMode.id == body.mode_id, ProjectMode.project_id == project.id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Mode not found")
    version = AppVersion(
        project_id=project.id,
        mode_id=body.mode_id,
        platform=body.platform,
        semver=body.semver,
        build_number=body.build_number,
        released_at=body.released_at,
        notes=body.notes,
        created_by=current_user.id,
    )
    db.add(version)
    await db.flush()
    await write_audit(db, org.id, current_user.id, "version.created", "app_version", str(version.id), request=request)
    return version


@router.delete("/{org_slug}/projects/{proj_slug}/versions/{version_id}", status_code=204)
async def delete_version(
    org_slug: str,
    proj_slug: str,
    version_id: UUID,
    request: Request,
    current_user: User = Depends(get_current_user),
    _member: OrgMember = Depends(require_role(RoleEnum.editor)),
    db: AsyncSession = Depends(get_db),
) -> None:
    org, project = await _get_project(db, org_slug, proj_slug)
    result = await db.execute(
        select(AppVersion).where(AppVersion.id == version_id, AppVersion.project_id == project.id)
    )
    version = result.scalar_one_or_none()
    if not version:
        raise HTTPException(status_code=404, detail="Version not found")
    await write_audit(db, org.id, current_user.id, "version.deleted", "app_version", str(version_id), request=request)
    await db.delete(version)
    await db.flush()
