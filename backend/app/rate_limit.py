from __future__ import annotations

from fastapi import HTTPException, Request

from app.kv import get_redis

WINDOW_SECONDS = 60
MAX_REQUESTS_PER_WINDOW = 10


def _client_ip(request: Request) -> str:
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def enforce_rate_limit(request: Request) -> None:
    redis = get_redis()
    if redis is None:
        return

    client_ip = _client_ip(request)
    key = f"ratelimit:{client_ip}"
    count = redis.incr(key)
    if count == 1:
        redis.expire(key, WINDOW_SECONDS)
    if count > MAX_REQUESTS_PER_WINDOW:
        raise HTTPException(
            status_code=429,
            detail=f"Too many requests. Limit is {MAX_REQUESTS_PER_WINDOW} analyses per {WINDOW_SECONDS} seconds. Please wait and try again.",
        )
