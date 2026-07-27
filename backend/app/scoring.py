from __future__ import annotations

import re
from typing import Any

from app.models import Evidence
from app.text_utils import ROLE_TITLE_TERMS, extract_emails, extract_urls


SCAM_PATTERNS = [
    {
        "id": "upfront_fee",
        "label": "Upfront fee request",
        "severity": "critical",
        "score": 30,
        "regex": r"\b(upfront|advance|registration|processing|training|equipment|visa|security|refundable)\s+(fee|payment|charge|deposit)\b|\bpay\b.{0,40}\b(before|prior to|to start|to proceed)\b|\b(send|pay)\b.{0,40}\bdeposit\b",
        "explain": "Legitimate employers rarely require candidates to pay before hiring.",
    },
    {
        "id": "gift_card_payment",
        "label": "Gift card requested as payment",
        "severity": "critical",
        "score": 28,
        "regex": r"\bgift\s*card\b.{0,60}\b(pay|payment|purchase|buy|deposit|fee)\b|\b(pay|payment|purchase|buy|deposit|fee)\b.{0,60}\bgift\s*card\b",
        "explain": "Gift cards are untraceable and irreversible; legitimate employers never request payment this way.",
    },
    {
        "id": "gift_card_mentioned",
        "label": "Gift card mentioned",
        "severity": "medium",
        "score": 8,
        "regex": r"\bgift\s*cards?\b",
        "explain": "Gift cards are a frequent vector in employment scams even when framed as a reward; treat any gift-card mention with caution.",
    },
    {
        "id": "urgency",
        "label": "High-pressure urgency",
        "severity": "high",
        "score": 14,
        "regex": r"\b(urgent|immediate joining|act fast|limited slots|final notice|today only|reply now|asap)\b|\b(within|in)\s+\d+\s*(hour|hr|minute|min)s?\b.{0,30}\b(expire|offer|reply|respond)\b|\b(expire|offer|reply|respond)\b.{0,30}\b(within|in)\s+\d+\s*(hour|hr|minute|min)s?\b",
        "explain": "Scams often pressure candidates into skipping normal verification.",
    },
    {
        "id": "messaging_app",
        "label": "Off-platform interview channel",
        "severity": "medium",
        "score": 10,
        "regex": r"\b(whatsapp|telegram|signal)\b.{0,60}\b(interview|hr|recruiter|offer|shortlisted)\b|\b(interview|shortlisted)\b.{0,60}\b(whatsapp|telegram|signal)\b",
        "explain": "Moving directly to messaging apps can make impersonation harder to trace.",
    },
    {
        "id": "sensitive_info",
        "label": "Early sensitive information request",
        "severity": "high",
        "score": 16,
        "regex": r"\b(passport|emirates id|national id|bank account|iban|credit card|otp|one-time password)\b",
        "explain": "Requests for identity or banking details before verified hiring are risky.",
    },
    {
        "id": "too_good",
        "label": "Unusually generous offer language",
        "severity": "medium",
        "score": 10,
        "regex": r"\b(no experience required|work from home)\b.{0,80}\b(high salary|huge salary|guaranteed income|weekly pay)\b|\b(high salary|huge salary|guaranteed income|weekly pay)\b.{0,80}\b(no experience required|work from home)\b",
        "explain": "Overly broad, high-reward promises are common in fake postings.",
    },
    {
        "id": "generic_contact",
        "label": "Generic email contact",
        "severity": "medium",
        "score": 8,
        "regex": r"\b[\w.+-]+@(gmail|yahoo|outlook|hotmail|proton|icloud)\.(com|co|ae|in|net)\b",
        "explain": "Recruiting for established companies should usually use a company domain.",
    },
    {
        "id": "generic_signature",
        "label": "Generic recruiter signature",
        "severity": "medium",
        "score": 8,
        "regex": r"\b(regards|thanks|thank you),?\s*\n\s*(coordination team|recruitment team|hiring team|hr team)\b",
        "explain": "Legitimate interview invitations usually identify a recruiter, company, and role clearly.",
    },
    {
        "id": "website_instead_of_meeting_link",
        "label": "Website provided instead of meeting link",
        "severity": "high",
        "score": 18,
        "regex": r"\b(interview|discussion)\s+information\s+is\s+available\s+at\b",
        "explain": "A vague website link in place of a named recruiter or meeting link is a common fake-interview pattern.",
    },
]

CONTEXTUAL_PATTERNS = [
    {
        "id": "date_missing_year",
        "label": "Interview date missing year",
        "severity": "medium",
        "score": 8,
        "explain": "A formal interview invite should include a complete date, especially when the month/day may already be stale.",
    },
    {
        "id": "missing_role",
        "label": "No job role identified",
        "severity": "medium",
        "score": 10,
        "explain": "Interview messages that omit the job title or requisition are harder to verify and often appear in mass outreach.",
    },
    {
        "id": "insufficient_verifiable_detail",
        "label": "No verifiable details provided",
        "severity": "medium",
        "score": 15,
        "explain": "This message gives no company name, role, contact link, or email -- there is nothing here to verify who is actually contacting you.",
    },
    {
        "id": "instant_offer_no_process",
        "label": "Instant offer with no hiring process",
        "severity": "high",
        "score": 25,
        "explain": "This message announces a job offer or selection without any interview, application, or hiring process mentioned -- legitimate employers essentially always have some verifiable process before extending an offer.",
    },
]

