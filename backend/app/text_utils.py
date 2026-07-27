from __future__ import annotations

import re
from urllib.parse import urlparse


KNOWN_ATS_DOMAINS = {
    "ashbyhq.com",
    "greenhouse.io",
    "lever.co",
    "myworkdayjobs.com",
    "workdayjobs.com",
}

JOB_RELATED_KEYWORDS = {
    "hiring", "recruit", "recruiter", "recruitment", "salary", "interview",
    "applicant", "employer", "employee", "career", "vacancy", "cv", "resume",
    "remote", "onboarding", "candidate", "part-time", "full-time", "internship",
    "compensation", "benefits", "shift", "employment", "responsibilities",
    "requirements", "qualifications", "experience", "skills", "duties",
    "engineer", "developer", "designer", "manager", "analyst", "coordinator",
    "specialist", "consultant", "assistant", "technician", "administrator",
    "executive", "officer", "intern", "shortlisted", "shortlist", "workday",
    "linkedin",
}

ROLE_TITLE_TERMS = {
    "engineer", "developer", "designer", "manager", "analyst", "coordinator",
    "specialist", "consultant", "assistant", "technician", "administrator",
    "executive", "officer", "intern", "accountant", "architect", "director",
    "recruiter",
}

REQUIREMENT_TERMS = {
    "requirements", "qualifications", "experience", "skills", "responsibilities", "duties",
}


def looks_like_job_content(text: str) -> bool:
    lowered = text.lower()
    if any(keyword in lowered for keyword in JOB_RELATED_KEYWORDS):
        return True
    if extract_emails(text) or extract_urls(text):
        return True
    return False


def looks_like_valid_jd(text: str) -> bool:
    """Strict heuristic: does this text contain a concrete, verifiable JD detail?

    Used as the no-LLM fallback for the JD-analyzer gate. Requires evidence of a
    role/title or requirements/skills -- a bare salary figure, company mention,
    or offer/interview wording is NOT enough on its own, since a message can
    name a company and a salary while never saying what the job even is.
    """
    lowered = text.lower()
    if any(term in lowered for term in ROLE_TITLE_TERMS):
        return True
    if any(term in lowered for term in REQUIREMENT_TERMS):
        return True
    if extract_emails(text) or extract_urls(text):
        return True
    return False


def extract_urls(text: str) -> list[str]:
    urls = re.findall(r"https?://[^\s<>\]\)\"']+", text)
    bare_domains = re.findall(
        r"(?<!@)\b(?:[a-zA-Z0-9-]+\.)+(?:com|net|org|ae|sa|qa|kw|bh|om|co|io|ai|jobs)\b",
        text,
    )
    normalized = [url.rstrip(".,;") for url in urls]
    for domain in bare_domains:
        candidate = f"https://{domain.rstrip('.,;')}"
        if candidate not in normalized and not any(domain in url for url in normalized):
            normalized.append(candidate)
    return normalized


def extract_emails(text: str) -> list[str]:
    return sorted(set(re.findall(r"\b[\w.+-]+@[\w.-]+\.[a-zA-Z]{2,}\b", text)))


def domain_from_url(url: str) -> str | None:
    try:
        parsed = urlparse(url if url.startswith(("http://", "https://")) else f"https://{url}")
    except ValueError:
        return None
    host = parsed.netloc.lower().split("@")[-1].split(":")[0]
    if host.startswith("www."):
        host = host[4:]
    return host or None


def registered_domain(host: str) -> str:
    parts = host.split(".")
    if len(parts) <= 2:
        return host
    two_part_suffixes = {"co.uk", "com.au", "co.in", "co.ae", "com.sa", "com.qa", "com.kw"}
    suffix = ".".join(parts[-2:])
    if suffix in two_part_suffixes and len(parts) >= 3:
        return ".".join(parts[-3:])
    return ".".join(parts[-2:])


def is_known_ats_domain(domain: str) -> bool:
    root = registered_domain(domain)
    return root in KNOWN_ATS_DOMAINS
