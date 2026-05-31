import time
from typing import Any

from fastapi import APIRouter
from redis.asyncio import Redis
from sqlalchemy import text

from app.core.config import settings
from app.core.db import async_session

router = APIRouter()

_start_time = time.time()


@router.get("/health")
async def health_check() -> dict[str, Any]:
    db_ok = False
    try:
        async with async_session() as session:
            await session.execute(text("SELECT 1"))
            db_ok = True
    except Exception:
        pass

    redis_ok = False
    try:
        redis = Redis.from_url(settings.REDIS_URL, decode_responses=True)
        await redis.ping()
        redis_ok = True
        await redis.aclose()
    except Exception:
        pass

    status = "ok" if (db_ok and redis_ok) else "degraded"
    return {
        "status": status,
        "db": db_ok,
        "redis": redis_ok,
        "uptime": round(time.time() - _start_time, 1),
    }
