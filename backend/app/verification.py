from __future__ import annotations

import asyncio
import datetime as dt
import ipaddress
import re
import socket
from html import unescape
from urllib.parse import parse_qs, quote_plus, unquote, urlparse

import httpx
from bs4 import BeautifulSoup

from app.agents.skills.search_synthesis import judge_search_relevance
from app.metrics import METRICS
from app.models import Evidence
from app.text_utils import domain_from_url, extract_emails, extract_urls, is_known_ats_domain, registered_domain


BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


async def resolve_dns(domain: str) -> Evidence:
    METRICS["dns_lookups"] += 1
    try:
        addresses = await asyncio.to_thread(socket.getaddrinfo, domain, None)
        ips = sorted({item[4][0] for item in addresses})[:4]
        if any(is_non_public_ip(ip) for ip in ips):
            return Evidence(
                "DNS resolution",
                "suspicious",
                f"{domain} resolves to {', '.join(ips)}, which is a private/loopback address, not a public host.",
                domain,
                "high",
            )
        return Evidence("DNS resolution", "found", f"{domain} resolves to {', '.join(ips)}", domain, "info")
    except socket.gaierror:
        return Evidence("DNS resolution", "not_found", f"{domain} does not resolve in DNS.", domain, "high")


def is_non_public_ip(address: str) -> bool:
    try:
        ip = ipaddress.ip_address(address)
    except ValueError:
        return False
    return ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_unspecified


async def fetch_url(client: httpx.AsyncClient, url: str) -> Evidence:
    METRICS["url_fetches"] += 1
    try:
        response = await client.get(url, follow_redirects=True)
        if response.status_code in {403, 406, 429}:
            response = await client.get(url, follow_redirects=True, headers=BROWSER_HEADERS)
        return response_to_evidence(response, url)
    except httpx.HTTPError as exc:
        return Evidence("URL reachability", "failed", f"Could not fetch URL: {exc.__class__.__name__}", url, "medium")


def response_to_evidence(response: httpx.Response, original_url: str) -> Evidence:
    title = ""
    if "text/html" in response.headers.get("content-type", ""):
        soup = BeautifulSoup(response.text[:100_000], "html.parser")
        title = soup.title.string.strip() if soup.title and soup.title.string else ""
    final_domain = domain_from_url(str(response.url)) or "unknown domain"
    detail = f"HTTP {response.status_code} from {final_domain}"
    if title:
        detail += f"; title: {title[:120]}"
    severity = "info" if response.status_code < 400 else "medium"
    title_lower = title.lower()
    if any(term in title_lower for term in ["access denied", "just a moment", "captcha", "verify you are human", "blocked"]):
        severity = "medium"
        return Evidence("URL reachability", "blocked", f"{detail}; page appears blocked or requires browser verification", original_url, severity)
    if any(term in title_lower for term in ["gulf jobs", "salary", "visa guide", "jobs 2026"]):
        severity = "medium"
        detail += "; page title looks like a generic jobs/visa-content site, not an interview page"
    return Evidence("URL reachability", "checked", detail, original_url, severity)


async def rdap_lookup(client: httpx.AsyncClient, domain: str) -> Evidence:
    METRICS["rdap_lookups"] += 1
    root = registered_domain(domain)
    if is_known_ats_domain(root):
        return Evidence(
            "ATS platform",
            "recognized",
            f"{root} is a recognized applicant-tracking platform; assess the employer/posting content separately.",
            root,
            "info",
        )
    suffix = root.rsplit(".", 1)[-1].lower()
    endpoints = [f"https://rdap.org/domain/{root}"]
    if suffix in {"com", "net"}:
        endpoints.append(f"https://rdap.verisign.com/{suffix}/v1/domain/{root.upper()}")
    try:
        data = None
        last_status = None
        for endpoint in endpoints:
            response = await client.get(endpoint)
            last_status = response.status_code
            if response.status_code >= 400:
                continue
            try:
                data = response.json()
                break
            except ValueError:
                continue
        if data is None:
            return Evidence("Domain registration", "not_found", f"No parseable RDAP record found for {root}; last HTTP status was {last_status}.", root, "high")
        events = data.get("events", [])
        registration_date = None
        for event in events:
            if event.get("eventAction") in {"registration", "registered"}:
                registration_date = event.get("eventDate")
                break
        if not registration_date:
            return Evidence("Domain registration", "checked", f"RDAP record exists for {root}, but no registration date was exposed.", root)
        created = dt.datetime.fromisoformat(registration_date.replace("Z", "+00:00"))
        age_days = (dt.datetime.now(dt.timezone.utc) - created).days
        severity = "high" if age_days < 90 else "medium" if age_days < 365 else "info"
        return Evidence(
            "Domain age",
            "checked",
            f"{root} appears about {age_days} days old; registered {created.date().isoformat()}.",
            root,
            severity,
        )
    except (httpx.HTTPError, ValueError, KeyError) as exc:
        return Evidence("Domain registration", "failed", f"RDAP lookup failed: {exc.__class__.__name__}", root, "medium")


