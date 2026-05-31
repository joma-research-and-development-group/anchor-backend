from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import write_audit
from app.core.db import get_db
from app.core.deps import get_current_user, require_role
from app.models.org_member import OrgMember, RoleEnum
from app.models.organization import Organization
from app.models.user import User
from app.schemas.member import MemberResponse, MemberUpdate

router = APIRouter()


@router.get("/{org_slug}/members", response_model=list[MemberResponse])
async def list_members(
    org_slug: str,
    _member: OrgMember = Depends(require_role(RoleEnum.viewer)),
    db: AsyncSession = Depends(get_db),
) -> list[MemberResponse]:
    result = await db.execute(select(Organization).where(Organization.slug == org_slug))
    org = result.scalar_one_or_none()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    result = await db.execute(
        select(OrgMember, User).join(User, OrgMember.user_id == User.id).where(OrgMember.org_id == org.id)
    )
    rows = result.all()
    return [
        MemberResponse(
            org_id=m.org_id,
            user_id=m.user_id,
            role=m.role,
            joined_at=m.joined_at,
            email=u.email,
            full_name=u.full_name,
        )
        for m, u in rows
    ]


@router.patch("/{org_slug}/members/{user_id}", response_model=MemberResponse)
async def update_member(
    org_slug: str,
    user_id: UUID,
    body: MemberUpdate,
    request: Request,
    current_user: User = Depends(get_current_user),
    _member: OrgMember = Depends(require_role(RoleEnum.admin)),
    db: AsyncSession = Depends(get_db),
) -> MemberResponse:
    result = await db.execute(select(Organization).where(Organization.slug == org_slug))
    org = result.scalar_one_or_none()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    result = await db.execute(
        select(OrgMember).where(OrgMember.org_id == org.id, OrgMember.user_id == user_id)
    )
    member = result.scalar_one_or_none()
    if not member:
        raise HTTPException(status_code=404, detail="Member not found")

    if member.role == RoleEnum.owner and body.role != RoleEnum.owner:
        raise HTTPException(status_code=403, detail="Cannot demote the owner")

    member.role = body.role
    await db.flush()

    await write_audit(
        db, org.id, current_user.id, "member.updated", "member", str(user_id),
        meta={"new_role": body.role.value}, request=request,
    )
    return MemberResponse(
        org_id=member.org_id, user_id=member.user_id, role=member.role, joined_at=member.joined_at
    )


@router.delete("/{org_slug}/members/{user_id}", status_code=204)
async def remove_member(
    org_slug: str,
    user_id: UUID,
    request: Request,
    current_user: User = Depends(get_current_user),
    _member: OrgMember = Depends(require_role(RoleEnum.admin)),
    db: AsyncSession = Depends(get_db),
) -> None:
    result = await db.execute(select(Organization).where(Organization.slug == org_slug))
    org = result.scalar_one_or_none()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    result = await db.execute(
        select(OrgMember).where(OrgMember.org_id == org.id, OrgMember.user_id == user_id)
    )
    member = result.scalar_one_or_none()
    if not member:
        raise HTTPException(status_code=404, detail="Member not found")

    if member.role == RoleEnum.owner:
        raise HTTPException(status_code=403, detail="Cannot remove the owner")

    await write_audit(
        db, org.id, current_user.id, "member.removed", "member", str(user_id), request=request
    )
    await db.delete(member)
    await db.flush()
