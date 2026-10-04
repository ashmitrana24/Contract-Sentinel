"""Forensics settings, report, and shared utilities.

ForensicsSettings: all configurable thresholds.
ForensicsReport: the result of analyze().
DetectorStatus: per-detector timing and error info.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from clauseguard.schemas.findings import Finding

# Module name used in all forensics findings
FORENSICS_MODULE = "pdf_forensics"
FORENSICS_VERSION = "1.0.0"

# Cap: max findings per type per document
MAX_FINDINGS_PER_TYPE = 50


class ForensicsSettings(BaseModel):
    """All configurable thresholds for forensics detectors."""

    # --- Budget ---
    budget_seconds: float = Field(
        default=20.0,
        description="Per-document total time budget; analysis aborts detectors after this",
    )

    # --- Revisions ---
    max_revisions: int = Field(
        default=25,
        description="Maximum revisions to analyze (first+last few if more exist)",
    )

    # --- Text hiding ---
    min_font_size_pt: float = Field(
        default=2.0,
        description="Font sizes strictly below this are flagged as tiny_text",
    )
    min_contrast_ratio: float = Field(
        default=1.5,
        description="WCAG contrast ratio below which text/background is flagged hidden",
    )

    # --- Metadata ---
    metadata_moddate_threshold_minutes: float = Field(
        default=1.0,
        description="ModDate must exceed CreationDate by at least this many minutes to flag",
    )
    known_online_editors: list[str] = Field(
        default_factory=lambda: [
            "ilovepdf",
            "smallpdf",
            "sejda",
            "pdfescape",
            "pdfcandy",
            "pdf2go",
            "online2pdf",
        ],
        description="Producer/creator strings hinting at online edit tools (weak signal only)",
    )

    # --- Hidden text severity thresholds ---
    hidden_text_high_char_threshold: int = Field(
        default=20,
        description="Hidden text >= this many chars OR containing sensitive tokens -> high severity",
    )

    model_config = {"arbitrary_types_allowed": True}


class DetectorStatus(BaseModel):
    """Per-detector execution status included in every ForensicsReport."""

    detector: str
    status: str  # "ok" | "error" | "skipped"
    duration_ms: float
    finding_count: int
    error: str | None = None

    @property
    def name(self) -> str:
        return self.detector


class ForensicsReport(BaseModel):
    """Complete result of one forensics analysis run."""

    version: str = FORENSICS_VERSION
    findings: list[Finding] = Field(default_factory=list)
    detectors: list[DetectorStatus] = Field(default_factory=list)
    overall_status: str = "ok"  # "ok" | "partial" | "error"
    total_duration_ms: float = 0.0
    budget_exceeded: bool = False
    details: dict[str, Any] = Field(default_factory=dict)

    @property
    def status(self) -> str:
        return self.overall_status

    @property
    def detector_status(self) -> list[DetectorStatus]:
        return self.detectors

    def finding_counts_by_severity(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for f in self.findings:
            counts[f.severity] = counts.get(f.severity, 0) + 1
        return counts
