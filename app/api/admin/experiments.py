from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.deps import get_current_user, require_role
from app.models.experiment import Experiment, ExperimentStatusEnum
from app.models.experiment_assignment import ExperimentAssignment
from app.models.experiment_variant import ExperimentVariant
from app.models.org_member import OrgMember, RoleEnum
from app.models.organization import Organization
from app.models.project import Project, ProjectMode
from app.models.user import User
from app.schemas.experiment import (
    ExperimentCreate,
    ExperimentResponse,
    ExperimentResults,
    ExperimentResultVariant,
    ExperimentUpdate,
    ExperimentVariantCreate,
    ExperimentVariantResponse,
    ExperimentWithVariants,
)

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


@router.get("/{org_slug}/projects/{proj_slug}/experiments", response_model=list[ExperimentResponse])
async def list_experiments(
    org_slug: str,
    proj_slug: str,
    _member: OrgMember = Depends(require_role(RoleEnum.viewer)),
    db: AsyncSession = Depends(get_db),
) -> list[Experiment]:
    project = await _get_project(db, org_slug, proj_slug)
    result = await db.execute(
        select(Experiment).where(Experiment.project_id == project.id).order_by(Experiment.created_at.desc())
    )
    return list(result.scalars().all())


@router.post("/{org_slug}/projects/{proj_slug}/experiments", response_model=ExperimentWithVariants, status_code=201)
async def create_experiment(
    org_slug: str,
    proj_slug: str,
    body: ExperimentCreate,
    current_user: User = Depends(get_current_user),
    _member: OrgMember = Depends(require_role(RoleEnum.editor)),
    db: AsyncSession = Depends(get_db),
) -> dict:
    project = await _get_project(db, org_slug, proj_slug)
    result = await db.execute(select(ProjectMode).where(ProjectMode.id == body.mode_id, ProjectMode.project_id == project.id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Mode not found")
    experiment = Experiment(
        project_id=project.id,
        mode_id=body.mode_id,
        name=body.name,
        description=body.description,
        traffic_pct=body.traffic_pct,
        created_by=current_user.id,
    )
    db.add(experiment)
    await db.flush()
    variants = []
    for v in body.variants:
        variant = ExperimentVariant(experiment_id=experiment.id, name=v.name, weight=v.weight, payload=v.payload)
        db.add(variant)
        variants.append(variant)
    await db.flush()
    return {**experiment.__dict__, "variants": variants}


@router.get("/{org_slug}/projects/{proj_slug}/experiments/{experiment_id}", response_model=ExperimentWithVariants)
async def get_experiment(
    org_slug: str,
    proj_slug: str,
    experiment_id: UUID,
    _member: OrgMember = Depends(require_role(RoleEnum.viewer)),
    db: AsyncSession = Depends(get_db),
) -> dict:
    project = await _get_project(db, org_slug, proj_slug)
    result = await db.execute(select(Experiment).where(Experiment.id == experiment_id, Experiment.project_id == project.id))
    experiment = result.scalar_one_or_none()
    if not experiment:
        raise HTTPException(status_code=404, detail="Experiment not found")
    result = await db.execute(select(ExperimentVariant).where(ExperimentVariant.experiment_id == experiment_id))
    variants = list(result.scalars().all())
    return {**experiment.__dict__, "variants": variants}


@router.put("/{org_slug}/projects/{proj_slug}/experiments/{experiment_id}", response_model=ExperimentResponse)
async def update_experiment(
    org_slug: str,
    proj_slug: str,
    experiment_id: UUID,
    body: ExperimentUpdate,
    _member: OrgMember = Depends(require_role(RoleEnum.editor)),
    db: AsyncSession = Depends(get_db),
) -> Experiment:
    project = await _get_project(db, org_slug, proj_slug)
    result = await db.execute(select(Experiment).where(Experiment.id == experiment_id, Experiment.project_id == project.id))
    experiment = result.scalar_one_or_none()
    if not experiment:
        raise HTTPException(status_code=404, detail="Experiment not found")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(experiment, field, value)
    await db.flush()
    return experiment


@router.delete("/{org_slug}/projects/{proj_slug}/experiments/{experiment_id}", status_code=204)
async def delete_experiment(
    org_slug: str,
    proj_slug: str,
    experiment_id: UUID,
    _member: OrgMember = Depends(require_role(RoleEnum.editor)),
    db: AsyncSession = Depends(get_db),
) -> None:
    project = await _get_project(db, org_slug, proj_slug)
    result = await db.execute(select(Experiment).where(Experiment.id == experiment_id, Experiment.project_id == project.id))
    experiment = result.scalar_one_or_none()
    if not experiment:
        raise HTTPException(status_code=404, detail="Experiment not found")
    await db.delete(experiment)
    await db.flush()


@router.post("/{org_slug}/projects/{proj_slug}/experiments/{experiment_id}/variants", response_model=ExperimentVariantResponse, status_code=201)
async def add_variant(
    org_slug: str,
    proj_slug: str,
    experiment_id: UUID,
    body: ExperimentVariantCreate,
    _member: OrgMember = Depends(require_role(RoleEnum.editor)),
    db: AsyncSession = Depends(get_db),
) -> ExperimentVariant:
    project = await _get_project(db, org_slug, proj_slug)
    result = await db.execute(select(Experiment).where(Experiment.id == experiment_id, Experiment.project_id == project.id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Experiment not found")
    variant = ExperimentVariant(experiment_id=experiment_id, name=body.name, weight=body.weight, payload=body.payload)
    db.add(variant)
    await db.flush()
    return variant


@router.post("/{org_slug}/projects/{proj_slug}/experiments/{experiment_id}/start", response_model=ExperimentResponse)
async def start_experiment(
    org_slug: str,
    proj_slug: str,
    experiment_id: UUID,
    _member: OrgMember = Depends(require_role(RoleEnum.editor)),
    db: AsyncSession = Depends(get_db),
) -> Experiment:
    project = await _get_project(db, org_slug, proj_slug)
    result = await db.execute(select(Experiment).where(Experiment.id == experiment_id, Experiment.project_id == project.id))
    experiment = result.scalar_one_or_none()
    if not experiment:
        raise HTTPException(status_code=404, detail="Experiment not found")
    experiment.status = ExperimentStatusEnum.running
    experiment.started_at = datetime.now(timezone.utc)
    await db.flush()
    return experiment


@router.post("/{org_slug}/projects/{proj_slug}/experiments/{experiment_id}/pause", response_model=ExperimentResponse)
async def pause_experiment(
    org_slug: str,
    proj_slug: str,
    experiment_id: UUID,
    _member: OrgMember = Depends(require_role(RoleEnum.editor)),
    db: AsyncSession = Depends(get_db),
) -> Experiment:
    project = await _get_project(db, org_slug, proj_slug)
    result = await db.execute(select(Experiment).where(Experiment.id == experiment_id, Experiment.project_id == project.id))
    experiment = result.scalar_one_or_none()
    if not experiment:
        raise HTTPException(status_code=404, detail="Experiment not found")
    experiment.status = ExperimentStatusEnum.paused
    await db.flush()
    return experiment


@router.post("/{org_slug}/projects/{proj_slug}/experiments/{experiment_id}/complete", response_model=ExperimentResponse)
async def complete_experiment(
    org_slug: str,
    proj_slug: str,
    experiment_id: UUID,
    _member: OrgMember = Depends(require_role(RoleEnum.editor)),
    db: AsyncSession = Depends(get_db),
) -> Experiment:
    project = await _get_project(db, org_slug, proj_slug)
    result = await db.execute(select(Experiment).where(Experiment.id == experiment_id, Experiment.project_id == project.id))
    experiment = result.scalar_one_or_none()
    if not experiment:
        raise HTTPException(status_code=404, detail="Experiment not found")
    experiment.status = ExperimentStatusEnum.completed
    experiment.ended_at = datetime.now(timezone.utc)
    await db.flush()
    return experiment


@router.get("/{org_slug}/projects/{proj_slug}/experiments/{experiment_id}/results", response_model=ExperimentResults)
async def experiment_results(
    org_slug: str,
    proj_slug: str,
    experiment_id: UUID,
    _member: OrgMember = Depends(require_role(RoleEnum.viewer)),
    db: AsyncSession = Depends(get_db),
) -> dict:
    project = await _get_project(db, org_slug, proj_slug)
    result = await db.execute(select(Experiment).where(Experiment.id == experiment_id, Experiment.project_id == project.id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Experiment not found")
    result = await db.execute(select(ExperimentVariant).where(ExperimentVariant.experiment_id == experiment_id))
    variants = list(result.scalars().all())
    variant_results = []
    total = 0
    for v in variants:
        count_result = await db.execute(
            select(func.count()).select_from(ExperimentAssignment).where(ExperimentAssignment.variant_id == v.id)
        )
        count = count_result.scalar() or 0
        total += count
        variant_results.append({"variant_id": v.id, "variant_name": v.name, "assignment_count": count})
    return {"experiment_id": experiment_id, "total_assignments": total, "variants": variant_results}
