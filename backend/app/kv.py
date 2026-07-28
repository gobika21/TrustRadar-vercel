from __future__ import annotations

import os

from upstash_redis import Redis

_redis: Redis | None = None
_redis_checked = False


def get_redis() -> Redis | None:
    """Return the shared Vercel KV (Upstash Redis) client, or None if not configured.

    Callers must handle None by failing open (rate limiting) or treating it as a
    cache miss (response cache) -- this keeps local dev working without KV set up.
    """
    global _redis, _redis_checked
    if _redis_checked:
        return _redis
    _redis_checked = True
    url = os.environ.get("KV_REST_API_URL")
    token = os.environ.get("KV_REST_API_TOKEN")
    if url and token:
        _redis = Redis(url=url, token=token)
    return _redis
