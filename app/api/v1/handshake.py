from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.key_gen import verify_api_key
from app.core.sdk_auth import create_sdk_session_token
from app.models.api_key import ApiKey, ApiKeyStatusEnum
from app.models.app_version import AppVersion
from app.models.config_entry import ConfigEntry
from app.models.config_override import ConfigOverride
from app.models.maintenance_window import MaintenanceWindow
from app.models.version_policy import VersionPolicy
from app.schemas.handshake import (
    HandshakeRequest,
    HandshakeResponse,
    MaintenanceInfo,
    SessionInfo,
    VersionInfo,
)
from app.services.config_evaluator import compute_etag, evaluate_config

router = APIRouter()


def _build_session(api_key: ApiKey, platform: str) -> SessionInfo:
    """Build a SessionInfo with all fields the SDK's AnchorSession expects."""
    token, expires_at = create_sdk_session_token(
        api_key.project_id, api_key.mode_id, api_key.version_id, platform
    )
    return SessionInfo(
        jwt=token,
        token=token,
        expires_at=expires_at,
        project_id=str(api_key.project_id),
        mode_id=str(api_key.mode_id),
        version_id=str(api_key.version_id),
        platform=platform,
    )


def _semver_tuple(v: str) -> tuple[int, ...]:
    parts = v.replace("-", ".").split(".")
    result = []
    for p in parts[:3]:
        try:
            result.append(int(p))
        except ValueError:
            result.append(0)
    while len(result) < 3:
        result.append(0)
    return tuple(result)


@router.post("/handshake", response_model=HandshakeResponse)
async def handshake(
    body: HandshakeRequest,
    x_anchor_key: str = Header(..., alias="X-Anchor-Key"),
    db: AsyncSession = Depends(get_db),
) -> HandshakeResponse:
    # 1. Extract prefix and look up key
    if len(x_anchor_key) < 20:
        raise HTTPException(status_code=401, detail="Invalid API key")
    prefix = x_anchor_key[:20]
    result = await db.execute(select(ApiKey).where(ApiKey.key_prefix == prefix))
    api_key = result.scalar_one_or_none()
    if not api_key:
        raise HTTPException(status_code=401, detail="Invalid API key")

    # 2. Verify full key against hash
    if not verify_api_key(x_anchor_key, api_key.key_hash):
        raise HTTPException(status_code=401, detail="Invalid API key")

    # 3. If revoked → force_update
    if api_key.status == ApiKeyStatusEnum.revoked:
        return HandshakeResponse(
            session=_build_session(api_key, body.platform.value),
            version=VersionInfo(action="force_update", message="API key has been revoked"),
            maintenance=MaintenanceInfo(active=False),
        )

    # 4. Get the version associated with this key
    result = await db.execute(select(AppVersion).where(AppVersion.id == api_key.version_id))
    key_version = result.scalar_one_or_none()

    # Check version mismatch
    if key_version and (key_version.semver != body.app_version or key_version.build_number != body.build_number):
        return HandshakeResponse(
            session=_build_session(api_key, body.platform.value),
            version=VersionInfo(action="force_update", message="Version mismatch"),
            maintenance=MaintenanceInfo(active=False),
        )

    # 5. Check maintenance windows
    now = datetime.now(timezone.utc)
    result = await db.execute(
        select(MaintenanceWindow).where(
            MaintenanceWindow.project_id == api_key.project_id,
            MaintenanceWindow.mode_id == api_key.mode_id,
            MaintenanceWindow.active.is_(True),
            MaintenanceWindow.starts_at <= now,
            or_(MaintenanceWindow.ends_at.is_(None), MaintenanceWindow.ends_at > now),
        )
    )
    active_maintenance = result.scalar_one_or_none()

    maintenance_info = MaintenanceInfo(active=False)
    if active_maintenance:
        maintenance_info = MaintenanceInfo(
            active=True,
            title=active_maintenance.title,
            message=active_maintenance.message,
        )

    # 6. Compare version against policy
    result = await db.execute(
        select(VersionPolicy).where(
            VersionPolicy.project_id == api_key.project_id,
            VersionPolicy.mode_id == api_key.mode_id,
            VersionPolicy.platform == body.platform,
        )
    )
    policy = result.scalar_one_or_none()

    version_action = "ok"
    version_message = None
    store_url = None
    latest = None

    if policy:
        latest = policy.latest_semver
        store_url = policy.store_url
        if policy.min_supported_semver and _semver_tuple(body.app_version) < _semver_tuple(policy.min_supported_semver):
            version_action = "force_update"
            version_message = policy.message_force
        elif policy.latest_semver and _semver_tuple(body.app_version) < _semver_tuple(policy.latest_semver):
            version_action = "soft_update"
            version_message = policy.message_soft

    # 7. Compute config etag
    result = await db.execute(
        select(ConfigEntry).where(
            ConfigEntry.project_id == api_key.project_id,
            ConfigEntry.mode_id == api_key.mode_id,
        )
    )
    entries = list(result.scalars().all())
    config_etag = None
    if entries:
        entries_data = []
        for entry in entries:
            ov_result = await db.execute(
                select(ConfigOverride).where(ConfigOverride.entry_id == entry.id)
            )
            overrides = [{"conditions": o.conditions, "value": o.value, "priority": o.priority} for o in ov_result.scalars().all()]
            entries_data.append({"key": entry.key, "default_value": entry.default_value, "overrides": overrides})
        client_context = {"app_version": body.app_version, "platform": body.platform.value, "country": ""}
        config_dict = evaluate_config(entries_data, client_context)
        config_etag = compute_etag(config_dict)

    # 8. Issue session JWT and return
    return HandshakeResponse(
        session=_build_session(api_key, body.platform.value),
        version=VersionInfo(action=version_action, store_url=store_url, message=version_message, latest=latest),
        maintenance=maintenance_info,
        config_etag=config_etag,
    )
