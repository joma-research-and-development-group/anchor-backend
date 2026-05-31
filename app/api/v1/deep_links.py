from fastapi import APIRouter, Depends, HTTPException, Header
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.models.deep_link import DeepLink

router = APIRouter()


@router.get("/dl/{slug}")
async def resolve_deep_link(
    slug: str,
    user_agent: str | None = Header(None),
    db: AsyncSession = Depends(get_db),
) -> RedirectResponse:
    result = await db.execute(select(DeepLink).where(DeepLink.slug == slug))
    link = result.scalar_one_or_none()
    if not link:
        raise HTTPException(status_code=404, detail="Deep link not found")

    link.clicks += 1
    await db.flush()

    # Determine platform from user-agent
    ua = (user_agent or "").lower()
    if "iphone" in ua or "ipad" in ua or "ios" in ua:
        url = link.ios_url or link.fallback_url
    elif "android" in ua:
        url = link.android_url or link.fallback_url
    else:
        url = link.web_url or link.fallback_url

    # Append UTM params if present
    params = []
    if link.utm_source:
        params.append(f"utm_source={link.utm_source}")
    if link.utm_medium:
        params.append(f"utm_medium={link.utm_medium}")
    if link.utm_campaign:
        params.append(f"utm_campaign={link.utm_campaign}")
    if params:
        separator = "&" if "?" in url else "?"
        url = f"{url}{separator}{'&'.join(params)}"

    return RedirectResponse(url=url, status_code=302)
