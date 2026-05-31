from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import write_audit
from app.core.db import get_db
from app.core.deps import get_current_user, require_role
from app.models.org_member import OrgMember, RoleEnum
from app.models.organization import Organization
from app.models.user import User
from app.schemas.org import OrgCreate, OrgResponse, OrgUpdate

router = APIRouter()


@router.get("", response_model=list[OrgResponse])
async def list_orgs(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[Organization]:
    result = await db.execute(
        select(Organization)
        .join(OrgMember, OrgMember.org_id == Organization.id)
        .where(OrgMember.user_id == current_user.id)
    )
    return list(result.scalars().all())


@router.post("", response_model=OrgResponse, status_code=201)
async def create_org(
    body: OrgCreate,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Organization:
    existing = await db.execute(select(Organization).where(Organization.slug == body.slug))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Organization slug already taken")

    org = Organization(name=body.name, slug=body.slug, created_by=current_user.id)
    db.add(org)
    await db.flush()

    member = OrgMember(org_id=org.id, user_id=current_user.id, role=RoleEnum.owner)
    db.add(member)
    await db.flush()

    await write_audit(db, org.id, current_user.id, "org.created", "organization", str(org.id), request=request)
    return org


@router.get("/{org_slug}", response_model=OrgResponse)
async def get_org(
    org_slug: str,
    _member: OrgMember = Depends(require_role(RoleEnum.viewer)),
    db: AsyncSession = Depends(get_db),
) -> Organization:
    result = await db.execute(select(Organization).where(Organization.slug == org_slug))
    org = result.scalar_one_or_none()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    return org


@router.patch("/{org_slug}", response_model=OrgResponse)
async def update_org(
    org_slug: str,
    body: OrgUpdate,
    request: Request,
    current_user: User = Depends(get_current_user),
    _member: OrgMember = Depends(require_role(RoleEnum.admin)),
    db: AsyncSession = Depends(get_db),
) -> Organization:
    result = await db.execute(select(Organization).where(Organization.slug == org_slug))
    org = result.scalar_one_or_none()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    if body.name is not None:
        org.name = body.name
    if body.slug is not None:
        dup = await db.execute(
            select(Organization).where(Organization.slug == body.slug, Organization.id != org.id)
        )
        if dup.scalar_one_or_none():
            raise HTTPException(status_code=409, detail="Slug already taken")
        org.slug = body.slug

    await db.flush()
    await write_audit(db, org.id, current_user.id, "org.updated", "organization", str(org.id), request=request)
    return org


@router.delete("/{org_slug}", status_code=204)
async def delete_org(
    org_slug: str,
    request: Request,
    current_user: User = Depends(get_current_user),
    _member: OrgMember = Depends(require_role(RoleEnum.owner)),
    db: AsyncSession = Depends(get_db),
) -> None:
    result = await db.execute(select(Organization).where(Organization.slug == org_slug))
    org = result.scalar_one_or_none()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    await write_audit(db, org.id, current_user.id, "org.deleted", "organization", str(org.id), request=request)
    await db.delete(org)
    await db.flush()
