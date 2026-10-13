"""Deterministic risk scoring and summary aggregator for ClauseGuard.

Pure function:
    summarize(findings, coverage_inputs, settings) -> RiskSummary

Weights:
    Critical: 40, High: 20, Medium: 8.
    Low and uncertain findings are minor notes (listed, never scored).

Diminishing returns:
    Within one finding type, the first counts fully, each subsequent counts 25%,
    and each finding type is capped at twice its base weight.
    Total score = min(100, sum).

Bands:
    High: any critical OR score >= 60.
    Medium: any high OR score >= 20.
    Low: otherwise.
"""

from __future__ import annotations

import uuid
from typing import Any, Literal

from pydantic import BaseModel, Field

from clauseguard.config import Settings, get_settings
from clauseguard.risk.catalog import get_finding_type_info

RiskBand = Literal["low", "medium", "high"]


class TopReason(BaseModel):
    """Highlight reason item in the risk summary."""

    finding_id: str | uuid.UUID | None = None
    type: str
    title: str
    severity: str
    category: str
    clause_ref: str | None = None
    page: int | None = None
    explanation: str


class CoverageNote(BaseModel):
    """Information or warning note about analysis coverage."""

    level: Literal["info", "warning"]
    code: str
    message: str


class RiskSummary(BaseModel):
    """Structured deterministic risk analysis summary."""

    score: int = Field(ge=0, le=100, description="Risk score between 0 and 100")
    band: RiskBand = Field(description="Risk band: low, medium, or high")
    headline: str = Field(description="Deterministic human summary headline")
    top_reasons: list[TopReason] = Field(
        default_factory=list,
        description="Top scored findings to inspect first (up to 5)",
    )
    counts_by_severity: dict[str, int] = Field(default_factory=dict)
    counts_by_category: dict[str, int] = Field(default_factory=dict)
    minor_notes_count: int = Field(default=0, description="Count of low or uncertain findings")
    coverage_notes: list[CoverageNote] = Field(default_factory=list)
    has_coverage_warning: bool = Field(default=False)
    version: str = Field(default="1.0.0")


def _get_val(item: Any, key: str, default: Any = None) -> Any:
    if isinstance(item, dict):
        return item.get(key, default)
    return getattr(item, key, default)


def _is_uncertain(finding: Any) -> bool:
    """Check if finding is tagged uncertain."""
    details = _get_val(finding, "details", None)
    if isinstance(details, dict):
        return bool(details.get("uncertain"))
    return False


def _get_severity_val(finding: Any) -> str:
    sev = _get_val(finding, "severity", "low")
    if hasattr(sev, "value"):
        return str(sev.value).lower()
    return str(sev).lower()


def _get_weight(sev: str, settings: Settings) -> int:
    if sev == "critical":
        return settings.risk_weight_critical
    if sev == "high":
        return settings.risk_weight_high
    if sev == "medium":
        return settings.risk_weight_medium
    return 0


def _build_headline(
    scored_findings: list[Any],
    top_reasons: list[TopReason],
    counts_by_severity: dict[str, int],
    minor_notes_count: int,
) -> str:
    """Construct deterministic headline from templates."""
    crit_count = counts_by_severity.get("critical", 0)
    high_count = counts_by_severity.get("high", 0)
    med_count = counts_by_severity.get("medium", 0)

    if not scored_findings:
        if minor_notes_count > 0:
            return f"No significant integrity risks found ({minor_notes_count} minor note{'s' if minor_notes_count > 1 else ''} recorded)."
        return "No significant integrity risks or inconsistencies found across the document."

    # Part 1: count description
    parts: list[str] = []
    if crit_count > 0:
        parts.append(f"{crit_count} critical issue{'s' if crit_count > 1 else ''}")
    if high_count > 0:
        parts.append(f"{high_count} high-severity issue{'s' if high_count > 1 else ''}")
    if med_count > 0:
        parts.append(f"{med_count} medium-severity issue{'s' if med_count > 1 else ''}")

    count_str = ", ".join(parts[:-1]) + (" and " if len(parts) > 1 else "") + parts[-1]
    lead = f"{count_str} found."

    # Part 2: action pointer from top reason
    if top_reasons:
        first = top_reasons[0]
        # Location fragment
        loc_parts = []
        if first.clause_ref:
            loc_parts.append(f"clause {first.clause_ref}")
        if first.page:
            loc_parts.append(f"page {first.page}")
        loc_str = f" in {' on '.join(loc_parts)}" if loc_parts else ""

        lead += f" Start with the {first.title.lower()}{loc_str}."

    return lead


