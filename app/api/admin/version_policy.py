from datetime import datetime, timezone
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
from app.models.version_policy import VersionPolicy
from app.schemas.version_policy import VersionPolicyResponse, VersionPolicyUpsert

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


@router.get("/{org_slug}/projects/{proj_slug}/version-policy", response_model=list[VersionPolicyResponse])
async def list_version_policies(
    org_slug: str,
    proj_slug: str,
    _member: OrgMember = Depends(require_role(RoleEnum.viewer)),
    db: AsyncSession = Depends(get_db),
) -> list[VersionPolicy]:
    _, project = await _get_project(db, org_slug, proj_slug)
    result = await db.execute(
        select(VersionPolicy).where(VersionPolicy.project_id == project.id)
    )
    return list(result.scalars().all())


@router.put("/{org_slug}/projects/{proj_slug}/version-policy", response_model=VersionPolicyResponse)
async def upsert_version_policy(
    org_slug: str,
    proj_slug: str,
    body: VersionPolicyUpsert,
    request: Request,
    current_user: User = Depends(get_current_user),
    _member: OrgMember = Depends(require_role(RoleEnum.editor)),
    db: AsyncSession = Depends(get_db),
) -> VersionPolicy:
    org, project = await _get_project(db, org_slug, proj_slug)
    # Verify mode
    result = await db.execute(
        select(ProjectMode).where(ProjectMode.id == body.mode_id, ProjectMode.project_id == project.id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Mode not found")
    # Upsert
    result = await db.execute(
        select(VersionPolicy).where(
            VersionPolicy.project_id == project.id,
            VersionPolicy.mode_id == body.mode_id,
            VersionPolicy.platform == body.platform,
        )
    )
    policy = result.scalar_one_or_none()
    if policy:
        policy.min_supported_semver = body.min_supported_semver
        policy.latest_semver = body.latest_semver
        policy.store_url = body.store_url
        policy.message_force = body.message_force
        policy.message_soft = body.message_soft
        policy.updated_at = datetime.now(timezone.utc)
    else:
        policy = VersionPolicy(
            project_id=project.id,
            mode_id=body.mode_id,
            platform=body.platform,
            min_supported_semver=body.min_supported_semver,
            latest_semver=body.latest_semver,
            store_url=body.store_url,
            message_force=body.message_force,
            message_soft=body.message_soft,
        )
        db.add(policy)
    await db.flush()
    await write_audit(db, org.id, current_user.id, "version_policy.upserted", "version_policy", str(policy.id), request=request)
    return policy
