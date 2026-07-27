from __future__ import annotations

import re
from typing import Any

from fastapi import HTTPException

from app.models import Evidence
from app.text_utils import extract_urls


def assert_job_url_accessible(job_url: str, evidence: list[Evidence]) -> None:
    if not job_url.strip():
        return

    normalized_job_url = job_url.strip()
    for item in evidence:
        if item.label != "URL reachability" or item.source != normalized_job_url:
            continue
        status_match = re.search(r"HTTP\s+(\d{3})", item.detail)
        status_code = int(status_match.group(1)) if status_match else None
        is_inaccessible_status = status_code is not None and status_code >= 400
        if item.status in {"failed", "blocked"} or is_inaccessible_status:
            raise HTTPException(
                status_code=422,
                detail=(
                    "TrustRadar could not access the job posting URL, so this link cannot be assessed reliably. "
                    "Open the page in your browser and paste the visible job description, or try a public posting URL."
                ),
            )
        return


def evidence_to_payload(item: Evidence) -> dict[str, Any]:
    return {
        **item.__dict__,
        "links": extract_evidence_links(item),
    }


def extract_evidence_links(item: Evidence) -> list[dict[str, str]]:
    links: list[dict[str, str]] = []
    if item.source.startswith(("http://", "https://")):
        links.append({"label": item.label, "url": item.source})
    if item.label == "Web search":
        for title, url in re.findall(r"([^|()]+?)\s*\((https?://[^)]+)\)", item.detail):
            links.append({"label": title.strip()[:90], "url": url.strip()})
    return links[:4]


def build_recommendation(tier_level: str) -> dict[str, str]:
    if tier_level == "critical":
        return {
            "label": "Don't apply to this",
            "tone": "danger",
            "detail": "This posting matches strong scam patterns. Do not pay, reply, or share personal or banking details.",
        }
    if tier_level == "high":
        return {
            "label": "Do not engage yet",
            "tone": "danger",
            "detail": "Verify the employer through an official channel before replying, paying, or sharing documents.",
        }
    if tier_level == "medium":
        return {
            "label": "Apply with caution",
            "tone": "review",
            "detail": "There are signals that need follow-up. Confirm the company, recruiter, and role before continuing.",
        }
    return {
        "label": "Likely safe to apply",
        "tone": "safe",
        "detail": "No strong scam indicators were found, but still confirm the employer identity before sharing personal data.",
    }


def build_agent_workflow(
    text: str,
    submitted_urls: list[str],
    findings: list[dict[str, Any]],
    live_evidence: list[Evidence],
) -> list[dict[str, str]]:
    live_labels = {item.label for item in live_evidence}
    web_search_done = any(item.label == "Web search" and item.status != "skipped" for item in live_evidence)
    urls_found = len(set(submitted_urls + extract_urls(text)))
    domains_checked = len({item.source for item in live_evidence if item.label in {"DNS resolution", "Domain age", "Domain registration", "ATS platform"}})

    return [
        {
            "step": "Evidence intake",
            "status": "complete",
            "detail": f"Reviewed submitted text plus {urls_found} link{'s' if urls_found != 1 else ''}.",
        },
        {
            "step": "Pattern review",
            "status": "complete",
            "detail": f"Found {len(findings)} scam-language signal{'s' if len(findings) != 1 else ''}.",
        },
        {
            "step": "Link and domain checks",
            "status": "complete" if {"URL reachability", "DNS resolution"} & live_labels else "skipped",
            "detail": (
                f"Checked reachability, DNS, and registration data for {domains_checked} domain{'s' if domains_checked != 1 else ''}."
                if {"URL reachability", "DNS resolution"} & live_labels
                else "Skipped link and domain checks because no URLs or domains were found in the submission."
            ),
        },
        {
            "step": "Public web review",
            "status": "complete" if web_search_done else "skipped",
            "detail": (
                "Searched public web results for scam, fraud, complaint, and fake-job signals."
                if web_search_done
                else "Skipped public web search because no company, domain, email, or recognizable employer name was available."
            ),
        },
        {
            "step": "Recommendation",
            "status": "complete",
            "detail": "Combined pattern and live-verification evidence into an apply recommendation.",
        },
    ]
