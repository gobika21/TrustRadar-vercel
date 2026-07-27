from __future__ import annotations

import json
import re

from app.agents.client import SEARCH_SYNTHESIS_MODEL, get_client
from app.agents.safety import wrap_untrusted

SYSTEM_PROMPT = """You judge how much risk web search results signal about a company or domain \
being checked for a job/recruitment scam. Respond with ONLY a JSON object, no prose, no \
markdown fences:
{"severity": "high|medium|info", "reasoning": "One sentence."}
Use "high" if a result specifically names or clearly refers to the target company or domain in \
a scam-warning, fraud, or complaint context.
Use "medium" if the results discuss job/recruitment scams, fraud, or fake-job warnings in \
general -- even if they do not name the target company specifically. Generic scam-awareness \
articles (FTC, BBB, "how to spot a fake job offer", etc.) count as "medium", not "info", \
because their presence in top results means no positive evidence of the company's legitimacy \
was found either -- do not treat generic scam content as a safe/neutral signal.
Use "info" only if the results are unrelated to job/recruitment scams altogether -- for \
example the company's own official site, unrelated news, or completely off-topic pages."""


async def judge_search_relevance(query: str, result_text: str) -> dict[str, str] | None:
    client = get_client()
    if client is None or not result_text.strip():
        return None

    prompt = f"Search query (target company/domain): {query}\n\n{wrap_untrusted('web search results', result_text[:3000])}"

    try:
        response = await client.messages.create(
            model=SEARCH_SYNTHESIS_MODEL,
            max_tokens=200,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = response.content[0].text if response.content else "{}"
        match = re.search(r"\{.*\}", raw.strip(), re.DOTALL)
        if not match:
            return None
        payload = json.loads(match.group(0))
        severity = payload.get("severity")
        if severity not in {"high", "medium", "info"}:
            return None
        return {"severity": severity, "reasoning": str(payload.get("reasoning", ""))[:200]}
    except Exception:
        return None
