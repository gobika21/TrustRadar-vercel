from __future__ import annotations

import asyncio
import traceback
from datetime import datetime, timezone
from time import perf_counter
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, File, Form, HTTPException, Request, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from app.agents.orchestrator import check_jd_validity, run_agentic_analysis
from app.analysis import (
    assert_job_url_accessible,
    build_agent_workflow,
    build_recommendation,
    evidence_to_payload,
)
from app.cache import get_cached_verification, store_cached_verification
from app.rate_limit import enforce_rate_limit
from app.metrics import METRICS, build_usage_snapshot, metrics_payload
from app.scoring import STRONG_SCAM_PATTERN_IDS, evidence_score, pattern_check, score_to_tier
from app.storage import (
    clear_analyses,
    get_analysis,
    initialize_database,
    list_analyses,
    list_blocked_attempts,
    record_blocked_attempt,
    save_analysis,
)
from app.text_utils import domain_from_url, extract_emails, extract_urls, looks_like_valid_jd
from app.uploads import read_uploads
from app.verification import (
    fetch_submitted_job_descriptions,
    verify_live,
)


app = FastAPI(title="TrustRadar API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup() -> None:
    try:
        initialize_database()
    except Exception as exc:
        # Don't let a missing/misconfigured Postgres integration take the whole
        # app down -- history storage will raise on its own when actually used,
        # but /api/health and other non-DB endpoints should still work.
        print(f"Warning: database initialization failed at startup: {exc}")


@app.get("/api/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/metrics")
async def metrics() -> dict[str, Any]:
    return metrics_payload()


@app.get("/api/history")
async def history(response: Response, limit: int = 20) -> list[dict[str, Any]]:
    response.headers["Cache-Control"] = "no-store"
    try:
        return list_analyses(max(1, min(limit, 100)))
    except Exception as exc:
        # A missing/misconfigured Postgres integration, or a transient connection
        # failure, shouldn't surface as an unhandled 500 -- that response loses its
        # CORS headers (Starlette's error handler sits outside CORSMiddleware),
        # which the browser then reports as an opaque "Failed to fetch" with no
        # way to distinguish it from a real network outage. Degrade to an empty
        # list instead so the frontend gets a normal, readable response.
        print(f"Warning: failed to load history: {exc}")
        return []


@app.get("/api/history/{entry_id}")
async def history_entry(entry_id: str, response: Response) -> dict[str, Any]:
    response.headers["Cache-Control"] = "no-store"
    try:
        entry = get_analysis(entry_id)
    except Exception as exc:
        print(f"Warning: failed to load history entry {entry_id}: {exc}")
        entry = None
    if entry is None:
        raise HTTPException(status_code=404, detail="Analysis history entry not found.")
    return entry


@app.delete("/api/history")
async def delete_history() -> dict[str, str]:
    try:
        clear_analyses()
    except Exception as exc:
        print(f"Warning: failed to clear history: {exc}")
    return {"status": "cleared"}


@app.get("/api/blocked-attempts")
async def blocked_attempts(response: Response, limit: int = 50) -> list[dict[str, Any]]:
    """Submissions that consumed a Claude call but were rejected before scoring.

    Not surfaced in the app's own UI -- this is purely for checking API usage
    that wouldn't otherwise show up in /api/history, since a rejected
    submission still costs a real API call but never reaches save_analysis.
    """
    response.headers["Cache-Control"] = "no-store"
    try:
        return list_blocked_attempts(max(1, min(limit, 200)))
    except Exception as exc:
        print(f"Warning: failed to load blocked attempts: {exc}")
        return []


def _log_blocked_attempt(text: str, reason: str) -> None:
    try:
        record_blocked_attempt(
            {
                "id": str(uuid4()),
                "createdAt": datetime.now(timezone.utc).isoformat(),
                "reason": reason[:200],
                "textSnippet": text.strip()[:300],
            }
        )
    except Exception as exc:
        # Same graceful-degradation rule as everywhere else: a logging
        # failure must never block the actual response the caller is
        # waiting for.
        print(f"Warning: failed to record blocked attempt: {exc}")


@app.post("/api/analyze")
async def analyze(
    request: Request,
    text: str = Form(""),
    job_url: str = Form(""),
    recruiter_url: str = Form(""),
    company_url: str = Form(""),
    files: list[UploadFile] = File(default=[]),
) -> dict[str, Any]:
    enforce_rate_limit(request)
    started_at = perf_counter()
    METRICS["analyze_requests"] += 1
    usage_before = METRICS.copy()
    submitted_urls = [url.strip() for url in [job_url, recruiter_url, company_url] if url.strip()]
    uploaded_text, uploaded_files = await read_uploads(files)
    fetched_description = await fetch_submitted_job_descriptions(submitted_urls)
    analysis_text = "\n\n".join(part for part in [text.strip(), uploaded_text, fetched_description] if part)
    METRICS["uploaded_files"] += len(uploaded_files)
    # Only treat the submission as "platform-sourced" when the fetched listing
    # is the *only* content -- if the user also pasted their own text or a
    # screenshot alongside the link, that pasted content should still be
    # judged with the normal cold-message expectations.
    sourced_from_platform = bool(fetched_description.strip()) and not text.strip() and not uploaded_text.strip()

    pattern_score, findings = pattern_check(analysis_text)
    has_strong_scam_signal = any(finding["id"] in STRONG_SCAM_PATTERN_IDS for finding in findings)

    if analysis_text.strip() and not submitted_urls and not has_strong_scam_signal:
        jd_check = await check_jd_validity(analysis_text)
        is_valid_jd = jd_check["is_valid_jd"] if jd_check is not None else looks_like_valid_jd(analysis_text)
        if not is_valid_jd:
            # This branch only runs a real Claude call (the JD-analyzer, above)
            # when agents are enabled, and it exits before ever reaching
            # save_analysis -- log it separately so a rejected attempt doesn't
            # cost money with zero trace anywhere.
            if jd_check is not None:
                _log_blocked_attempt(analysis_text, "jd_gate: insufficient detail")
            raise HTTPException(
                status_code=422,
                detail=(
                    "This doesn't include enough detail to review -- a job post or recruiter message "
                    "should mention a company, role, or requirements. Paste the full job description or "
                    "message text, then run the check again."
                ),
            )

    try:
        cached = get_cached_verification(analysis_text, submitted_urls)
        if cached is not None:
            llm_findings, extracted_fields, live_evidence = cached
        else:
            (llm_findings, extracted_fields), live_evidence = await asyncio.gather(
                run_agentic_analysis(analysis_text, sourced_from_platform),
                verify_live(analysis_text, submitted_urls),
            )
            store_cached_verification(
                analysis_text, submitted_urls, (llm_findings, extracted_fields, live_evidence)
            )
        findings = findings + llm_findings
        pattern_score += sum(item["score"] for item in llm_findings)
        assert_job_url_accessible(job_url, live_evidence)
        total_score = min(100, pattern_score + evidence_score(live_evidence))
        tier, tier_level = score_to_tier(total_score)

        summary = "No strong scam indicators were found in the available evidence. Verify the employer before sharing personal information."
        if tier_level in {"critical", "high"}:
            summary = "Multiple risk signals need independent verification before you reply, pay, or share identity documents."
        elif tier_level == "medium":
            summary = "Some signals require follow-up before you trust the posting or recruiter."

        entry_id = str(uuid4())
        result = {
            "id": entry_id,
            "tier": tier,
            "tier_level": tier_level,
            "score": total_score,
            "summary": summary,
            "recommendation": build_recommendation(tier_level),
            "agent_workflow": build_agent_workflow(analysis_text, submitted_urls, findings, live_evidence),
            "usage": build_usage_snapshot(usage_before),
            "pattern_findings": findings,
            "live_evidence": [evidence_to_payload(item) for item in live_evidence],
            "uploaded_files": uploaded_files,
            "extracted": {
                "urls": extract_urls(analysis_text) + submitted_urls,
                "emails": extract_emails(analysis_text),
            },
            "extracted_fields": extracted_fields,
            "recommendations": [
                "Do not pay fees or deposits for interviews, visas, training, or equipment.",
                "Confirm the recruiter through the company website or an official company email domain.",
                "Search the company and recruiter name with terms such as scam, fraud, complaint, and fake job.",
                "Do not share passport, Emirates ID, bank details, or OTPs until the employer is verified.",
            ],
        }
    except HTTPException as exc:
        # By this point the agentic analysis (up to several real Claude
        # calls) and live verification have already run -- e.g. the job URL
        # turned out to be inaccessible, so assert_job_url_accessible raised
        # instead of returning a scored result. That still cost money and,
        # same as the JD-gate rejection above, never reaches save_analysis.
        _log_blocked_attempt(analysis_text, f"http_{exc.status_code}: {exc.detail}")
        raise
    except Exception:
        METRICS["analysis_errors"] += 1
        # An unhandled exception here is caught by Starlette's error handler
        # *outside* CORSMiddleware, so the response has no CORS headers and the
        # browser reports an opaque "Failed to fetch" with the real cause hidden.
        # Log the full traceback (visible in the platform's function logs) and
        # raise a normal HTTPException instead, which keeps CORS headers intact.
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail="Something went wrong while analyzing this submission. Please try again.",
        )
    finally:
        METRICS["total_analysis_ms"] += (perf_counter() - started_at) * 1000
    try:
        save_analysis(
            {
                "id": entry_id,
                "createdAt": datetime.now(timezone.utc).isoformat(),
                "label": build_history_label(text, job_url, uploaded_files),
                "input": {
                    "text": analysis_text,
                    "linkUrl": job_url,
                    "files": uploaded_files,
                },
                "result": result,
            }
        )
    except Exception as exc:
        # A missing/misconfigured Postgres integration shouldn't block returning
        # an analysis result the user already waited for -- just skip saving it.
        print(f"Warning: failed to save analysis to history: {exc}")
    return result


def build_history_label(text: str, link_url: str, uploaded_files: list[dict[str, str]]) -> str:
    if link_url.strip():
        domain = domain_from_url(link_url.strip())
        return domain or trim_label(link_url.strip())
    if text.strip():
        return trim_label(text.strip())
    if uploaded_files:
        return f"{len(uploaded_files)} uploaded file{'s' if len(uploaded_files) != 1 else ''}"
    return "Untitled check"


def trim_label(value: str) -> str:
    return f"{value[:44]}..." if len(value) > 44 else value
