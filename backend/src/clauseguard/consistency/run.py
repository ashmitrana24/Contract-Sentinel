"""Consistency analysis runner and CLI entrypoint.

Orchestrates all consistency detectors:
- Enforces per-document time budget (default 10s)
- Runs each detector in an isolated try/except block
- Caps findings per type per document at 50 with a summary finding if exceeded
- Trims all evidence snippets to at most 300 characters
- Provides CLI: python -m clauseguard.consistency.run path/to/file.pdf
"""

from __future__ import annotations

import argparse
import json
import logging
import time
from collections import defaultdict
from pathlib import Path
from typing import TYPE_CHECKING, Any

from clauseguard.consistency.dates import detect_dates
from clauseguard.consistency.models import (
    CONSISTENCY_MODULE,
    MAX_EVIDENCE_CHARS,
    ConsistencyReport,
    ConsistencySettings,
    DetectorStatus,
)
from clauseguard.consistency.numbering import detect_clause_numbering
from clauseguard.consistency.pairs import detect_pairs
from clauseguard.consistency.parties import detect_party_inconsistencies
from clauseguard.consistency.references import detect_cross_references
from clauseguard.consistency.text_index import build_text_index
from clauseguard.schemas.findings import Finding, Severity

if TYPE_CHECKING:
    from clauseguard.schemas.parsed import ParsedDocument

logger = logging.getLogger(__name__)


def analyze(
    doc: ParsedDocument,
    settings: ConsistencySettings | None = None,
) -> ConsistencyReport:
    """Run all consistency detectors on a parsed document within a time budget.

    Each detector runs isolated: an exception in one produces a 'detector_error'
    DetectorStatus entry while the remaining detectors continue executing.
    """
    if settings is None:
        settings = ConsistencySettings()

    start_time = time.perf_counter()
    index = build_text_index(doc)

    raw_findings: list[Finding] = []
    detector_statuses: list[DetectorStatus] = []
    aggregated_stats: dict[str, Any] = {}
    budget_exceeded = False

    # Store references detector stats to correlate dangling xrefs with numbering gaps
    refs_stats: dict[str, Any] = {}

    detectors = [
        ("pairs", lambda: detect_pairs(doc, index, settings)),
        ("dates", lambda: detect_dates(doc, index, settings)),
        ("parties", lambda: detect_party_inconsistencies(doc, index, settings)),
        ("references", lambda: detect_cross_references(doc, index, settings)),
        (
            "numbering",
            lambda: detect_clause_numbering(
                doc,
                index,
                settings,
                dangling_targets=refs_stats.get("dangling_targets", []),
            ),
        ),
    ]

    for name, detector_fn in detectors:
        elapsed = time.perf_counter() - start_time
        if elapsed >= settings.budget_seconds:
            budget_exceeded = True
            detector_statuses.append(
                DetectorStatus(
                    detector=name,
                    status="skipped",
                    duration_ms=0.0,
                    finding_count=0,
                    stats={"skipped_reason": "budget_exceeded"},
                )
            )
            continue

        det_start = time.perf_counter()
        try:
            findings, stats = detector_fn()
            duration_ms = (time.perf_counter() - det_start) * 1000.0

            if name == "references":
                refs_stats = stats

            raw_findings.extend(findings)
            status_val = "skipped" if stats.get("skipped_reason") else "ok"
            detector_statuses.append(
                DetectorStatus(
                    detector=name,
                    status=status_val,
                    duration_ms=round(duration_ms, 2),
                    finding_count=len(findings),
                    stats=stats,
                )
            )
            aggregated_stats[name] = stats

        except Exception as exc:
            duration_ms = (time.perf_counter() - det_start) * 1000.0
            logger.exception("Consistency detector '%s' failed: %s", name, exc)
            detector_statuses.append(
                DetectorStatus(
                    detector=name,
                    status="error",
                    duration_ms=round(duration_ms, 2),
                    finding_count=0,
                    error=str(exc),
                    stats={"error": str(exc)},
                )
            )

    # -----------------------------------------------------------------------
    # Post-processing: Cap findings per type per document at 50 with summary finding
    # and trim evidence to MAX_EVIDENCE_CHARS (300).
    # -----------------------------------------------------------------------
    findings_by_type: dict[str, list[Finding]] = defaultdict(list)
    for f in raw_findings:
        # Trim evidence
        if f.evidence and len(f.evidence) > MAX_EVIDENCE_CHARS:
            f = f.model_copy(update={"evidence": f.evidence[:MAX_EVIDENCE_CHARS]})
        findings_by_type[f.type].append(f)

    capped_findings: list[Finding] = []
    cap = settings.max_findings_per_type

    for ftype, items in findings_by_type.items():
        if len(items) > cap:
            capped_findings.extend(items[:cap])
            _sev_order = [Severity.LOW, Severity.MEDIUM, Severity.HIGH, Severity.CRITICAL]
            summary_sev = max((it.severity for it in items), key=lambda s: _sev_order.index(s))
            summary_finding = Finding(
                module=CONSISTENCY_MODULE,
                type=ftype,
                severity=summary_sev,
                page=None,
                clause_ref=None,
                evidence=f"Total {len(items)} occurrences of '{ftype}' exceeded maximum cap of {cap}.",
                explanation=(
                    f"More than {cap} instances of '{ftype}' were detected in this document. "
                    f"Showing the first {cap} occurrences."
                ),
                details={"total_count": len(items), "cap": cap, "rule_id": "CAP_EXCEEDED"},
            )
            capped_findings.append(summary_finding)
        else:
            capped_findings.extend(items)

    total_duration_ms = (time.perf_counter() - start_time) * 1000.0

    # Determine overall status
    statuses = [ds.status for ds in detector_statuses]
    if all(s in ("ok", "skipped") for s in statuses):
        overall_status = "ok"
    elif all(s == "error" for s in statuses):
        overall_status = "error"
    else:
        overall_status = "partial"

    return ConsistencyReport(
        findings=capped_findings,
        detectors=detector_statuses,
        overall_status=overall_status,
        total_duration_ms=round(total_duration_ms, 2),
        budget_exceeded=budget_exceeded,
        stats=aggregated_stats,
    )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    """CLI runner: parse a PDF and output consistency report as JSON."""
    parser = argparse.ArgumentParser(
        description="ClauseGuard Consistency Analysis CLI",
    )
    parser.add_argument("pdf_path", type=str, help="Path to contract PDF file")
    parser.add_argument(
        "--order",
        choices=["DMY", "MDY"],
        default="DMY",
        help="Date ordering for ambiguous numeric dates (default: DMY)",
    )
    parser.add_argument(
        "--budget",
        type=float,
        default=10.0,
        help="Time budget in seconds (default: 10.0)",
    )
    args = parser.parse_args()

    pdf_file = Path(args.pdf_path)
    if not pdf_file.exists():
        parser.error(f"File not found: {pdf_file}")

    from clauseguard.parsing.parse_document import parse_document

    doc = parse_document(pdf_file.read_bytes())
    settings = ConsistencySettings(
        date_format_order=args.order,
        budget_seconds=args.budget,
    )
    report = analyze(doc, settings)

    print(json.dumps(report.model_dump(mode="json"), indent=2))  # noqa: T201


if __name__ == "__main__":
    main()
