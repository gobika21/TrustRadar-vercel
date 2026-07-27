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

        _client = anthropic.AsyncAnthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    return _client
