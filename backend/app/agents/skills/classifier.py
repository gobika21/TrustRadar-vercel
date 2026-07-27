from __future__ import annotations

import json
import re
from typing import Any

from app.agents.client import CLASSIFIER_MODEL, get_client
from app.agents.safety import redact_pii

SYSTEM_PROMPT = """You are a job-scam detection assistant embedded in TrustRadar. You read a \
job posting or recruiter message and identify scam risk signals that a rule-based regex \
system would miss: paraphrased fee requests, subtle pressure tactics, implausible offers, \
and inconsistencies a keyword search cannot catch. Respond with ONLY a JSON object matching \
this schema, no prose, no markdown fences:
{"findings": [{"id": "short_snake_case_id", "label": "Short label", "severity": "critical|high|medium|info", "score": <int 0-25>, "explanation": "One sentence why."}]}
Only include findings for genuine signals actually present in the text. If the text reads as \
a normal, legitimate posting, return {"findings": []}. Do not flag anything that is explicitly \
negated (e.g. "no upfront fee" is reassuring, not a risk) or already obviously benign."""


async def classify_scam_intent(text: str) -> list[dict[str, Any]]:
    client = get_client()
    if client is None or not text.strip():
        return []

    safe_text = redact_pii(text)[:6000]

    try:
        response = await client.messages.create(
            model=CLASSIFIER_MODEL,
            max_tokens=800,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": f"Job posting or message to review:\n\n{safe_text}"}],
        )
        raw = response.content[0].text if response.content else "{}"
        payload = _parse_json(raw)
        findings = payload.get("findings", [])
        return [_normalize_finding(item) for item in findings if isinstance(item, dict) and item.get("label")]
    except Exception:
        return []


def _normalize_finding(item: dict[str, Any]) -> dict[str, Any]:
    severity = item.get("severity")
    if severity not in {"critical", "high", "medium", "info"}:
        severity = "medium"
    try:
        score = max(0, min(25, int(item.get("score", 8))))
    except (TypeError, ValueError):
        score = 8
    return {
        "id": f"llm_{item.get('id', 'signal')}",
        "label": str(item.get("label", "LLM signal"))[:80],
        "severity": severity,
        "score": score,
        "explanation": str(item.get("explanation", ""))[:300],
        "matches": 1,
        "source": "llm_classifier",
    }


def _parse_json(raw: str) -> dict[str, Any]:
    match = re.search(r"\{.*\}", raw.strip(), re.DOTALL)
    if not match:
        return {}
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        return {}
