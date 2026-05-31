import hashlib
from typing import Any

from fastapi import APIRouter, Depends, Header, Query, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.sdk_auth import get_sdk_session
from app.models.localization import LocalizationEntry

router = APIRouter()


@router.get("/localization", response_model=dict[str, str])
async def get_localization(
    response: Response,
    locale: str = Query(...),
    if_none_match: str | None = Header(None),
    session: dict[str, Any] = Depends(get_sdk_session),
    db: AsyncSession = Depends(get_db),
) -> Any:
    result = await db.execute(
        select(LocalizationEntry).where(
            LocalizationEntry.project_id == session["project_id"],
            LocalizationEntry.mode_id == session["mode_id"],
            LocalizationEntry.locale == locale,
        ).order_by(LocalizationEntry.key)
    )
    entries = list(result.scalars().all())
    data = {e.key: e.value for e in entries}
    content_str = "|".join(f"{k}={v}" for k, v in sorted(data.items()))
    etag = hashlib.md5(content_str.encode()).hexdigest()  # noqa: S324
    if if_none_match and if_none_match.strip('"') == etag:
        return Response(status_code=304)
    response.headers["ETag"] = f'"{etag}"'
    return data