def decode_ddg_href(href: str) -> str:
    parsed = urlparse(href)
    if parsed.netloc.endswith("duckduckgo.com") and parsed.path == "/l/":
        uddg = parse_qs(parsed.query).get("uddg", [""])[0]
        return unquote(uddg) if uddg else href
    return href


def domain_tokens(query: str) -> set[str]:
    lowered = query.lower()
    company_match = re.search(r"\b([a-z0-9][a-z0-9-]{2,})\s+company\s+recruitment\s+scam\b", lowered)
    query_tokens = {company_match.group(1).replace("-", "")} if company_match else set()
    plain_company_match = re.search(r"\b([a-z0-9][a-z0-9 .&-]{2,60}?)\s+recruitment\s+scam\b", lowered)
    if plain_company_match:
        query_tokens.update(
            token.replace("-", "")
            for token in re.findall(r"[a-z0-9-]{4,}", plain_company_match.group(1))
        )
    host_match = re.search(r"\b([a-z0-9-]+\.[a-z]{2,})\b", lowered)
    if not host_match:
        return {token for token in query_tokens if len(token) >= 4}
    stem = host_match.group(1).split(".", 1)[0]
    tokens = {stem, *query_tokens}
    if stem.endswith("llc"):
        tokens.add(stem[:-3])
    if stem.startswith("al") and len(stem) > 4:
        tokens.add(stem[2:])
    if stem.startswith("al") and stem.endswith("llc") and len(stem) > 7:
        tokens.add(stem[2:-3])
    return {token for token in tokens if len(token) >= 4}


def search_result_severity(query: str, result_text: str) -> str:
    lowered = result_text.lower()
    negative_terms = [
        "job scam alert",
        "job scam",
        "scam using ai",
        "dangerous scam",
        "fake recruiting",
        "fake recruiter",
        "fake job",
        "fake company",
        "fraud",
        "phishing",
        "deception",
        "recruitment trap",
        "personal data theft",
        "data theft warning",
        "identity theft",
        "beware of",
        "are a scam",
    ]
    reputation_page_terms = ["scam or legit", "trustpilot", "scam-detector"]
    target_tokens = domain_tokens(query)
    result_entries = [entry.strip().lower() for entry in re.split(r"\s+\|\s+", result_text) if entry.strip()]
    target_negative_entries = [
        entry
        for entry in result_entries
        if any(term in entry for term in negative_terms) and any(token in entry for token in target_tokens)
    ]
    target_reputation_entries = [
        entry
        for entry in result_entries
        if any(term in entry for term in reputation_page_terms) and any(token in entry for token in target_tokens)
    ]
    if target_negative_entries:
        return "high"
    if target_reputation_entries:
        return "medium"
    if any(term in lowered for term in negative_terms):
        return "medium"
    return "info"


async def web_search(client: httpx.AsyncClient, query: str) -> Evidence:
    METRICS["web_searches"] += 1
    if not query.strip():
        return Evidence("Web search", "skipped", "No company or domain query was available.", "search")
    try:
        url = f"https://html.duckduckgo.com/html/?q={quote_plus(query)}"
        response = await client.get(url, follow_redirects=True)
        if response.status_code >= 400:
            return Evidence("Web search", "failed", f"Search returned HTTP {response.status_code}.", query, "medium")
        soup = BeautifulSoup(response.text, "html.parser")
        results = []
        for anchor in soup.select(".result__a")[:3]:
            title = unescape(anchor.get_text(" ", strip=True))
            href = decode_ddg_href(anchor.get("href", ""))
            results.append(f"{title} ({href})")
        if results:
            detail = "Top results: " + " | ".join(results)
            severity = search_result_severity(query, detail)
            llm_judgment = await judge_search_relevance(query, detail)
            if llm_judgment:
                severity = llm_judgment["severity"]
                detail += f" | LLM assessment: {llm_judgment['reasoning']}"
            return Evidence("Web search", "found", detail, query, severity)
        return Evidence("Web search", "not_found", "No search results were parsed for this query.", query, "medium")
    except httpx.HTTPError as exc:
        return Evidence("Web search", "failed", f"Search failed: {exc.__class__.__name__}", query, "medium")


