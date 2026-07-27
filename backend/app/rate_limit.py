from __future__ import annotations

import time
from collections import defaultdict

from fastapi import HTTPException, Request

WINDOW_SECONDS = 60
MAX_REQUESTS_PER_WINDOW = 10

_HITS: dict[str, list[float]] = defaultdict(list)


def _client_ip(request: Request) -> str:
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def enforce_rate_limit(request: Request) -> None:
    client_ip = _client_ip(request)
    now = time.monotonic()
    window_start = now - WINDOW_SECONDS
    hits = _HITS[client_ip]
    hits[:] = [ts for ts in hits if ts > window_start]
    if len(hits) >= MAX_REQUESTS_PER_WINDOW:
        raise HTTPException(
            status_code=429,
            detail=f"Too many requests. Limit is {MAX_REQUESTS_PER_WINDOW} analyses per {WINDOW_SECONDS} seconds. Please wait and try again.",
        )
    hits.append(now)
