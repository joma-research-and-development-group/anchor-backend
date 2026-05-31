from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.sdk_auth import get_sdk_session
from app.core.sdk_device import get_or_create_session_device
from app.models.crash_group import CrashGroup, CrashGroupStatusEnum
from app.models.crash_report import CrashReport
from app.services.crash_grouper import generate_fingerprint

router = APIRouter()


@router.post("/crashes", status_code=201)
async def submit_crash(
    body: dict[str, Any],
    session: dict[str, Any] = Depends(get_sdk_session),
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """Accepts the SDK crash payload: {error, stack_trace, timestamp, extra}.

    Device, platform and version are resolved from the session device.
    """
    device = await get_or_create_session_device(db, session)
    error = str(body.get("error", "Error"))
    stacktrace = str(body.get("stack_trace") or body.get("stacktrace") or "")
    error_type = (error.split(":", 1)[0] or "Error")[:255]
    now = datetime.now(timezone.utc)

    fingerprint = generate_fingerprint(error_type, stacktrace)
    result = await db.execute(select(CrashGroup).where(CrashGroup.fingerprint == fingerprint))
    group = result.scalar_one_or_none()
    if group:
        group.count += 1
        group.last_seen_at = now
    else:
        group = CrashGroup(
            project_id=session["project_id"],
            mode_id=session["mode_id"],
            fingerprint=fingerprint,
            title=f"{error_type}: {error[:100]}",
            first_seen_at=now,
            last_seen_at=now,
            count=1,
            status=CrashGroupStatusEnum.open,
        )
        db.add(group)
        await db.flush()

    report = CrashReport(
        project_id=session["project_id"],
        mode_id=session["mode_id"],
        device_id=device.id,
        group_id=group.id,
        error_type=error_type,
        error_message=error,
        stacktrace=stacktrace,
        app_version=device.app_version or "0.0.0",
        build_number=str(device.build_number or 0),
        platform=device.platform or session.get("platform", "unknown"),
        os_version=device.os_version or "unknown",
        device_model=device.device_model or "unknown",
        extra=body.get("extra"),
        created_at=now,
    )
    db.add(report)
    await db.flush()
    return {"status": "recorded", "group_id": str(group.id)}
