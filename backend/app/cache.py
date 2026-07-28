from __future__ import annotations

import base64
import hashlib
import pickle
from typing import Any

from app.kv import get_redis

TTL_SECONDS = 1800


def _cache_key(text: str, submitted_urls: list[str]) -> str:
    normalized = text.strip().lower() + "|" + "|".join(sorted(url.strip().lower() for url in submitted_urls))
    return "cache:" + hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def get_cached_verification(text: str, submitted_urls: list[str]) -> Any | None:
    if not text.strip():
        return None
    redis = get_redis()
    if redis is None:
        return None
    raw = redis.get(_cache_key(text, submitted_urls))
    if raw is None:
        return None
    return pickle.loads(base64.b64decode(raw))


def store_cached_verification(text: str, submitted_urls: list[str], payload: Any) -> None:
    if not text.strip():
        return
    redis = get_redis()
    if redis is None:
        return
    encoded = base64.b64encode(pickle.dumps(payload)).decode("ascii")
    redis.set(_cache_key(text, submitted_urls), encoded, ex=TTL_SECONDS)
