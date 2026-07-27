from __future__ import annotations

from typing import Any

from app.agents.dispatcher import dispatch_jd_check, dispatch_text_classification


async def run_agentic_analysis(text: str) -> list[dict[str, Any]]:
    """Entry point for the agentic layer, called once per analyze request.

    This is a thin pass-through to the dispatcher today. The seam exists so a
    future session/follow-up context (e.g. "why was this flagged?") can be
    added here later without changing what callers pass in.
    """
    return await dispatch_text_classification(text)


async def check_jd_validity(text: str) -> dict[str, Any] | None:
    """Ask the JD-analyzer skill whether text has enough concrete detail to review.

    Returns None when agents are disabled or the check fails, signalling
    callers to fall back to the regex/keyword heuristic instead.
    """
    return await dispatch_jd_check(text)
