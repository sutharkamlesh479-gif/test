"""Shared finding and report models."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import hashlib
from typing import Any

SEVERITIES = {"info", "low", "medium", "high", "critical"}
CONFIDENCES = {"low", "medium", "high"}


def stable_id(namespace: str, *parts: object) -> str:
    """Build a stable, non-secret identifier for report objects."""
    seed = "\x1f".join([namespace, *(str(part) for part in parts)])
    return hashlib.sha256(seed.encode("utf-8", errors="replace")).hexdigest()[:12]


@dataclass(slots=True)
class Finding:
    title: str
    description: str
    severity: str = "info"
    confidence: str = "medium"
    source: str = "unknown"
    evidence: list[str] = field(default_factory=list)
    recommendation: str = "Review the evidence and validate it in context."
    finding_id: str = ""

    def __post_init__(self) -> None:
        if self.severity not in SEVERITIES:
            raise ValueError(f"Unsupported severity: {self.severity}")
        if self.confidence not in CONFIDENCES:
            raise ValueError(f"Unsupported confidence: {self.confidence}")
        if not self.finding_id:
            self.finding_id = stable_id("finding", self.source, self.title, *self.evidence)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def base_report(analysis_type: str) -> dict[str, Any]:
    from . import __version__
    return {
        "schema_version": "1.0",
        "tool": "AURIX OMEGA",
        "tool_version": __version__,
        "analysis_type": analysis_type,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "findings": [],
        "limitations": [
            "Findings are triage signals, not proof of malicious intent.",
            "Analysis is limited to the supplied artifact or exported evidence.",
            "Absence of findings does not prove a system or artifact is safe.",
        ],
    }
