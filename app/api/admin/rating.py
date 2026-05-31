from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.deps import require_role
from app.models.org_member import OrgMember, RoleEnum
from app.models.organization import Organization
from app.models.project import Project, ProjectMode
from app.models.rating_rule import RatingRule
from app.schemas.rating import RatingRuleResponse, RatingRuleUpsert

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


@router.get("/{org_slug}/projects/{proj_slug}/rating-rules", response_model=list[RatingRuleResponse])
async def list_rating_rules(
    org_slug: str,
    proj_slug: str,
    _member: OrgMember = Depends(require_role(RoleEnum.viewer)),
    db: AsyncSession = Depends(get_db),
) -> list[RatingRule]:
    _, project = await _get_project(db, org_slug, proj_slug)
    result = await db.execute(select(RatingRule).where(RatingRule.project_id == project.id))
    return list(result.scalars().all())


@router.put("/{org_slug}/projects/{proj_slug}/rating-rules", response_model=RatingRuleResponse)
async def upsert_rating_rule(
    org_slug: str,
    proj_slug: str,
    body: RatingRuleUpsert,
    _member: OrgMember = Depends(require_role(RoleEnum.editor)),
    db: AsyncSession = Depends(get_db),
) -> RatingRule:
    _, project = await _get_project(db, org_slug, proj_slug)
    result = await db.execute(select(ProjectMode).where(ProjectMode.id == body.mode_id, ProjectMode.project_id == project.id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Mode not found")
    result = await db.execute(
        select(RatingRule).where(RatingRule.project_id == project.id, RatingRule.mode_id == body.mode_id)
    )
    rule = result.scalar_one_or_none()
    if rule:
        for field, value in body.model_dump(exclude={"mode_id"}).items():
            setattr(rule, field, value)
        rule.updated_at = datetime.now(timezone.utc)
    else:
        rule = RatingRule(project_id=project.id, **body.model_dump())
    db.add(rule)
    await db.flush()
    return rule
