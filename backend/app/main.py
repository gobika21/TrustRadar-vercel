from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from time import perf_counter
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
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
from app.models import Evidence
from app.scoring import STRONG_SCAM_PATTERN_IDS, evidence_score, pattern_check, score_to_tier
from app.storage import clear_analyses, get_analysis, initialize_database, list_analyses, save_analysis
from app.text_utils import domain_from_url, extract_emails, extract_urls, looks_like_valid_jd
from app.uploads import read_uploads
from app.verification import build_search_query, rdap_lookup, search_result_severity, verify_live


app = FastAPI(title="TrustRadar API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://trustradar-v1-frontend.s3-website.eu-north-1.amazonaws.com",
        "https://d1wofahxptye8m.cloudfront.net",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup() -> None:
    initialize_database()


@app.get("/api/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/metrics")
async def metrics() -> dict[str, Any]:
    return metrics_payload()


@app.get("/api/history")
async def history(limit: int = 20) -> list[dict[str, Any]]:
    return list_analyses(max(1, min(limit, 100)))


@app.get("/api/history/{entry_id}")
async def history_entry(entry_id: str) -> dict[str, Any]:
    entry = get_analysis(entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="Analysis history entry not found.")
    return entry


@app.delete("/api/history")
async def delete_history() -> dict[str, str]:
    clear_analyses()
    return {"status": "cleared"}


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
    analysis_text = "\n\n".join(part for part in [text.strip(), uploaded_text] if part)
    METRICS["uploaded_files"] += len(uploaded_files)

    pattern_score, findings = pattern_check(analysis_text)
    has_strong_scam_signal = any(finding["id"] in STRONG_SCAM_PATTERN_IDS for finding in findings)

    if analysis_text.strip() and not submitted_urls and not has_strong_scam_signal:
        jd_check = await check_jd_validity(analysis_text)
        is_valid_jd = jd_check["is_valid_jd"] if jd_check is not None else looks_like_valid_jd(analysis_text)
        if not is_valid_jd:
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
            llm_findings, live_evidence = cached
        else:
            llm_findings, live_evidence = await asyncio.gather(
                run_agentic_analysis(analysis_text),
                verify_live(analysis_text, submitted_urls),
            )
            store_cached_verification(analysis_text, submitted_urls, (llm_findings, live_evidence))
        findings = findings + llm_findings
        pattern_score += sum(item["score"] for item in llm_findings)
        assert_job_url_accessible(job_url, live_evidence)
        total_score = min(100, pattern_score + evidence_score(live_evidence))
        tier, tier_level = score_to_tier(total_score)
    except Exception:
        METRICS["analysis_errors"] += 1
        raise
    finally:
        METRICS["total_analysis_ms"] += (perf_counter() - started_at) * 1000

    summary = "No strong scam indicators were found in the available evidence. Verify the employer before sharing personal information."
    if tier_level in {"critical", "high"}:
        summary = "Multiple risk signals need independent verification before you reply, pay, or share identity documents."
    elif tier_level == "medium":
        summary = "Some signals require follow-up before you trust the posting or recruiter."

    result = {
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
        "recommendations": [
            "Do not pay fees or deposits for interviews, visas, training, or equipment.",
            "Confirm the recruiter through the company website or an official company email domain.",
            "Search the company and recruiter name with terms such as scam, fraud, complaint, and fake job.",
            "Do not share passport, Emirates ID, bank details, or OTPs until the employer is verified.",
        ],
    }
    save_analysis(
        {
            "id": str(uuid4()),
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
