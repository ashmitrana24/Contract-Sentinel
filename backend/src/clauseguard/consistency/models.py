"""Consistency settings, report schema, and detector execution status.

ConsistencySettings: all configurable thresholds for consistency detectors.
ConsistencyReport: complete output of analyze().
DetectorStatus: per-detector timing, status, finding counts, and statistics.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from clauseguard.schemas.findings import Finding

CONSISTENCY_MODULE = "consistency"
CONSISTENCY_VERSION = "1.0.0"
MAX_FINDINGS_PER_TYPE = 50
MAX_EVIDENCE_CHARS = 300


class ConsistencySettings(BaseModel):
    """All configurable thresholds for consistency analysis detectors."""

    # Time budget
    budget_seconds: float = Field(
        default=10.0,
        description="Per-document total time budget; remaining detectors are skipped if exceeded",
    )

    # Max findings per type
    max_findings_per_type: int = Field(
        default=MAX_FINDINGS_PER_TYPE,
        description="Cap on findings per type per document before summary finding",
    )

    # Dates
    date_format_order: str = Field(
        default="DMY",
        description="Ordering for ambiguous numeric dates like 01/02/2026: 'DMY' or 'MDY'",
    )
    term_tolerance_days: int = Field(
        default=31,
        description="Tolerance in days between stated term period and calculated date span",
    )

    # Parties
    party_similarity_threshold: float = Field(
        default=85.0,
        description="rapidfuzz similarity ratio (0-100) to flag party name variants",
    )
    max_unknown_parties: int = Field(
        default=10,
        description="Cap on unknown_party_entity findings reported per document",
    )
    min_parties_for_detector: int = Field(
        default=2,
        description="Minimum parties that must be extracted to run party consistency check",
    )

    # References & Numbering
    min_clauses_for_structural_checks: int = Field(
        default=5,
        description="Minimum parsed clauses required to run cross-reference and numbering checks",
    )

    model_config = {"arbitrary_types_allowed": True}


class DetectorStatus(BaseModel):
    """Execution status and metric summary for an individual detector."""

    detector: str
    status: str  # "ok" | "error" | "skipped"
    duration_ms: float
    finding_count: int
    error: str | None = None
    stats: dict[str, Any] = Field(default_factory=dict)

    @property
    def name(self) -> str:
        return self.detector


class ConsistencyReport(BaseModel):
    """Complete result of consistency analysis."""

    version: str = CONSISTENCY_VERSION
    findings: list[Finding] = Field(default_factory=list)
    detectors: list[DetectorStatus] = Field(default_factory=list)
    overall_status: str = "ok"  # "ok" | "partial" | "error"
    total_duration_ms: float = 0.0
    budget_exceeded: bool = False
    stats: dict[str, Any] = Field(
        default_factory=dict,
        description="Aggregated detector statistics (pairs found, verified, mismatched, unparseable, skipped)",
    )

    @property
    def status(self) -> str:
        return self.overall_status

    @property
    def detector_status(self) -> list[DetectorStatus]:
        return self.detectors

    def finding_counts_by_severity(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for f in self.findings:
            sev = f.severity.value if hasattr(f.severity, "value") else str(f.severity)
            counts[sev] = counts.get(sev, 0) + 1
        return counts
