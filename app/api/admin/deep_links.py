from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.deps import get_current_user, require_role
from app.models.deep_link import DeepLink
from app.models.org_member import OrgMember, RoleEnum
from app.models.organization import Organization
from app.models.project import Project, ProjectMode
from app.models.user import User
from app.schemas.deep_link import DeepLinkCreate, DeepLinkResponse, DeepLinkUpdate

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


@router.get("/{org_slug}/projects/{proj_slug}/deep-links", response_model=list[DeepLinkResponse])
async def list_deep_links(
    org_slug: str,
    proj_slug: str,
    _member: OrgMember = Depends(require_role(RoleEnum.viewer)),
    db: AsyncSession = Depends(get_db),
) -> list[DeepLink]:
    project = await _get_project(db, org_slug, proj_slug)
    result = await db.execute(
        select(DeepLink).where(DeepLink.project_id == project.id).order_by(DeepLink.created_at.desc())
    )
    return list(result.scalars().all())


@router.post("/{org_slug}/projects/{proj_slug}/deep-links", response_model=DeepLinkResponse, status_code=201)
async def create_deep_link(
    org_slug: str,
    proj_slug: str,
    body: DeepLinkCreate,
    current_user: User = Depends(get_current_user),
    _member: OrgMember = Depends(require_role(RoleEnum.editor)),
    db: AsyncSession = Depends(get_db),
) -> DeepLink:
    project = await _get_project(db, org_slug, proj_slug)
    result = await db.execute(select(ProjectMode).where(ProjectMode.id == body.mode_id, ProjectMode.project_id == project.id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Mode not found")
    # Check slug uniqueness
    existing = await db.execute(select(DeepLink).where(DeepLink.slug == body.slug))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Slug already in use")
    link = DeepLink(
        project_id=project.id,
        mode_id=body.mode_id,
        slug=body.slug,
        title=body.title,
        ios_url=body.ios_url,
        android_url=body.android_url,
        web_url=body.web_url,
        fallback_url=body.fallback_url,
        utm_source=body.utm_source,
        utm_medium=body.utm_medium,
        utm_campaign=body.utm_campaign,
        created_by=current_user.id,
    )
    db.add(link)
    await db.flush()
    return link


@router.put("/{org_slug}/projects/{proj_slug}/deep-links/{link_id}", response_model=DeepLinkResponse)
async def update_deep_link(
    org_slug: str,
    proj_slug: str,
    link_id: UUID,
    body: DeepLinkUpdate,
    _member: OrgMember = Depends(require_role(RoleEnum.editor)),
    db: AsyncSession = Depends(get_db),
) -> DeepLink:
    project = await _get_project(db, org_slug, proj_slug)
    result = await db.execute(select(DeepLink).where(DeepLink.id == link_id, DeepLink.project_id == project.id))
    link = result.scalar_one_or_none()
    if not link:
        raise HTTPException(status_code=404, detail="Deep link not found")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(link, field, value)
    await db.flush()
    return link


@router.delete("/{org_slug}/projects/{proj_slug}/deep-links/{link_id}", status_code=204)
async def delete_deep_link(
    org_slug: str,
    proj_slug: str,
    link_id: UUID,
    _member: OrgMember = Depends(require_role(RoleEnum.editor)),
    db: AsyncSession = Depends(get_db),
) -> None:
    project = await _get_project(db, org_slug, proj_slug)
    result = await db.execute(select(DeepLink).where(DeepLink.id == link_id, DeepLink.project_id == project.id))
    link = result.scalar_one_or_none()
    if not link:
        raise HTTPException(status_code=404, detail="Deep link not found")
    await db.delete(link)
    await db.flush()


@router.get("/{org_slug}/projects/{proj_slug}/deep-links/{link_id}/stats")
async def deep_link_stats(
    org_slug: str,
    proj_slug: str,
    link_id: UUID,
    _member: OrgMember = Depends(require_role(RoleEnum.viewer)),
    db: AsyncSession = Depends(get_db),
) -> dict:
    project = await _get_project(db, org_slug, proj_slug)
    result = await db.execute(select(DeepLink).where(DeepLink.id == link_id, DeepLink.project_id == project.id))
    link = result.scalar_one_or_none()
    if not link:
        raise HTTPException(status_code=404, detail="Deep link not found")
    return {"link_id": str(link_id), "slug": link.slug, "clicks": link.clicks}
