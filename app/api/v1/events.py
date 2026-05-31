from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.sdk_auth import get_sdk_session
from app.core.sdk_device import get_or_create_session_device
from app.models.event import Event

router = APIRouter()


def _parse_ts(value: Any) -> datetime:
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            pass
    return datetime.now(timezone.utc)


@router.post("/events", status_code=201)
async def ingest_events(
    body: dict[str, Any],
    session: dict[str, Any] = Depends(get_sdk_session),
    db: AsyncSession = Depends(get_db),
) -> dict[str, int]:
    device = await get_or_create_session_device(db, session)
    events = body.get("events", [])
    for ev in events:
        db.add(Event(
            project_id=session["project_id"],
            mode_id=session["mode_id"],
            device_id=device.id,
            name=ev.get("name", "unknown"),
            properties=ev.get("properties") or {},
            session_id=ev.get("session_id"),
            created_at=_parse_ts(ev.get("timestamp")),
        ))
    await db.flush()
    return {"ingested": len(events)}


@router.post("/events/session")
async def session_event(
    body: dict[str, Any],
    session: dict[str, Any] = Depends(get_sdk_session),
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    device = await get_or_create_session_device(db, session)
    event_name = f"session_{body.get('action', 'unknown')}"
    db.add(Event(
        project_id=session["project_id"],
        mode_id=session["mode_id"],
        device_id=device.id,
        name=event_name,
        session_id=body.get("session_id"),
        created_at=datetime.now(timezone.utc),
    ))
    await db.flush()
    return {"status": "ok", "event": event_name}
