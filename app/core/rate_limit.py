import time
from typing import Any

from fastapi import HTTPException, Request, status
from redis.asyncio import Redis

from app.core.config import settings

_redis: Redis | None = None


async def get_redis() -> Redis:
    global _redis
    if _redis is None:
        _redis = Redis.from_url(settings.REDIS_URL, decode_responses=True)
    return _redis


async def _check_rate_limit(key: str, limit: int, window_sec: int) -> None:
    redis = await get_redis()
    now = time.time()
    window_start = now - window_sec
    pipe = redis.pipeline()
    pipe.zremrangebyscore(key, 0, window_start)
    pipe.zadd(key, {str(now): now})
    pipe.zcard(key)
    pipe.expire(key, window_sec)
    results = await pipe.execute()
    count = results[2]
    if count > limit:
        retry_after = int(window_sec - (now - window_start))
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded",
            headers={"Retry-After": str(max(1, retry_after))},
        )


def rate_limit_ip(limit: int, window_sec: int) -> Any:
    async def dependency(request: Request) -> None:
        ip = request.client.host if request.client else "unknown"
        key = f"rl:ip:{request.url.path}:{ip}"
        await _check_rate_limit(key, limit, window_sec)

    return dependency


def rate_limit_key(limit: int, window_sec: int) -> Any:
    async def dependency(request: Request) -> None:
        api_key = request.headers.get("X-Anchor-Key", "unknown")[:20]
        key = f"rl:key:{request.url.path}:{api_key}"
        await _check_rate_limit(key, limit, window_sec)

    return dependency
