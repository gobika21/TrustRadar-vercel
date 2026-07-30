from __future__ import annotations

import json
import re
from typing import Any

from app.agents.client import CLASSIFIER_MODEL, get_client
from app.agents.safety import redact_pii

SYSTEM_PROMPT = """You extract structured facts from a job posting or recruiter message -- \
you do not judge whether it's a scam, only pull out what's actually stated in the text. \
Respond with ONLY a JSON object matching this schema, no prose, no markdown fences:
{
  "company": "string or null",
  "role": "string or null",
  "salary": "string or null",
  "requirements": ["short phrase", ...],
  "contact_email": "string or null",
  "contact_url": "string or null",
  "application_reference": "string or null -- a job ID, requisition number, or reference to a specific application",
  "interview_datetime": "string or null -- any date/time mentioned for an interview or next step",
  "greeting_tone": "casual|formal|neutral",
  "urgency_language": true|false,
  "process_mentioned": true|false
}
For "process_mentioned": true only if the message references a real hiring process --
an application being reviewed, a screening step, an assessment, multiple rounds -- not just
the bare word "interview" with nothing else behind it.
Only extract what is explicitly present in the text -- use null/false/[] for anything not \
stated. Do not infer, guess, or fill in plausible-sounding values for missing details."""


async def extract_job_fields(text: str) -> dict[str, Any] | None:
    client = get_client()
    if client is None or not text.strip():
        return None

    safe_text = redact_pii(text)[:6000]

    try:
        response = await client.messages.create(
            model=CLASSIFIER_MODEL,
            max_tokens=500,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": f"Text to extract from:\n\n{safe_text}"}],
        )
        raw = response.content[0].text if response.content else "{}"
        payload = _parse_json(raw)
        if not payload:
            return None
        return _normalize(payload)
    except Exception:
        return None


def _normalize(payload: dict[str, Any]) -> dict[str, Any]:
    requirements = payload.get("requirements")
    if not isinstance(requirements, list):
        requirements = []
    tone = payload.get("greeting_tone")
    if tone not in {"casual", "formal", "neutral"}:
        tone = "neutral"
    return {
        "company": _clean_str(payload.get("company")),
        "role": _clean_str(payload.get("role")),
        "salary": _clean_str(payload.get("salary")),
        "requirements": [str(item)[:80] for item in requirements if str(item).strip()][:8],
        "contact_email": _clean_str(payload.get("contact_email")),
        "contact_url": _clean_str(payload.get("contact_url")),
        "application_reference": _clean_str(payload.get("application_reference")),
        "interview_datetime": _clean_str(payload.get("interview_datetime")),
        "greeting_tone": tone,
        "urgency_language": bool(payload.get("urgency_language")),
        "process_mentioned": bool(payload.get("process_mentioned")),
    }


def _clean_str(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    value = value.strip()
    return value[:200] if value else None


def _parse_json(raw: str) -> dict[str, Any]:
    match = re.search(r"\{.*\}", raw.strip(), re.DOTALL)
    if not match:
        return {}
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        return {}
