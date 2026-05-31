from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, Header, Request, Response
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.sdk_auth import get_sdk_session
from app.models.config_entry import ConfigEntry
from app.models.config_override import ConfigOverride
from app.models.maintenance_window import MaintenanceWindow
from app.models.version_policy import VersionPolicy
from app.schemas.handshake import MaintenanceInfo
from app.schemas.version_policy import VersionPolicyResponse
from app.services.config_evaluator import compute_etag, evaluate_config

router = APIRouter()


@router.get("/version-policy", response_model=VersionPolicyResponse | None)
async def get_version_policy(
    session: dict[str, Any] = Depends(get_sdk_session),
    db: AsyncSession = Depends(get_db),
) -> VersionPolicy | None:
    result = await db.execute(
        select(VersionPolicy).where(
            VersionPolicy.project_id == session["project_id"],
            VersionPolicy.mode_id == session["mode_id"],
            VersionPolicy.platform == session["platform"],
        )
    )
    return result.scalar_one_or_none()


@router.get("/maintenance", response_model=MaintenanceInfo)
async def get_maintenance(
    session: dict[str, Any] = Depends(get_sdk_session),
    db: AsyncSession = Depends(get_db),
) -> MaintenanceInfo:
    now = datetime.now(timezone.utc)
    result = await db.execute(
        select(MaintenanceWindow).where(
            MaintenanceWindow.project_id == session["project_id"],
            MaintenanceWindow.mode_id == session["mode_id"],
            MaintenanceWindow.active.is_(True),
            MaintenanceWindow.starts_at <= now,
            or_(MaintenanceWindow.ends_at.is_(None), MaintenanceWindow.ends_at > now),
        )
    )
    window = result.scalar_one_or_none()
    if window:
        return MaintenanceInfo(active=True, title=window.title, message=window.message)
    return MaintenanceInfo(active=False)


@router.get("/config", response_model=None)
async def get_config(
    response: Response,
    session: dict[str, Any] = Depends(get_sdk_session),
    db: AsyncSession = Depends(get_db),
    if_none_match: str | None = Header(None, alias="If-None-Match"),
) -> dict[str, Any] | Response:
    result = await db.execute(
        select(ConfigEntry).where(
            ConfigEntry.project_id == session["project_id"],
            ConfigEntry.mode_id == session["mode_id"],
        )
    )
    entries = list(result.scalars().all())

    entries_data = []
    for entry in entries:
        ov_result = await db.execute(
            select(ConfigOverride).where(ConfigOverride.entry_id == entry.id)
        )
        overrides = [{"conditions": o.conditions, "value": o.value, "priority": o.priority} for o in ov_result.scalars().all()]
        entries_data.append({"key": entry.key, "default_value": entry.default_value, "overrides": overrides})

    client_context = {"app_version": "", "platform": session["platform"], "country": ""}
    config_dict = evaluate_config(entries_data, client_context)
    etag = compute_etag(config_dict)

    if if_none_match and if_none_match.strip('"') == etag:
        return Response(status_code=304)

    response.headers["ETag"] = f'"{etag}"'
    return config_dict
