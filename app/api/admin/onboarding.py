from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import write_audit
from app.core.db import get_db
from app.core.deps import get_current_user, require_role
from app.models.onboarding_flow import OnboardingFlow
from app.models.onboarding_slide import OnboardingSlide
from app.models.org_member import OrgMember, RoleEnum
from app.models.organization import Organization
from app.models.project import Project, ProjectMode
from app.models.user import User
from app.schemas.onboarding import (
    OnboardingFlowCreate,
    OnboardingFlowResponse,
    OnboardingFlowUpdate,
    OnboardingSlideCreate,
    OnboardingSlideResponse,
    OnboardingSlideUpdate,
)

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


async def _get_flow_with_slides(db: AsyncSession, flow: OnboardingFlow) -> OnboardingFlowResponse:
    result = await db.execute(select(OnboardingSlide).where(OnboardingSlide.flow_id == flow.id).order_by(OnboardingSlide.order))
    slides = list(result.scalars().all())
    return OnboardingFlowResponse(
        id=flow.id,
        project_id=flow.project_id,
        mode_id=flow.mode_id,
        name=flow.name,
        trigger=flow.trigger,
        target_version=flow.target_version,
        is_active=flow.is_active,
        priority=flow.priority,
        created_by=flow.created_by,
        created_at=flow.created_at,
        slides=[OnboardingSlideResponse.model_validate(s) for s in slides],
    )


@router.get("/{org_slug}/projects/{proj_slug}/onboarding", response_model=list[OnboardingFlowResponse])
async def list_flows(
    org_slug: str,
    proj_slug: str,
    _member: OrgMember = Depends(require_role(RoleEnum.viewer)),
    db: AsyncSession = Depends(get_db),
) -> list[OnboardingFlowResponse]:
    _, project = await _get_project(db, org_slug, proj_slug)
    result = await db.execute(
        select(OnboardingFlow).where(OnboardingFlow.project_id == project.id).order_by(OnboardingFlow.priority.desc())
    )
    flows = list(result.scalars().all())
    return [await _get_flow_with_slides(db, f) for f in flows]


