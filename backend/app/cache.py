from __future__ import annotations

import hashlib
import time
from typing import Any

TTL_SECONDS = 1800

_CACHE: dict[str, tuple[float, Any]] = {}


def _cache_key(text: str, submitted_urls: list[str]) -> str:
    normalized = text.strip().lower() + "|" + "|".join(sorted(url.strip().lower() for url in submitted_urls))
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def get_cached_verification(text: str, submitted_urls: list[str]) -> Any | None:
    if not text.strip():
        return None
    _evict_expired()
    entry = _CACHE.get(_cache_key(text, submitted_urls))
    return entry[1] if entry is not None else None


def store_cached_verification(text: str, submitted_urls: list[str], payload: Any) -> None:
    if not text.strip():
        return
    _CACHE[_cache_key(text, submitted_urls)] = (time.monotonic() + TTL_SECONDS, payload)
    _evict_expired()


def _evict_expired() -> None:
    now = time.monotonic()
    for key in [key for key, (expires_at, _) in _CACHE.items() if expires_at < now]:
        _CACHE.pop(key, None)
