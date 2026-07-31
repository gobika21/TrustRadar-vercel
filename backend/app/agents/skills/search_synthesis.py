from __future__ import annotations

import json
import re

from app.agents.client import SEARCH_SYNTHESIS_MODEL, get_client
from app.agents.safety import wrap_untrusted

SYSTEM_PROMPT = """You judge how much risk web search results signal about a company or domain \
being checked for a job/recruitment scam. Respond with ONLY a JSON object, no prose, no \
markdown fences:
{"severity": "high|medium|info", "reasoning": "One sentence."}
Use "high" ONLY if a result is unambiguously about the exact target company or domain named in \
the search query, in a scam-warning, fraud, or complaint context. Before using "high", check: is \
this genuinely the same organization, or just a different company/page that happens to share a \
word, an industry, or a similar-sounding name with the target? A result about "Orbital \
Recruitment" is NOT evidence about a target company called "Orbitworks" or "Loft Orbital" just \
because they share the word "orbital" -- these are different organizations, not the same one \
under a variant spelling. If you are not confident the result is about the exact same entity, \
use "medium" or "info" instead, and say so in your reasoning.
A result from a generic reputation-checker site (Scamadviser, "is this a scam or legit?", \
Trustpilot, scam-detector, etc.) is NOT by itself evidence the domain was flagged as fraudulent \
-- these tools auto-generate a "check this site" page for nearly every domain on the internet, \
legitimate or not, purely because someone searched for it. The mere existence of such a page is \
not a scam report. Only use "high" for one of these if the result's own title or snippet states \
an actual negative finding (e.g. "flagged as a scam", "low trust score", specific fraud reports) \
-- not just that a checker page exists for the domain. If all you can tell is that a reputation \
page exists, that's "medium" at most, not "high".
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
