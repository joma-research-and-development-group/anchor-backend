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
from app.models.push_campaign import CampaignStatusEnum, PushCampaign
from app.models.user import User
from app.schemas.push import PushCampaignCreate, PushCampaignResponse

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


@router.get("/{org_slug}/projects/{proj_slug}/push-campaigns", response_model=list[PushCampaignResponse])
async def list_campaigns(
    org_slug: str,
    proj_slug: str,
    _member: OrgMember = Depends(require_role(RoleEnum.viewer)),
    db: AsyncSession = Depends(get_db),
) -> list[PushCampaign]:
    _, project = await _get_project(db, org_slug, proj_slug)
    result = await db.execute(
        select(PushCampaign).where(PushCampaign.project_id == project.id).order_by(PushCampaign.created_at.desc())
    )
    return list(result.scalars().all())


@router.post("/{org_slug}/projects/{proj_slug}/push-campaigns", response_model=PushCampaignResponse, status_code=201)
async def create_campaign(
    org_slug: str,
    proj_slug: str,
    body: PushCampaignCreate,
    request: Request,
    current_user: User = Depends(get_current_user),
    _member: OrgMember = Depends(require_role(RoleEnum.editor)),
    db: AsyncSession = Depends(get_db),
) -> PushCampaign:
    org, project = await _get_project(db, org_slug, proj_slug)
    result = await db.execute(select(ProjectMode).where(ProjectMode.id == body.mode_id, ProjectMode.project_id == project.id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Mode not found")
    campaign = PushCampaign(
        project_id=project.id,
        mode_id=body.mode_id,
        title=body.title,
        body=body.body,
        data=body.data,
        target_type=body.target_type,
        target_value=body.target_value,
        scheduled_at=body.scheduled_at,
        created_by=current_user.id,
    )
    db.add(campaign)
    await db.flush()
    await write_audit(db, org.id, current_user.id, "push_campaign.created", "push_campaign", str(campaign.id), request=request)
    return campaign


@router.post("/{org_slug}/projects/{proj_slug}/push-campaigns/{campaign_id}/send", response_model=PushCampaignResponse)
async def send_campaign(
    org_slug: str,
    proj_slug: str,
    campaign_id: UUID,
    request: Request,
    current_user: User = Depends(get_current_user),
    _member: OrgMember = Depends(require_role(RoleEnum.editor)),
    db: AsyncSession = Depends(get_db),
) -> PushCampaign:
    org, project = await _get_project(db, org_slug, proj_slug)
    result = await db.execute(select(PushCampaign).where(PushCampaign.id == campaign_id, PushCampaign.project_id == project.id))
    campaign = result.scalar_one_or_none()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    if campaign.status != CampaignStatusEnum.draft:
        raise HTTPException(status_code=400, detail="Campaign already sent or sending")
    campaign.status = CampaignStatusEnum.sending
    await db.flush()
    from app.workers.tasks.push_delivery import send_push_campaign
    send_push_campaign.delay(str(campaign_id))
    await write_audit(db, org.id, current_user.id, "push_campaign.sent", "push_campaign", str(campaign_id), request=request)
    return campaign


@router.delete("/{org_slug}/projects/{proj_slug}/push-campaigns/{campaign_id}", status_code=204)
async def delete_campaign(
    org_slug: str,
    proj_slug: str,
    campaign_id: UUID,
    request: Request,
    current_user: User = Depends(get_current_user),
    _member: OrgMember = Depends(require_role(RoleEnum.editor)),
    db: AsyncSession = Depends(get_db),
) -> None:
    org, project = await _get_project(db, org_slug, proj_slug)
    result = await db.execute(select(PushCampaign).where(PushCampaign.id == campaign_id, PushCampaign.project_id == project.id))
    campaign = result.scalar_one_or_none()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    await write_audit(db, org.id, current_user.id, "push_campaign.deleted", "push_campaign", str(campaign_id), request=request)
    await db.delete(campaign)
    await db.flush()
