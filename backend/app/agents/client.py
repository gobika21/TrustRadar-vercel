from __future__ import annotations

import os

CLASSIFIER_MODEL = "claude-haiku-4-5-20251001"
VISION_MODEL = "claude-haiku-4-5-20251001"
SEARCH_SYNTHESIS_MODEL = "claude-haiku-4-5-20251001"

_client = None


def agents_enabled() -> bool:
    return bool(os.environ.get("ANTHROPIC_API_KEY"))


def get_client():
    global _client
    if not agents_enabled():
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
