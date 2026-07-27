from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Evidence:
    label: str
    status: str
    detail: str
    source: str
    severity: str = "info"
