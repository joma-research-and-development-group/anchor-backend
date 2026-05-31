from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from fastapi import Depends, Header, HTTPException, status
from jose import JWTError, jwt

from app.core.config import settings


def create_sdk_session_token(project_id: UUID, mode_id: UUID, version_id: UUID, platform: str) -> tuple[str, datetime]:
    """Create a session JWT for SDK clients. Returns (token, expires_at)."""
    expires_at = datetime.now(timezone.utc) + timedelta(hours=1)
    payload = {
        "sub": "sdk_session",
        "project_id": str(project_id),
        "mode_id": str(mode_id),
        "version_id": str(version_id),
        "platform": platform,
        "exp": expires_at,
        "type": "sdk_session",
    }
    token = jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)
    return token, expires_at


async def get_sdk_session(authorization: str | None = Header(None)) -> dict[str, Any]:
    """Extract and verify SDK session JWT from Bearer token."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing SDK session token")
    token = authorization[7:]
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
        if payload.get("type") != "sdk_session":
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token type")
        return {
            "project_id": UUID(payload["project_id"]),
            "mode_id": UUID(payload["mode_id"]),
            "version_id": UUID(payload["version_id"]),
            "platform": payload["platform"],
        }
    except (JWTError, KeyError, ValueError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired SDK session token")
