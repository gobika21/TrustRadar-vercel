from __future__ import annotations

import os
from datetime import datetime, timezone

CLASSIFIER_MODEL = "claude-haiku-4-5-20251001"
VISION_MODEL = "claude-haiku-4-5-20251001"
SEARCH_SYNTHESIS_MODEL = "claude-haiku-4-5-20251001"

# Caps total real Claude API calls per day across all users and all five
# skills combined, independent of the per-IP rate limit in rate_limit.py --
# that limit only stops one abusive IP, it does nothing to bound total spend
# when many different people are using the app at once. Configurable via env
# var so it can be tuned without a redeploy.
DEFAULT_MAX_DAILY_AGENT_CALLS = 300

_client = None


def agents_enabled() -> bool:
    return bool(os.environ.get("ANTHROPIC_API_KEY"))


def _agent_budget_available() -> bool:
    """Whether today's Claude call budget still has room.

    Fails open (allows the call) when Redis isn't configured, matching the
    same fail-open convention rate_limit.py already uses -- local dev without
    KV set up shouldn't lose agent functionality. This means budget
    protection itself depends on Redis being up in production; that's an
    accepted tradeoff for consistency with the rest of the app, not an
    oversight.
    """
    from app.kv import get_redis

    redis = get_redis()
    if redis is None:
        return True
    max_calls = int(os.environ.get("MAX_DAILY_AGENT_CALLS", DEFAULT_MAX_DAILY_AGENT_CALLS))
    today = datetime.now(timezone.utc).date().isoformat()
    key = f"agent-budget:{today}"
    count = redis.incr(key)
    if count == 1:
        redis.expire(key, 86400)
    return count <= max_calls


def get_client():
    global _client
    if not agents_enabled():
        return None
    if not _agent_budget_available():
        return None
    if _client is None:
        import anthropic

        # Without an explicit timeout, the SDK's default is long enough that a
        # slow/stuck call can outlive the serverless function's own execution
        # limit -- the platform kills the function abruptly instead of this
        # call failing within the app's own error handling, which already
        # falls back to the regex/heuristic path on any exception here.
        # max_retries is capped low for the same reason: the SDK's default
        # retries would multiply worst-case latency for a fallback that's
        # already available immediately.
        _client = anthropic.AsyncAnthropic(
            api_key=os.environ["ANTHROPIC_API_KEY"], timeout=10.0, max_retries=1
        )
    return _client
