from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import write_audit
from app.core.db import get_db
from app.core.deps import get_current_user, require_role
from app.models.announcement import Announcement
from app.models.org_member import OrgMember, RoleEnum
from app.models.organization import Organization
from app.models.project import Project, ProjectMode
from app.models.user import User
from app.schemas.announcement import AnnouncementCreate, AnnouncementResponse, AnnouncementUpdate

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


@router.get("/{org_slug}/projects/{proj_slug}/announcements", response_model=list[AnnouncementResponse])
async def list_announcements(
    org_slug: str,
    proj_slug: str,
    _member: OrgMember = Depends(require_role(RoleEnum.viewer)),
    db: AsyncSession = Depends(get_db),
) -> list[Announcement]:
    _, project = await _get_project(db, org_slug, proj_slug)
    result = await db.execute(
        select(Announcement).where(Announcement.project_id == project.id).order_by(Announcement.created_at.desc())
    )
    return list(result.scalars().all())


@router.post("/{org_slug}/projects/{proj_slug}/announcements", response_model=AnnouncementResponse, status_code=201)
async def create_announcement(
    org_slug: str,
    proj_slug: str,
    body: AnnouncementCreate,
    request: Request,
    current_user: User = Depends(get_current_user),
    _member: OrgMember = Depends(require_role(RoleEnum.editor)),
    db: AsyncSession = Depends(get_db),
) -> Announcement:
    org, project = await _get_project(db, org_slug, proj_slug)
    result = await db.execute(select(ProjectMode).where(ProjectMode.id == body.mode_id, ProjectMode.project_id == project.id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Mode not found")
    ann = Announcement(
        project_id=project.id,
        mode_id=body.mode_id,
        title=body.title,
        body=body.body,
        type=body.type,
        action_url=body.action_url,
        image_url=body.image_url,
        target_conditions=body.target_conditions,
        starts_at=body.starts_at,
        ends_at=body.ends_at,
        priority=body.priority,
        is_active=body.is_active,
        created_by=current_user.id,
    )
    db.add(ann)
    await db.flush()
    await write_audit(db, org.id, current_user.id, "announcement.created", "announcement", str(ann.id), request=request)
    return ann


@router.put("/{org_slug}/projects/{proj_slug}/announcements/{ann_id}", response_model=AnnouncementResponse)
async def update_announcement(
    org_slug: str,
    proj_slug: str,
    ann_id: UUID,
    body: AnnouncementUpdate,
    request: Request,
    current_user: User = Depends(get_current_user),
    _member: OrgMember = Depends(require_role(RoleEnum.editor)),
    db: AsyncSession = Depends(get_db),
) -> Announcement:
    org, project = await _get_project(db, org_slug, proj_slug)
    result = await db.execute(select(Announcement).where(Announcement.id == ann_id, Announcement.project_id == project.id))
    ann = result.scalar_one_or_none()
    if not ann:
        raise HTTPException(status_code=404, detail="Announcement not found")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(ann, field, value)
    await db.flush()
    await write_audit(db, org.id, current_user.id, "announcement.updated", "announcement", str(ann_id), request=request)
    return ann


@router.delete("/{org_slug}/projects/{proj_slug}/announcements/{ann_id}", status_code=204)
async def delete_announcement(
    org_slug: str,
    proj_slug: str,
    ann_id: UUID,
    request: Request,
    current_user: User = Depends(get_current_user),
    _member: OrgMember = Depends(require_role(RoleEnum.editor)),
    db: AsyncSession = Depends(get_db),
) -> None:
    org, project = await _get_project(db, org_slug, proj_slug)
    result = await db.execute(select(Announcement).where(Announcement.id == ann_id, Announcement.project_id == project.id))
    ann = result.scalar_one_or_none()
    if not ann:
        raise HTTPException(status_code=404, detail="Announcement not found")
    await write_audit(db, org.id, current_user.id, "announcement.deleted", "announcement", str(ann_id), request=request)
    await db.delete(ann)
    await db.flush()
