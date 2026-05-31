from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import write_audit
from app.core.db import get_db
from app.core.deps import get_current_user, require_role
from app.core.key_gen import generate_api_key
from app.models.api_key import ApiKey, ApiKeyStatusEnum
from app.models.app_version import AppVersion
from app.models.org_member import OrgMember, RoleEnum
from app.models.organization import Organization
from app.models.project import Project, ProjectMode
from app.models.user import User
from app.schemas.api_key import ApiKeyCreate, ApiKeyCreatedResponse, ApiKeyResponse, ApiKeyRevoke

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


@router.get("/{org_slug}/projects/{proj_slug}/api-keys", response_model=list[ApiKeyResponse])
async def list_api_keys(
    org_slug: str,
    proj_slug: str,
    _member: OrgMember = Depends(require_role(RoleEnum.viewer)),
    db: AsyncSession = Depends(get_db),
) -> list[ApiKey]:
    _, project = await _get_project(db, org_slug, proj_slug)
    result = await db.execute(
        select(ApiKey).where(ApiKey.project_id == project.id).order_by(ApiKey.created_at.desc())
    )
    return list(result.scalars().all())


@router.post(
    "/{org_slug}/projects/{proj_slug}/versions/{version_id}/api-keys",
    response_model=ApiKeyCreatedResponse,
    status_code=201,
)
async def create_api_key(
    org_slug: str,
    proj_slug: str,
    version_id: UUID,
    body: ApiKeyCreate,
    request: Request,
    current_user: User = Depends(get_current_user),
    _member: OrgMember = Depends(require_role(RoleEnum.editor)),
    db: AsyncSession = Depends(get_db),
) -> dict:
    org, project = await _get_project(db, org_slug, proj_slug)
    # Verify version belongs to project
    result = await db.execute(
        select(AppVersion).where(AppVersion.id == version_id, AppVersion.project_id == project.id)
    )
    version = result.scalar_one_or_none()
    if not version:
        raise HTTPException(status_code=404, detail="Version not found")
    # Get mode name for key generation
    result = await db.execute(select(ProjectMode).where(ProjectMode.id == version.mode_id))
    mode = result.scalar_one_or_none()
    mode_name = mode.name if mode else "test"

    raw_secret, prefix, key_hash = generate_api_key(mode_name)
    api_key = ApiKey(
        project_id=project.id,
        mode_id=version.mode_id,
        version_id=version_id,
        name=body.name,
        key_prefix=prefix,
        key_hash=key_hash,
        created_by=current_user.id,
    )
    db.add(api_key)
    await db.flush()
    await write_audit(db, org.id, current_user.id, "api_key.created", "api_key", str(api_key.id), request=request)
    return {
        "id": api_key.id,
        "project_id": api_key.project_id,
        "mode_id": api_key.mode_id,
        "version_id": api_key.version_id,
        "name": api_key.name,
        "key_prefix": api_key.key_prefix,
        "status": api_key.status,
        "created_at": api_key.created_at,
        "revoked_at": api_key.revoked_at,
        "raw_secret": raw_secret,
    }


@router.post("/{org_slug}/projects/{proj_slug}/api-keys/{key_id}/revoke", response_model=ApiKeyResponse)
async def revoke_api_key(
    org_slug: str,
    proj_slug: str,
    key_id: UUID,
    body: ApiKeyRevoke,
    request: Request,
    current_user: User = Depends(get_current_user),
    _member: OrgMember = Depends(require_role(RoleEnum.editor)),
    db: AsyncSession = Depends(get_db),
) -> ApiKey:
    org, project = await _get_project(db, org_slug, proj_slug)
    result = await db.execute(
        select(ApiKey).where(ApiKey.id == key_id, ApiKey.project_id == project.id)
    )
    api_key = result.scalar_one_or_none()
    if not api_key:
        raise HTTPException(status_code=404, detail="API key not found")
    if api_key.status == ApiKeyStatusEnum.revoked:
        raise HTTPException(status_code=409, detail="Key already revoked")
    api_key.status = ApiKeyStatusEnum.revoked
    api_key.revoked_at = datetime.now(timezone.utc)
    api_key.revoked_reason = body.reason
    await db.flush()
    await write_audit(db, org.id, current_user.id, "api_key.revoked", "api_key", str(key_id), request=request)
    return api_key