@router.post("/{org_slug}/projects/{proj_slug}/onboarding", response_model=OnboardingFlowResponse, status_code=201)
async def create_flow(
    org_slug: str,
    proj_slug: str,
    body: OnboardingFlowCreate,
    request: Request,
    current_user: User = Depends(get_current_user),
    _member: OrgMember = Depends(require_role(RoleEnum.editor)),
    db: AsyncSession = Depends(get_db),
) -> OnboardingFlowResponse:
    org, project = await _get_project(db, org_slug, proj_slug)
    result = await db.execute(select(ProjectMode).where(ProjectMode.id == body.mode_id, ProjectMode.project_id == project.id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Mode not found")
    flow = OnboardingFlow(
        project_id=project.id,
        mode_id=body.mode_id,
        name=body.name,
        trigger=body.trigger,
        target_version=body.target_version,
        is_active=body.is_active,
        priority=body.priority,
        created_by=current_user.id,
    )
    db.add(flow)
    await db.flush()
    for slide_data in body.slides:
        slide = OnboardingSlide(flow_id=flow.id, **slide_data.model_dump())
        db.add(slide)
    await db.flush()
    await write_audit(db, org.id, current_user.id, "onboarding.created", "onboarding_flow", str(flow.id), request=request)
    return await _get_flow_with_slides(db, flow)


@router.patch("/{org_slug}/projects/{proj_slug}/onboarding/{flow_id}", response_model=OnboardingFlowResponse)
async def update_flow(
    org_slug: str,
    proj_slug: str,
    flow_id: UUID,
    body: OnboardingFlowUpdate,
    request: Request,
    current_user: User = Depends(get_current_user),
    _member: OrgMember = Depends(require_role(RoleEnum.editor)),
    db: AsyncSession = Depends(get_db),
) -> OnboardingFlowResponse:
    org, project = await _get_project(db, org_slug, proj_slug)
    result = await db.execute(select(OnboardingFlow).where(OnboardingFlow.id == flow_id, OnboardingFlow.project_id == project.id))
    flow = result.scalar_one_or_none()
    if not flow:
        raise HTTPException(status_code=404, detail="Onboarding flow not found")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(flow, field, value)
    await db.flush()
    await write_audit(db, org.id, current_user.id, "onboarding.updated", "onboarding_flow", str(flow_id), request=request)
    return await _get_flow_with_slides(db, flow)


@router.delete("/{org_slug}/projects/{proj_slug}/onboarding/{flow_id}", status_code=204)
async def delete_flow(
    org_slug: str,
    proj_slug: str,
    flow_id: UUID,
    request: Request,
    current_user: User = Depends(get_current_user),
    _member: OrgMember = Depends(require_role(RoleEnum.editor)),
    db: AsyncSession = Depends(get_db),
) -> None:
    org, project = await _get_project(db, org_slug, proj_slug)
    result = await db.execute(select(OnboardingFlow).where(OnboardingFlow.id == flow_id, OnboardingFlow.project_id == project.id))
    flow = result.scalar_one_or_none()
    if not flow:
        raise HTTPException(status_code=404, detail="Onboarding flow not found")
    await write_audit(db, org.id, current_user.id, "onboarding.deleted", "onboarding_flow", str(flow_id), request=request)
    await db.delete(flow)
    await db.flush()


# Slide CRUD
@router.post("/{org_slug}/projects/{proj_slug}/onboarding/{flow_id}/slides", response_model=OnboardingSlideResponse, status_code=201)
async def create_slide(
    org_slug: str,
    proj_slug: str,
    flow_id: UUID,
    body: OnboardingSlideCreate,
    request: Request,
    current_user: User = Depends(get_current_user),
    _member: OrgMember = Depends(require_role(RoleEnum.editor)),
    db: AsyncSession = Depends(get_db),
) -> OnboardingSlide:
    org, project = await _get_project(db, org_slug, proj_slug)
    result = await db.execute(select(OnboardingFlow).where(OnboardingFlow.id == flow_id, OnboardingFlow.project_id == project.id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Onboarding flow not found")
    slide = OnboardingSlide(flow_id=flow_id, **body.model_dump())
    db.add(slide)
    await db.flush()
    await write_audit(db, org.id, current_user.id, "onboarding.slide_created", "onboarding_slide", str(slide.id), request=request)
    return slide


@router.patch("/{org_slug}/projects/{proj_slug}/onboarding/{flow_id}/slides/{slide_id}", response_model=OnboardingSlideResponse)
async def update_slide(
    org_slug: str,
    proj_slug: str,
    flow_id: UUID,
    slide_id: UUID,
    body: OnboardingSlideUpdate,
    request: Request,
    current_user: User = Depends(get_current_user),
    _member: OrgMember = Depends(require_role(RoleEnum.editor)),
    db: AsyncSession = Depends(get_db),
) -> OnboardingSlide:
    org, project = await _get_project(db, org_slug, proj_slug)
    result = await db.execute(select(OnboardingFlow).where(OnboardingFlow.id == flow_id, OnboardingFlow.project_id == project.id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Onboarding flow not found")
    result = await db.execute(select(OnboardingSlide).where(OnboardingSlide.id == slide_id, OnboardingSlide.flow_id == flow_id))
    slide = result.scalar_one_or_none()
    if not slide:
        raise HTTPException(status_code=404, detail="Slide not found")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(slide, field, value)
    await db.flush()
    await write_audit(db, org.id, current_user.id, "onboarding.slide_updated", "onboarding_slide", str(slide_id), request=request)
    return slide


@router.delete("/{org_slug}/projects/{proj_slug}/onboarding/{flow_id}/slides/{slide_id}", status_code=204)
async def delete_slide(
    org_slug: str,
    proj_slug: str,
    flow_id: UUID,
    slide_id: UUID,
    request: Request,
    current_user: User = Depends(get_current_user),
    _member: OrgMember = Depends(require_role(RoleEnum.editor)),
    db: AsyncSession = Depends(get_db),
) -> None:
    org, project = await _get_project(db, org_slug, proj_slug)
    result = await db.execute(select(OnboardingFlow).where(OnboardingFlow.id == flow_id, OnboardingFlow.project_id == project.id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Onboarding flow not found")
    result = await db.execute(select(OnboardingSlide).where(OnboardingSlide.id == slide_id, OnboardingSlide.flow_id == flow_id))
    slide = result.scalar_one_or_none()
    if not slide:
        raise HTTPException(status_code=404, detail="Slide not found")
    await write_audit(db, org.id, current_user.id, "onboarding.slide_deleted", "onboarding_slide", str(slide_id), request=request)
    await db.delete(slide)
    await db.flush()
