from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.sdk_auth import get_sdk_session
from app.models.crash_group import CrashGroup, CrashGroupStatusEnum
from app.models.crash_report import CrashReport
from app.models.device import Device
from app.schemas.crash import CrashReportCreate, CrashReportResponse
from app.services.crash_grouper import generate_fingerprint

router = APIRouter()


@router.post("/crashes", response_model=CrashReportResponse, status_code=201)
async def submit_crash(
    body: CrashReportCreate,
    session: dict[str, Any] = Depends(get_sdk_session),
    db: AsyncSession = Depends(get_db),
) -> CrashReport:
    # Resolve device
    result = await db.execute(
        select(Device).where(
            Device.project_id == session["project_id"],
            Device.mode_id == session["mode_id"],
            Device.install_id == body.install_id,
        )
    )
    device = result.scalar_one_or_none()
    device_id = device.id if device else None

    # Generate fingerprint and find/create group
    fingerprint = generate_fingerprint(body.error_type, body.stacktrace)
    now = datetime.now(timezone.utc)

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
            title=f"{body.error_type}: {body.error_message[:100]}",
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
        device_id=device_id,
        group_id=group.id,
        error_type=body.error_type,
        error_message=body.error_message,
        stacktrace=body.stacktrace,
        app_version=body.app_version,
        build_number=body.build_number,
        platform=body.platform,
        os_version=body.os_version,
        device_model=body.device_model,
        extra=body.extra,
        created_at=now,
    )
    db.add(report)
    await db.flush()
    return report