INSTANT_OFFER_PATTERN = re.compile(
    r"\byou\s+(got|have\s+got|have)\s+(the\s+)?(job|offer|position)\b"
    r"|\byou'?ve?\s+been\s+(hired|selected)\b"
    r"|\bcongratulations,?\s+you\s+(got|have)\s+(the\s+)?(job|offer)\b",
    re.IGNORECASE,
)
PROCESS_TERMS = {
    "interview", "apply", "application", "resume", "cv", "process",
    "assessment", "test", "screening",
}

CONTEXTUAL_PATTERN_IDS = {pattern["id"] for pattern in CONTEXTUAL_PATTERNS}
STRONG_SCAM_PATTERN_IDS = {
    pattern["id"] for pattern in SCAM_PATTERNS if pattern["severity"] in {"critical", "high"}
} | {"instant_offer_no_process"}


def score_to_tier(score: int) -> tuple[str, str]:
    if score >= 70:
        return "Likely scam", "critical"
    if score >= 45:
        return "High risk", "high"
    if score >= 24:
        return "Needs verification", "medium"
    return "Lower risk", "low"


NEGATION_WORDS = re.compile(r"\b(no|not|never|without|isn't|doesn't|won't|don't|didn't|wasn't|weren't|n't)\b", re.IGNORECASE)
NEGATION_LOOKBACK_CHARS = 24


def _is_negated(text: str, match_start: int) -> bool:
    context = text[max(0, match_start - NEGATION_LOOKBACK_CHARS) : match_start]
    return bool(NEGATION_WORDS.search(context))


def pattern_check(text: str) -> tuple[int, list[dict[str, Any]]]:
    findings: list[dict[str, Any]] = []
    score = 0
    for pattern in SCAM_PATTERNS:
        all_matches = list(re.finditer(pattern["regex"], text, re.IGNORECASE | re.DOTALL))
        matches = [match for match in all_matches if not _is_negated(text, match.start())]
        if matches:
            score += pattern["score"]
            findings.append(
                {
                    "id": pattern["id"],
                    "label": pattern["label"],
                    "severity": pattern["severity"],
                    "score": pattern["score"],
                    "explanation": pattern["explain"],
                    "matches": len(matches),
                }
            )
    contextual_score, contextual_findings = contextual_check(text)
    return score + contextual_score, findings + contextual_findings


def contextual_check(text: str) -> tuple[int, list[dict[str, Any]]]:
    normalized = re.sub(r"\s+", " ", text.strip())
    lowered = normalized.lower()
    findings: list[dict[str, Any]] = []
    score = 0

    if re.search(r"\bdate:\s*\d{1,2}\s+[a-zA-Z]{3,9}\b", text, re.IGNORECASE) and not re.search(
        r"\bdate:\s*\d{1,2}\s+[a-zA-Z]{3,9}\s+\d{4}\b",
        text,
        re.IGNORECASE,
    ):
        pattern = CONTEXTUAL_PATTERNS[0]
        score += pattern["score"]
        findings.append(
            {
                "id": pattern["id"],
                "label": pattern["label"],
                "severity": pattern["severity"],
                "score": pattern["score"],
                "explanation": pattern["explain"],
                "matches": 1,
            }
        )

    mentions_interview = any(term in lowered for term in ["interview", "discussion", "shortlisted"])
    no_role_identified = mentions_interview and not any(term in lowered for term in ROLE_TITLE_TERMS)
    if no_role_identified:
        pattern = CONTEXTUAL_PATTERNS[1]
        score += pattern["score"]
        findings.append(
            {
                "id": pattern["id"],
                "label": pattern["label"],
                "severity": pattern["severity"],
                "score": pattern["score"],
                "explanation": pattern["explain"],
                "matches": 1,
            }
        )

        has_contact_signal = bool(extract_emails(text)) or bool(extract_urls(text))
        if not has_contact_signal:
            pattern = CONTEXTUAL_PATTERNS[2]
            score += pattern["score"]
            findings.append(
                {
                    "id": pattern["id"],
                    "label": pattern["label"],
                    "severity": pattern["severity"],
                    "score": pattern["score"],
                    "explanation": pattern["explain"],
                    "matches": 1,
                }
            )

    mentions_instant_offer = bool(INSTANT_OFFER_PATTERN.search(text))
    mentions_process = any(term in lowered for term in PROCESS_TERMS)
    if mentions_instant_offer and not mentions_process:
        pattern = CONTEXTUAL_PATTERNS[3]
        score += pattern["score"]
        findings.append(
            {
                "id": pattern["id"],
                "label": pattern["label"],
                "severity": pattern["severity"],
                "score": pattern["score"],
                "explanation": pattern["explain"],
                "matches": 1,
            }
        )

    return score, findings


def evidence_score(evidence: list[Evidence]) -> int:
    score = 0
    for item in evidence:
        if item.severity == "critical":
            score += 20
        elif item.severity == "high":
            score += 30 if item.label == "Web search" else 16
        elif item.severity == "medium":
            if item.status in {"failed", "skipped", "not_found"}:
                continue
            if item.label == "URL reachability":
                score += 8
            elif item.label == "Domain registration":
                score += 16
            elif item.label == "Web search":
                score += 24
            else:
                score += 8
    return score
