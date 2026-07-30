from __future__ import annotations

from typing import Any

from app.agents.client import agents_enabled
from app.agents.skills.classifier import classify_scam_intent
from app.agents.skills.extractor import extract_job_fields
from app.agents.skills.jd_analyzer import analyze_jd


async def dispatch_extraction(text: str) -> dict[str, Any] | None:
    if not agents_enabled() or not text.strip():
        return None
    return await extract_job_fields(text)


async def dispatch_text_classification(
    text: str, extracted: dict[str, Any] | None = None
) -> list[dict[str, Any]]:
    if not agents_enabled() or not text.strip():
        return []
    return await classify_scam_intent(text, extracted)


async def dispatch_jd_check(text: str) -> dict[str, Any] | None:
    if not agents_enabled() or not text.strip():
        return None
    return await analyze_jd(text)
