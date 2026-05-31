import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import write_audit
from app.core.db import get_db
from app.core.deps import get_current_user, require_role
from app.models.org_invitation import OrgInvitation
from app.models.org_member import OrgMember, RoleEnum
from app.models.organization import Organization
from app.models.user import User
from app.schemas.member import InvitationCreate, InvitationResponse

router = APIRouter()


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


@router.post("/{org_slug}/invitations", response_model=InvitationResponse, status_code=201)
async def create_invitation(
    org_slug: str,
    body: InvitationCreate,
    request: Request,
    current_user: User = Depends(get_current_user),
    _member: OrgMember = Depends(require_role(RoleEnum.admin)),
    db: AsyncSession = Depends(get_db),
) -> OrgInvitation:
    result = await db.execute(select(Organization).where(Organization.slug == org_slug))
    org = result.scalar_one_or_none()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    # Check if already a member
    existing_member = await db.execute(
        select(OrgMember)
        .join(User, OrgMember.user_id == User.id)
        .where(OrgMember.org_id == org.id, User.email == body.email)
    )
    if existing_member.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="User is already a member")

    token = secrets.token_urlsafe(32)
    invitation = OrgInvitation(
        org_id=org.id,
        email=body.email,
        role=body.role,
        token_hash=_hash_token(token),
        invited_by=current_user.id,
        expires_at=datetime.now(timezone.utc) + timedelta(days=7),
    )
    db.add(invitation)
    await db.flush()

    # Send email async
    from app.workers.tasks.email import send_invitation_email

    send_invitation_email.delay(body.email, token, org.name)

    await write_audit(
        db, org.id, current_user.id, "invitation.created", "invitation",
        str(invitation.id), meta={"email": body.email}, request=request,
    )
    return invitation


@router.get("/{org_slug}/invitations", response_model=list[InvitationResponse])
async def list_invitations(
    org_slug: str,
    _member: OrgMember = Depends(require_role(RoleEnum.admin)),
    db: AsyncSession = Depends(get_db),
) -> list[OrgInvitation]:
    result = await db.execute(select(Organization).where(Organization.slug == org_slug))
    org = result.scalar_one_or_none()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    result = await db.execute(
        select(OrgInvitation).where(OrgInvitation.org_id == org.id).order_by(OrgInvitation.created_at.desc())
    )
    return list(result.scalars().all())


@router.delete("/{org_slug}/invitations/{invitation_id}", status_code=204)
async def delete_invitation(
    org_slug: str,
    invitation_id: UUID,
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
        select(OrgInvitation).where(OrgInvitation.id == invitation_id, OrgInvitation.org_id == org.id)
    )
    invitation = result.scalar_one_or_none()
    if not invitation:
        raise HTTPException(status_code=404, detail="Invitation not found")

    await write_audit(
        db, org.id, current_user.id, "invitation.deleted", "invitation",
        str(invitation_id), request=request,
    )
    await db.delete(invitation)
    await db.flush()


@router.post("/invitations/accept", status_code=200)
async def accept_invitation(
    token: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    token_hash = _hash_token(token)
    result = await db.execute(
        select(OrgInvitation).where(OrgInvitation.token_hash == token_hash)
    )
    invitation = result.scalar_one_or_none()
    if not invitation:
        raise HTTPException(status_code=404, detail="Invitation not found")

    if invitation.accepted_at:
        raise HTTPException(status_code=409, detail="Invitation already accepted")

    if invitation.expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=410, detail="Invitation expired")

    if invitation.email != current_user.email:
        raise HTTPException(status_code=403, detail="Invitation is for a different email")

    # Check if already a member
    existing = await db.execute(
        select(OrgMember).where(
            OrgMember.org_id == invitation.org_id, OrgMember.user_id == current_user.id
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Already a member")

    member = OrgMember(org_id=invitation.org_id, user_id=current_user.id, role=invitation.role)
    db.add(member)
    invitation.accepted_at = datetime.now(timezone.utc)
    await db.flush()

    return {"detail": "Invitation accepted"}
