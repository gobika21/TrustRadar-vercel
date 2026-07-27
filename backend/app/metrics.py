from __future__ import annotations

from typing import Any


METRICS = {
    "analyze_requests": 0,
    "url_fetches": 0,
    "dns_lookups": 0,
    "rdap_lookups": 0,
    "web_searches": 0,
    "uploaded_files": 0,
    "analysis_errors": 0,
    "total_analysis_ms": 0.0,
}


def build_usage_snapshot(before: dict[str, Any]) -> dict[str, int]:
    return {
        "url_fetches": METRICS["url_fetches"] - before["url_fetches"],
        "dns_lookups": METRICS["dns_lookups"] - before["dns_lookups"],
        "rdap_lookups": METRICS["rdap_lookups"] - before["rdap_lookups"],
        "web_searches": METRICS["web_searches"] - before["web_searches"],
    }


def metrics_payload() -> dict[str, Any]:
    average_ms = 0.0
    if METRICS["analyze_requests"]:
        average_ms = METRICS["total_analysis_ms"] / METRICS["analyze_requests"]
    return {
        **METRICS,
        "average_analysis_ms": round(average_ms, 2),
        "total_analysis_ms": round(METRICS["total_analysis_ms"], 2),
        "note": "In-memory local counters. They reset when the backend process restarts.",
    }
