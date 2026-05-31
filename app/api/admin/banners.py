from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import write_audit
from app.core.db import get_db
from app.core.deps import get_current_user, require_role
from app.models.banner import BannerCampaign
from app.models.banner_impression import BannerImpression
from app.models.org_member import OrgMember, RoleEnum
from app.models.organization import Organization
from app.models.project import Project, ProjectMode
from app.models.user import User
from app.schemas.banner import BannerCreate, BannerResponse, BannerUpdate

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


@router.get("/{org_slug}/projects/{proj_slug}/banners", response_model=list[BannerResponse])
async def list_banners(
    org_slug: str,
    proj_slug: str,
    _member: OrgMember = Depends(require_role(RoleEnum.viewer)),
    db: AsyncSession = Depends(get_db),
) -> list[BannerCampaign]:
    _, project = await _get_project(db, org_slug, proj_slug)
    result = await db.execute(
        select(BannerCampaign).where(BannerCampaign.project_id == project.id).order_by(BannerCampaign.created_at.desc())
    )
    return list(result.scalars().all())


@router.post("/{org_slug}/projects/{proj_slug}/banners", response_model=BannerResponse, status_code=201)
async def create_banner(
    org_slug: str,
    proj_slug: str,
    body: BannerCreate,
    request: Request,
    current_user: User = Depends(get_current_user),
    _member: OrgMember = Depends(require_role(RoleEnum.editor)),
    db: AsyncSession = Depends(get_db),
) -> BannerCampaign:
    org, project = await _get_project(db, org_slug, proj_slug)
    result = await db.execute(select(ProjectMode).where(ProjectMode.id == body.mode_id, ProjectMode.project_id == project.id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Mode not found")
    banner = BannerCampaign(
        project_id=project.id,
        mode_id=body.mode_id,
        name=body.name,
        title=body.title,
        body=body.body,
        image_url=body.image_url,
        cta_label=body.cta_label,
        cta_url=body.cta_url,
        target_conditions=body.target_conditions,
        starts_at=body.starts_at,
        ends_at=body.ends_at,
        frequency_cap=body.frequency_cap,
        priority=body.priority,
        is_active=body.is_active,
        created_by=current_user.id,
    )
    db.add(banner)
    await db.flush()
    await write_audit(db, org.id, current_user.id, "banner.created", "banner", str(banner.id), request=request)
    return banner


@router.put("/{org_slug}/projects/{proj_slug}/banners/{banner_id}", response_model=BannerResponse)
async def update_banner(
    org_slug: str,
    proj_slug: str,
    banner_id: UUID,
    body: BannerUpdate,
    request: Request,
    current_user: User = Depends(get_current_user),
    _member: OrgMember = Depends(require_role(RoleEnum.editor)),
    db: AsyncSession = Depends(get_db),
) -> BannerCampaign:
    org, project = await _get_project(db, org_slug, proj_slug)
    result = await db.execute(select(BannerCampaign).where(BannerCampaign.id == banner_id, BannerCampaign.project_id == project.id))
    banner = result.scalar_one_or_none()
    if not banner:
        raise HTTPException(status_code=404, detail="Banner not found")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(banner, field, value)
    await db.flush()
    await write_audit(db, org.id, current_user.id, "banner.updated", "banner", str(banner_id), request=request)
    return banner


@router.delete("/{org_slug}/projects/{proj_slug}/banners/{banner_id}", status_code=204)
async def delete_banner(
    org_slug: str,
    proj_slug: str,
    banner_id: UUID,
    request: Request,
    current_user: User = Depends(get_current_user),
    _member: OrgMember = Depends(require_role(RoleEnum.editor)),
    db: AsyncSession = Depends(get_db),
) -> None:
    org, project = await _get_project(db, org_slug, proj_slug)
    result = await db.execute(select(BannerCampaign).where(BannerCampaign.id == banner_id, BannerCampaign.project_id == project.id))
    banner = result.scalar_one_or_none()
    if not banner:
        raise HTTPException(status_code=404, detail="Banner not found")
    await write_audit(db, org.id, current_user.id, "banner.deleted", "banner", str(banner_id), request=request)
    await db.delete(banner)
    await db.flush()


@router.get("/{org_slug}/projects/{proj_slug}/banners/{banner_id}/stats")
async def banner_stats(
    org_slug: str,
    proj_slug: str,
    banner_id: UUID,
    _member: OrgMember = Depends(require_role(RoleEnum.viewer)),
    db: AsyncSession = Depends(get_db),
) -> dict:
    _, project = await _get_project(db, org_slug, proj_slug)
    result = await db.execute(select(BannerCampaign).where(BannerCampaign.id == banner_id, BannerCampaign.project_id == project.id))
    banner = result.scalar_one_or_none()
    if not banner:
        raise HTTPException(status_code=404, detail="Banner not found")
    impressions = await db.execute(
        select(func.count()).select_from(BannerImpression).where(BannerImpression.banner_id == banner_id)
    )
    clicks = await db.execute(
        select(func.count()).select_from(BannerImpression).where(
            BannerImpression.banner_id == banner_id,
            BannerImpression.clicked_at.isnot(None),
        )
    )
    return {
        "banner_id": str(banner_id),
        "total_impressions": impressions.scalar() or 0,
        "total_clicks": clicks.scalar() or 0,
    }
