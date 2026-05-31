from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import write_audit
from app.core.db import get_db
from app.core.deps import get_current_user, require_role
from app.models.maintenance_window import MaintenanceWindow
from app.models.org_member import OrgMember, RoleEnum
from app.models.organization import Organization
from app.models.project import Project, ProjectMode
from app.models.user import User
from app.schemas.maintenance import MaintenanceCreate, MaintenanceResponse, MaintenanceUpdate

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


@router.get("/{org_slug}/projects/{proj_slug}/maintenance", response_model=list[MaintenanceResponse])
async def list_maintenance(
    org_slug: str,
    proj_slug: str,
    _member: OrgMember = Depends(require_role(RoleEnum.viewer)),
    db: AsyncSession = Depends(get_db),
) -> list[MaintenanceWindow]:
    _, project = await _get_project(db, org_slug, proj_slug)
    result = await db.execute(
        select(MaintenanceWindow).where(MaintenanceWindow.project_id == project.id).order_by(MaintenanceWindow.created_at.desc())
    )
    return list(result.scalars().all())


@router.post("/{org_slug}/projects/{proj_slug}/maintenance", response_model=MaintenanceResponse, status_code=201)
async def create_maintenance(
    org_slug: str,
    proj_slug: str,
    body: MaintenanceCreate,
    request: Request,
    current_user: User = Depends(get_current_user),
    _member: OrgMember = Depends(require_role(RoleEnum.editor)),
    db: AsyncSession = Depends(get_db),
) -> MaintenanceWindow:
    org, project = await _get_project(db, org_slug, proj_slug)
    # Verify mode
    result = await db.execute(
        select(ProjectMode).where(ProjectMode.id == body.mode_id, ProjectMode.project_id == project.id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Mode not found")
    window = MaintenanceWindow(
        project_id=project.id,
        mode_id=body.mode_id,
        title=body.title,
        message=body.message,
        starts_at=body.starts_at,
        ends_at=body.ends_at,
        allow_read_only=body.allow_read_only,
        created_by=current_user.id,
    )
    db.add(window)
    await db.flush()
    await write_audit(db, org.id, current_user.id, "maintenance.created", "maintenance_window", str(window.id), request=request)
    return window


@router.patch("/{org_slug}/projects/{proj_slug}/maintenance/{id}", response_model=MaintenanceResponse)
async def update_maintenance(
    org_slug: str,
    proj_slug: str,
    id: UUID,
    body: MaintenanceUpdate,
    request: Request,
    current_user: User = Depends(get_current_user),
    _member: OrgMember = Depends(require_role(RoleEnum.editor)),
    db: AsyncSession = Depends(get_db),
) -> MaintenanceWindow:
    org, project = await _get_project(db, org_slug, proj_slug)
    result = await db.execute(
        select(MaintenanceWindow).where(MaintenanceWindow.id == id, MaintenanceWindow.project_id == project.id)
    )
    window = result.scalar_one_or_none()
    if not window:
        raise HTTPException(status_code=404, detail="Maintenance window not found")
    if body.title is not None:
        window.title = body.title
    if body.message is not None:
        window.message = body.message
    if body.starts_at is not None:
        window.starts_at = body.starts_at
    if body.ends_at is not None:
        window.ends_at = body.ends_at
    if body.allow_read_only is not None:
        window.allow_read_only = body.allow_read_only
    if body.active is not None:
        window.active = body.active
    await db.flush()
    await write_audit(db, org.id, current_user.id, "maintenance.updated", "maintenance_window", str(id), request=request)
    return window


@router.delete("/{org_slug}/projects/{proj_slug}/maintenance/{id}", status_code=204)
async def delete_maintenance(
    org_slug: str,
    proj_slug: str,
    id: UUID,
    request: Request,
    current_user: User = Depends(get_current_user),
    _member: OrgMember = Depends(require_role(RoleEnum.editor)),
    db: AsyncSession = Depends(get_db),
) -> None:
    org, project = await _get_project(db, org_slug, proj_slug)
    result = await db.execute(
        select(MaintenanceWindow).where(MaintenanceWindow.id == id, MaintenanceWindow.project_id == project.id)
    )
    window = result.scalar_one_or_none()
    if not window:
        raise HTTPException(status_code=404, detail="Maintenance window not found")
    await write_audit(db, org.id, current_user.id, "maintenance.deleted", "maintenance_window", str(id), request=request)
    await db.delete(window)
    await db.flush()
