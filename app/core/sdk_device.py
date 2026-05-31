from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.device import Device


async def get_or_create_session_device(db: AsyncSession, session: dict) -> Device:
    """Look up the most recently seen Device for (project_id, mode_id); create if none."""
    result = await db.execute(
        select(Device)
        .where(
            Device.project_id == session["project_id"],
            Device.mode_id == session["mode_id"],
        )
        .order_by(Device.last_seen_at.desc())
        .limit(1)
    )
    device = result.scalar_one_or_none()
    if device:
        return device
    now = datetime.now(timezone.utc)
    device = Device(
        project_id=session["project_id"],
        mode_id=session["mode_id"],
        install_id=f"sdk-session-{session['version_id']}",
        platform=session["platform"],
        app_version="0.0.0",
        first_seen_at=now,
        last_seen_at=now,
        last_active_at=now,
    )
    db.add(device)
    await db.flush()
    return device
