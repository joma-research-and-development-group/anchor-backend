from collections.abc import Callable
from uuid import UUID

from fastapi import Cookie, Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.security import verify_token
from app.models.org_member import OrgMember, RoleEnum
from app.models.user import User

ROLE_HIERARCHY: dict[RoleEnum, int] = {
    RoleEnum.viewer: 0,
    RoleEnum.editor: 1,
    RoleEnum.admin: 2,
    RoleEnum.owner: 3,
}


async def get_current_user(
    db: AsyncSession = Depends(get_db),
    access_token: str | None = Cookie(None),
    authorization: str | None = Header(None),
) -> User:
    token = access_token
    if not token and authorization and authorization.startswith("Bearer "):
        token = authorization[7:]
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated", headers={"WWW-Authenticate": "Bearer"})
    user_id = verify_token(token, "access")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token", headers={"WWW-Authenticate": "Bearer"})
    result = await db.execute(select(User).where(User.id == user_id, User.is_active.is_(True)))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user


def require_role(min_role: RoleEnum) -> Callable[..., object]:
    async def dependency(
        org_slug: str,
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
    ) -> OrgMember:
        from app.models.organization import Organization

        result = await db.execute(select(Organization).where(Organization.slug == org_slug))
        org = result.scalar_one_or_none()
        if not org:
            raise HTTPException(status_code=404, detail="Organization not found", headers={"code": "ORG_NOT_FOUND"})
        result = await db.execute(
            select(OrgMember).where(OrgMember.org_id == org.id, OrgMember.user_id == current_user.id)
        )
        member = result.scalar_one_or_none()
        if not member:
            raise HTTPException(status_code=403, detail="Not a member of this organization")
        if ROLE_HIERARCHY[member.role] < ROLE_HIERARCHY[min_role]:
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return member

    return dependency


async def get_current_org_member(
    org_slug: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> OrgMember:
    from app.models.organization import Organization

    result = await db.execute(select(Organization).where(Organization.slug == org_slug))
    org = result.scalar_one_or_none()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    result = await db.execute(
        select(OrgMember).where(OrgMember.org_id == org.id, OrgMember.user_id == current_user.id)
    )
    member = result.scalar_one_or_none()
    if not member:
        raise HTTPException(status_code=403, detail="Not a member of this organization")
    return member
