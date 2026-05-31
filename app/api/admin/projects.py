from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import write_audit
from app.core.db import get_db
from app.core.deps import get_current_user, require_role
from app.models.org_member import OrgMember, RoleEnum
from app.models.organization import Organization
from app.models.project import Project, ProjectMode
from app.models.user import User
from app.schemas.project import ModeCreate, ModeResponse, ProjectCreate, ProjectResponse, ProjectUpdate

router = APIRouter()


@router.post("/{org_slug}/projects", response_model=ProjectResponse, status_code=201)
async def create_project(
    org_slug: str,
    body: ProjectCreate,
    request: Request,
    current_user: User = Depends(get_current_user),
    _member: OrgMember = Depends(require_role(RoleEnum.editor)),
    db: AsyncSession = Depends(get_db),
) -> Project:
    result = await db.execute(select(Organization).where(Organization.slug == org_slug))
    org = result.scalar_one_or_none()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    existing = await db.execute(
        select(Project).where(Project.org_id == org.id, Project.slug == body.slug)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Project slug already exists in this org")

    project = Project(
        org_id=org.id,
        name=body.name,
        slug=body.slug,
        bundle_id_ios=body.bundle_id_ios,
        bundle_id_android=body.bundle_id_android,
        created_by=current_user.id,
    )
    db.add(project)
    await db.flush()

    await write_audit(
        db, org.id, current_user.id, "project.created", "project", str(project.id), request=request
    )
    return project


@router.get("/{org_slug}/projects", response_model=list[ProjectResponse])
async def list_projects(
    org_slug: str,
    _member: OrgMember = Depends(require_role(RoleEnum.viewer)),
    db: AsyncSession = Depends(get_db),
) -> list[Project]:
    result = await db.execute(select(Organization).where(Organization.slug == org_slug))
    org = result.scalar_one_or_none()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    result = await db.execute(
        select(Project).where(Project.org_id == org.id).order_by(Project.created_at.desc())
    )
    return list(result.scalars().all())


@router.get("/{org_slug}/projects/{proj_slug}", response_model=ProjectResponse)
async def get_project(
    org_slug: str,
    proj_slug: str,
    _member: OrgMember = Depends(require_role(RoleEnum.viewer)),
    db: AsyncSession = Depends(get_db),
) -> Project:
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
    return project


@router.patch("/{org_slug}/projects/{proj_slug}", response_model=ProjectResponse)
async def update_project(
    org_slug: str,
    proj_slug: str,
    body: ProjectUpdate,
    request: Request,
    current_user: User = Depends(get_current_user),
    _member: OrgMember = Depends(require_role(RoleEnum.editor)),
    db: AsyncSession = Depends(get_db),
) -> Project:
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

    if body.name is not None:
        project.name = body.name
    if body.slug is not None:
        dup = await db.execute(
            select(Project).where(Project.org_id == org.id, Project.slug == body.slug, Project.id != project.id)
        )
        if dup.scalar_one_or_none():
            raise HTTPException(status_code=409, detail="Slug already taken")
        project.slug = body.slug
    if body.bundle_id_ios is not None:
        project.bundle_id_ios = body.bundle_id_ios
    if body.bundle_id_android is not None:
        project.bundle_id_android = body.bundle_id_android

    await db.flush()
    await write_audit(
        db, org.id, current_user.id, "project.updated", "project", str(project.id), request=request
    )
    return project


@router.delete("/{org_slug}/projects/{proj_slug}", status_code=204)
async def delete_project(
    org_slug: str,
    proj_slug: str,
    request: Request,
    current_user: User = Depends(get_current_user),
    _member: OrgMember = Depends(require_role(RoleEnum.admin)),
    db: AsyncSession = Depends(get_db),
) -> None:
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

    await write_audit(
        db, org.id, current_user.id, "project.deleted", "project", str(project.id), request=request
    )
    await db.delete(project)
    await db.flush()


@router.post("/{org_slug}/projects/{proj_slug}/modes", response_model=ModeResponse, status_code=201)
async def create_mode(
    org_slug: str,
    proj_slug: str,
    body: ModeCreate,
    request: Request,
    current_user: User = Depends(get_current_user),
    _member: OrgMember = Depends(require_role(RoleEnum.editor)),
    db: AsyncSession = Depends(get_db),
) -> ProjectMode:
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

    mode = ProjectMode(project_id=project.id, name=body.name, is_default=body.is_default)
    db.add(mode)
    await db.flush()

    await write_audit(
        db, org.id, current_user.id, "mode.created", "project_mode", str(mode.id), request=request
    )
    return mode


@router.delete("/{org_slug}/projects/{proj_slug}/modes/{mode_id}", status_code=204)
async def delete_mode(
    org_slug: str,
    proj_slug: str,
    mode_id: UUID,
    request: Request,
    current_user: User = Depends(get_current_user),
    _member: OrgMember = Depends(require_role(RoleEnum.admin)),
    db: AsyncSession = Depends(get_db),
) -> None:
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

    result = await db.execute(
        select(ProjectMode).where(ProjectMode.id == mode_id, ProjectMode.project_id == project.id)
    )
    mode = result.scalar_one_or_none()
    if not mode:
        raise HTTPException(status_code=404, detail="Mode not found")

    await write_audit(
        db, org.id, current_user.id, "mode.deleted", "project_mode", str(mode_id), request=request
    )
    await db.delete(mode)
    await db.flush()