def build_search_query(text: str, urls: list[str], emails: list[str]) -> str:
    employer_from_ats = employer_slug_from_ats_url(urls)
    if employer_from_ats:
        return f"{employer_from_ats} company recruitment scam"
    domains = [domain_from_url(url) for url in urls]
    domains = [domain for domain in domains if domain and not is_known_ats_domain(domain)]
    email_domains = [email.split("@", 1)[1] for email in emails]
    candidates = domains + email_domains
    if candidates:
        return f"{registered_domain(candidates[0])} company recruitment scam"
    company_match = re.search(r"(?:company|employer|client|organization|organisation)[:\s-]+([A-Z][A-Za-z0-9 &.,-]{2,60})", text)
    if company_match:
        return f"{company_match.group(1).strip()} recruitment scam"
    about_match = re.search(
        r"(?:^|\n)\s*About\s+([A-Z][A-Za-z0-9 &.,'-]{2,70}?)(?:\n|$)",
        text,
    )
    if about_match:
        company_name = normalize_company_name(about_match.group(1))
        if company_name:
            return f"{company_name} recruitment scam"
    lowercase_company_match = re.search(
        r"\b(?:from|at|with)\s+([a-zA-Z][a-zA-Z0-9 &.'-]{1,60}?)\s+company\b",
        text,
        re.IGNORECASE,
    )
    if lowercase_company_match:
        company_name = normalize_company_name(lowercase_company_match.group(1))
        if company_name:
            return f"{company_name} recruitment scam"
    words = re.findall(r"\b[A-Z][A-Za-z0-9&.-]{2,}\b", text)
    return " ".join(words[:4] + ["recruitment", "scam"]) if words else ""


def normalize_company_name(value: str) -> str:
    value = re.sub(r"\s+", " ", value).strip(" .,-")
    value = re.sub(r"\b(Inc|LLC|Ltd|Limited|Corporation|Corp|Company|Co)\.?\b", "", value, flags=re.IGNORECASE)
    value = re.sub(r"\s+", " ", value).strip(" .,-")
    return value


def employer_slug_from_ats_url(urls: list[str]) -> str | None:
    for url in urls:
        parsed = urlparse(url)
        host = parsed.netloc.lower()
        path_parts = [part for part in parsed.path.split("/") if part]
        if host.endswith("jobs.lever.co") and path_parts:
            return path_parts[0].replace("-", " ")
        if host.endswith("boards.greenhouse.io"):
            company = parse_qs(parsed.query).get("for", [""])[0]
            if company:
                return company.replace("-", " ")
            if path_parts:
                return path_parts[0].replace("-", " ")
        if host.endswith("jobs.ashbyhq.com") and path_parts:
            return path_parts[0].replace("-", " ")
        if host.endswith("myworkdayjobs.com"):
            tenant = host.split(".", 1)[0]
            if tenant and tenant not in {"www", "wd1", "wd2", "wd3", "wd5"}:
                return humanize_company_slug(tenant)
            if path_parts:
                return humanize_company_slug(path_parts[0])
    return None


def humanize_company_slug(value: str) -> str:
    spaced = re.sub(r"([a-z])([A-Z])", r"\1 \2", value)
    spaced = re.sub(r"[-_]+", " ", spaced)
    return re.sub(r"\s+", " ", spaced).strip()


async def verify_live(text: str, submitted_urls: list[str]) -> list[Evidence]:
    urls = list(dict.fromkeys(submitted_urls + extract_urls(text)))
    emails = extract_emails(text)
    domains = sorted({domain_from_url(url) for url in urls if domain_from_url(url)})
    domains.extend(email.split("@", 1)[1].lower() for email in emails)
    domains = sorted({registered_domain(domain) for domain in domains})

    timeout = httpx.Timeout(8.0, connect=4.0)
    async with httpx.AsyncClient(timeout=timeout, headers=BROWSER_HEADERS) as client:
        tasks = []
        for url in urls[:4]:
            tasks.append(fetch_url(client, url))
        for domain in domains[:4]:
            tasks.append(resolve_dns(domain))
            tasks.append(rdap_lookup(client, domain))
        tasks.append(web_search(client, build_search_query(text, urls, emails)))
        if not tasks:
            return [Evidence("Live verification", "skipped", "No URLs, domains, emails, or company name were found to verify.", "input", "medium")]
        return list(await asyncio.gather(*tasks))
