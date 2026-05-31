import re
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.deps import get_current_user
from app.core.security import (
    create_access_token,
    create_refresh_token,
    hash_password,
    verify_password,
    verify_token,
)
from app.models.org_member import OrgMember, RoleEnum
from app.models.organization import Organization
from app.models.user import User
from app.schemas.auth import LoginRequest, SignupRequest, TokenResponse, UserResponse

router = APIRouter()


def _slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug


@router.post("/signup", response_model=TokenResponse, status_code=201)
async def signup(body: SignupRequest, response: Response, db: AsyncSession = Depends(get_db)) -> TokenResponse:
    existing = await db.execute(select(User).where(User.email == body.email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Email already registered")

    user = User(
        email=body.email,
        password_hash=hash_password(body.password),
        full_name=body.full_name,
    )
    db.add(user)
    await db.flush()

    org_slug = _slugify(body.org_name)
    existing_org = await db.execute(select(Organization).where(Organization.slug == org_slug))
    if existing_org.scalar_one_or_none():
        org_slug = f"{org_slug}-{str(user.id)[:8]}"

    org = Organization(name=body.org_name, slug=org_slug, created_by=user.id)
    db.add(org)
    await db.flush()

    member = OrgMember(org_id=org.id, user_id=user.id, role=RoleEnum.owner)
    db.add(member)
    await db.flush()

    access_token = create_access_token(str(user.id))
    refresh_token = create_refresh_token(str(user.id))

    response.set_cookie(
        key="access_token", value=access_token, httponly=True, samesite="lax", max_age=900
    )
    response.set_cookie(
        key="refresh_token", value=refresh_token, httponly=True, samesite="lax", max_age=604800
    )
    return TokenResponse(access_token=access_token)


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, response: Response, db: AsyncSession = Depends(get_db)) -> TokenResponse:
    result = await db.execute(select(User).where(User.email == body.email))
    user = result.scalar_one_or_none()
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account disabled")

    user.last_login_at = datetime.now(timezone.utc)
    await db.flush()

    access_token = create_access_token(str(user.id))
    refresh_token = create_refresh_token(str(user.id))

    response.set_cookie(
        key="access_token", value=access_token, httponly=True, samesite="lax", max_age=900
    )
    response.set_cookie(
        key="refresh_token", value=refresh_token, httponly=True, samesite="lax", max_age=604800
    )
    return TokenResponse(access_token=access_token)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    response: Response,
    db: AsyncSession = Depends(get_db),
    refresh_token: str | None = None,
) -> TokenResponse:
    from fastapi import Cookie as CookieParam

    # Try to get from cookie via dependency injection workaround
    if not refresh_token:
        raise HTTPException(status_code=401, detail="No refresh token")
    user_id = verify_token(refresh_token, "refresh")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    result = await db.execute(select(User).where(User.id == user_id, User.is_active.is_(True)))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    access_token = create_access_token(str(user.id))
    new_refresh = create_refresh_token(str(user.id))

    response.set_cookie(
        key="access_token", value=access_token, httponly=True, samesite="lax", max_age=900
    )
    response.set_cookie(
        key="refresh_token", value=new_refresh, httponly=True, samesite="lax", max_age=604800
    )
    return TokenResponse(access_token=access_token)


@router.post("/logout")
async def logout(response: Response) -> dict[str, str]:
    response.delete_cookie("access_token")
    response.delete_cookie("refresh_token")
    return {"detail": "Logged out"}


@router.get("/me", response_model=UserResponse)
async def me(current_user: User = Depends(get_current_user)) -> User:
    return current_user
