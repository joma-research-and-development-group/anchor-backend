from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import write_audit
from app.core.db import get_db
from app.core.deps import get_current_user, require_role
from app.core.encryption import encrypt_credentials
from app.models.org_member import OrgMember, RoleEnum
from app.models.organization import Organization
from app.models.project import Project, ProjectMode
from app.models.push_credential import PushCredential
from app.models.user import User
from app.schemas.push import PushCredentialCreate, PushCredentialResponse

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


@router.get("/{org_slug}/projects/{proj_slug}/push-credentials", response_model=list[PushCredentialResponse])
async def list_push_credentials(
    org_slug: str,
    proj_slug: str,
    _member: OrgMember = Depends(require_role(RoleEnum.viewer)),
    db: AsyncSession = Depends(get_db),
) -> list[PushCredential]:
    _, project = await _get_project(db, org_slug, proj_slug)
    result = await db.execute(select(PushCredential).where(PushCredential.project_id == project.id))
    return list(result.scalars().all())


@router.post("/{org_slug}/projects/{proj_slug}/push-credentials", response_model=PushCredentialResponse, status_code=201)
async def create_push_credential(
    org_slug: str,
    proj_slug: str,
    body: PushCredentialCreate,
    request: Request,
    current_user: User = Depends(get_current_user),
    _member: OrgMember = Depends(require_role(RoleEnum.admin)),
    db: AsyncSession = Depends(get_db),
) -> PushCredential:
    org, project = await _get_project(db, org_slug, proj_slug)
    result = await db.execute(select(ProjectMode).where(ProjectMode.id == body.mode_id, ProjectMode.project_id == project.id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Mode not found")
    cred = PushCredential(
        project_id=project.id,
        mode_id=body.mode_id,
        platform=body.platform,
        provider=body.provider,
        name=body.name,
        encrypted_creds=encrypt_credentials(body.credentials),
        is_default=body.is_default,
        created_by=current_user.id,
    )
    db.add(cred)
    await db.flush()
    await write_audit(db, org.id, current_user.id, "push_credential.created", "push_credential", str(cred.id), request=request)
    return cred


@router.delete("/{org_slug}/projects/{proj_slug}/push-credentials/{cred_id}", status_code=204)
async def delete_push_credential(
    org_slug: str,
    proj_slug: str,
    cred_id: UUID,
    request: Request,
    current_user: User = Depends(get_current_user),
    _member: OrgMember = Depends(require_role(RoleEnum.admin)),
    db: AsyncSession = Depends(get_db),
) -> None:
    org, project = await _get_project(db, org_slug, proj_slug)
    result = await db.execute(select(PushCredential).where(PushCredential.id == cred_id, PushCredential.project_id == project.id))
    cred = result.scalar_one_or_none()
    if not cred:
        raise HTTPException(status_code=404, detail="Push credential not found")
    await write_audit(db, org.id, current_user.id, "push_credential.deleted", "push_credential", str(cred_id), request=request)
    await db.delete(cred)
    await db.flush()