def summarize(
    findings: list[Any],
    coverage_inputs: dict[str, Any] | None = None,
    settings: Settings | None = None,
) -> RiskSummary:
    """Compute deterministic risk summary for a document."""
    if settings is None:
        settings = get_settings()
    if coverage_inputs is None:
        coverage_inputs = {}

    counts_by_severity: dict[str, int] = {
        "critical": 0,
        "high": 0,
        "medium": 0,
        "low": 0,
    }
    counts_by_category: dict[str, int] = {
        "tampering": 0,
        "inconsistency": 0,
    }

    scored_findings: list[Any] = []
    minor_notes_count = 0

    # Group findings by type for diminishing returns
    findings_by_type: dict[str, list[Any]] = {}

    for f in findings:
        sev = _get_severity_val(f)
        counts_by_severity[sev] = counts_by_severity.get(sev, 0) + 1

        ftype = _get_val(f, "type", "unknown")
        mod = _get_val(f, "module", None)
        info = get_finding_type_info(ftype, mod)
        counts_by_category[info.category] = counts_by_category.get(info.category, 0) + 1

        uncertain = _is_uncertain(f)
        if sev in ("critical", "high", "medium") and not uncertain:
            scored_findings.append(f)
            findings_by_type.setdefault(ftype, []).append(f)
        else:
            minor_notes_count += 1

    # Calculate score with diminishing returns within finding types
    total_raw_score = 0.0
    _sev_rank = {"critical": 3, "high": 2, "medium": 1, "low": 0}

    for _ftype, type_items in findings_by_type.items():
        # Sort by severity descending so the highest severity gets full weight
        sorted_items = sorted(
            type_items,
            key=lambda x: _sev_rank.get(_get_severity_val(x), 0),
            reverse=True,
        )
        if not sorted_items:
            continue

        base_weight = _get_weight(_get_severity_val(sorted_items[0]), settings)
        type_cap = base_weight * settings.risk_type_cap_factor

        type_total = float(base_weight)
        for extra in sorted_items[1:]:
            extra_w = _get_weight(_get_severity_val(extra), settings)
            type_total += extra_w * settings.risk_diminishing_rate

        type_total = min(type_total, type_cap)
        total_raw_score += type_total

    score = min(100, round(total_raw_score))

    # Determine risk band
    has_critical = counts_by_severity.get("critical", 0) > 0 and any(
        _get_severity_val(f) == "critical" and not _is_uncertain(f) for f in findings
    )
    has_high = counts_by_severity.get("high", 0) > 0 and any(
        _get_severity_val(f) == "high" and not _is_uncertain(f) for f in findings
    )
    has_high_tampering = getattr(settings, "risk_tampering_high_escalation", True) and any(
        _get_severity_val(f) in ("critical", "high")
        and get_finding_type_info(getattr(f, "type", ""), getattr(f, "module", None)).category == "tampering"
        and not _is_uncertain(f)
        for f in findings
    )

    if has_critical or has_high_tampering or score >= settings.risk_high_threshold:
        band: RiskBand = "high"
    elif has_high or score >= settings.risk_medium_threshold:
        band = "medium"
    else:
        band = "low"

    # Top reasons (max 5, ordered by severity descending, then score contribution)
    scored_sorted = sorted(
        scored_findings,
        key=lambda x: (
            _sev_rank.get(_get_severity_val(x), 0),
            _get_weight(_get_severity_val(x), settings),
        ),
        reverse=True,
    )

    top_reasons: list[TopReason] = []
    for f in scored_sorted[:5]:
        ftype = _get_val(f, "type", "unknown")
        mod = _get_val(f, "module", None)
        info = get_finding_type_info(ftype, mod)
        fid = _get_val(f, "id", None)
        top_reasons.append(
            TopReason(
                finding_id=fid,
                type=ftype,
                title=info.title,
                severity=_get_severity_val(f),
                category=info.category,
                clause_ref=_get_val(f, "clause_ref", None),
                page=_get_val(f, "page", None),
                explanation=_get_val(f, "explanation", ""),
            )
        )

    # Coverage notes
    coverage_notes: list[CoverageNote] = []
    has_warning = False

    needs_ocr = coverage_inputs.get("needs_ocr", False)
    if needs_ocr:
        has_warning = True
        coverage_notes.append(
            CoverageNote(
                level="warning",
                code="needs_ocr",
                message="Document contains low character density or scanned images. Text analysis is incomplete without OCR.",
            )
        )

    clause_count = coverage_inputs.get("clause_count", 10)
    unsegmented = coverage_inputs.get("unsegmented", False)
    if unsegmented or clause_count < 5:
        has_warning = True
        coverage_notes.append(
            CoverageNote(
                level="warning",
                code="unsegmented_clauses",
                message=f"Only {clause_count} clauses were segmented. Cross-reference and structural numbering checks have limited scope.",
            )
        )

    analysis_runs = coverage_inputs.get("analysis_runs", [])
    for run in analysis_runs:
        run_status = run.get("status") if isinstance(run, dict) else getattr(run, "status", None)
        run_mod = run.get("module") if isinstance(run, dict) else getattr(run, "module", "analysis")
        run_err = run.get("error") if isinstance(run, dict) else getattr(run, "error", None)
        if run_status in ("error", "partial"):
            has_warning = True
            msg = f"Analysis module '{run_mod}' returned status '{run_status}'"
            if run_err:
                msg += f": {run_err[:100]}"
            coverage_notes.append(
                CoverageNote(
                    level="warning",
                    code=f"module_run_{run_mod}_{run_status}",
                    message=msg,
                )
            )

        # Check detector statuses inside run
        det_status_dict = (
            run.get("detector_status") if isinstance(run, dict) else getattr(run, "detector_status", {})
        ) or {}
        detectors_list = det_status_dict.get("detectors", [])
        for det in detectors_list:
            d_name = det.get("detector", "unknown")
            d_st = det.get("status")
            if d_st == "skipped":
                has_warning = True
                coverage_notes.append(
                    CoverageNote(
                        level="warning",
                        code=f"detector_skipped_{d_name}",
                        message=f"Detector '{d_name}' was skipped due to execution budget constraints.",
                    )
                )
            elif d_st == "error":
                has_warning = True
                coverage_notes.append(
                    CoverageNote(
                        level="warning",
                        code=f"detector_error_{d_name}",
                        message=f"Detector '{d_name}' encountered an error: {det.get('error', 'unknown error')[:100]}.",
                    )
                )

    if not coverage_notes:
        coverage_notes.append(
            CoverageNote(
                level="info",
                code="full_coverage",
                message="All forensic and consistency detectors ran with full analytical coverage.",
            )
        )

    headline = _build_headline(
        scored_findings,
        top_reasons,
        counts_by_severity,
        minor_notes_count,
    )

    return RiskSummary(
        score=score,
        band=band,
        headline=headline,
        top_reasons=top_reasons,
        counts_by_severity=counts_by_severity,
        counts_by_category=counts_by_category,
        minor_notes_count=minor_notes_count,
        coverage_notes=coverage_notes,
        has_coverage_warning=has_warning,
        version=settings.risk_version,
    )
