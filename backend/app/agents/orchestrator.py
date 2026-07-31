from __future__ import annotations

from typing import Any

from app.agents.dispatcher import dispatch_extraction, dispatch_jd_check, dispatch_text_classification


async def run_agentic_analysis(
    text: str, sourced_from_platform: bool = False
) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
    """Entry point for the agentic layer, called once per analyze request.

    Runs as two separate NLP steps rather than one: extraction pulls structured
    facts out of the raw text (company, role, salary, contact info, tone),
    then evaluation reasons over those facts to judge suspicion -- instead of
    re-parsing the raw text from scratch for every judgment call. Returns both
    the scam-risk findings and the extracted facts, so the facts can also be
    shown to the user as evidence.

    sourced_from_platform tells the classifier this text was fetched from a
    job-hosting platform's own listing page rather than pasted from a direct
    message, so it doesn't penalize the normal absence of contact/salary
    details that a platform listing wouldn't include in the description body.
    """
    extracted = await dispatch_extraction(text)
    findings = await dispatch_text_classification(text, extracted, sourced_from_platform)
    return findings, extracted


async def check_jd_validity(text: str) -> dict[str, Any] | None:
    """Ask the JD-analyzer skill whether text has enough concrete detail to review.

    Returns None when agents are disabled or the check fails, signalling
    callers to fall back to the regex/keyword heuristic instead.
    """
    return await dispatch_jd_check(text)
