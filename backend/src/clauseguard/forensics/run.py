"""Forensics analysis orchestrator.

analyze(pdf_bytes, settings) -> ForensicsReport
  - Runs all detectors in isolation (exception in one does not abort others)
  - Enforces per-document time budget (checked between detectors)
  - Returns ForensicsReport with all findings and per-detector status

CLI: python -m clauseguard.forensics.run path/to/file.pdf
  Prints the ForensicsReport as pretty-printed JSON.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from clauseguard.forensics.active_content import detect_active_content
from clauseguard.forensics.incremental import detect_incremental
from clauseguard.forensics.metadata import detect_metadata
from clauseguard.forensics.models import (
    FORENSICS_VERSION,
    DetectorStatus,
    ForensicsReport,
    ForensicsSettings,
)
from clauseguard.forensics.signatures import detect_signatures
from clauseguard.forensics.text_hiding import detect_text_hiding
from clauseguard.schemas.findings import Finding, Severity

logger = logging.getLogger(__name__)


def analyze(
    pdf_bytes: bytes,
    settings: ForensicsSettings | None = None,
) -> ForensicsReport:
    """Run all forensics detectors on ``pdf_bytes`` and return a ForensicsReport.

    Each detector runs in isolation: if one raises an exception, it records
    a 'detector_error' entry and continues with the others.

    The per-document time budget is checked between detectors; if exceeded,
    remaining detectors are skipped with status 'skipped'.
    """
    if settings is None:
        settings = ForensicsSettings()

    budget_seconds = settings.budget_seconds
    start_time = time.monotonic()
    all_findings: list[Finding] = []
    detector_statuses: list[DetectorStatus] = []
    budget_exceeded = False
    overall_status = "ok"

    # Ordered list of (name, callable)
    detectors: list[tuple[str, Any]] = [
        ("incremental", detect_incremental),
        ("text_hiding", detect_text_hiding),
        ("metadata", detect_metadata),
        ("signatures", detect_signatures),
        ("active_content", detect_active_content),
    ]

    for detector_name, detector_fn in detectors:
        elapsed = time.monotonic() - start_time
        if elapsed >= budget_seconds:
            budget_exceeded = True
            overall_status = "partial"
            detector_statuses.append(
                DetectorStatus(
                    detector=detector_name,
                    status="skipped",
                    duration_ms=0.0,
                    finding_count=0,
                    error="Budget exceeded",
                )
            )
            logger.warning(
                "Forensics budget exceeded (%.1fs > %.1fs); skipping %s",
                elapsed,
                budget_seconds,
                detector_name,
            )
            continue

        det_start = time.monotonic()
        try:
            det_findings = detector_fn(pdf_bytes, settings)
            det_duration_ms = (time.monotonic() - det_start) * 1000
            all_findings.extend(det_findings)
            detector_statuses.append(
                DetectorStatus(
                    detector=detector_name,
                    status="ok",
                    duration_ms=det_duration_ms,
                    finding_count=len(det_findings),
                )
            )
            logger.debug(
                "Detector '%s' completed in %.0fms with %d findings",
                detector_name,
                det_duration_ms,
                len(det_findings),
            )
        except Exception as exc:
            det_duration_ms = (time.monotonic() - det_start) * 1000
            overall_status = "partial"
            err_msg = f"{type(exc).__name__}: {exc!s}"
            logger.exception("Detector '%s' raised an exception: %s", detector_name, exc)
            # Add a detector_error finding
            all_findings.append(
                Finding(
                    module="pdf_forensics",
                    type="detector_error",
                    severity=Severity.LOW,
                    evidence=err_msg[:300],
                    explanation=(
                        f"The '{detector_name}' detector encountered an internal error "
                        f"and could not complete its analysis. "
                        f"Error: {err_msg[:200]}"
                    ),
                    details={"detector": detector_name, "error": err_msg},
                )
            )
            detector_statuses.append(
                DetectorStatus(
                    detector=detector_name,
                    status="error",
                    duration_ms=det_duration_ms,
                    finding_count=1,
                    error=err_msg[:500],
                )
            )

    total_duration_ms = (time.monotonic() - start_time) * 1000

    return ForensicsReport(
        version=FORENSICS_VERSION,
        findings=all_findings,
        detectors=detector_statuses,
        overall_status=overall_status,
        total_duration_ms=total_duration_ms,
        budget_exceeded=budget_exceeded,
        details={
            "pdf_size_bytes": len(pdf_bytes),
            "finding_count": len(all_findings),
        },
    )


# ---------------------------------------------------------------------------
# CLI entrypoint
# ---------------------------------------------------------------------------


def _cli_main() -> None:
    import argparse
    import json
    import sys

    logging.basicConfig(
        level=logging.WARNING,
        format="%(levelname)s %(name)s: %(message)s",
    )

    parser = argparse.ArgumentParser(
        description="ClauseGuard PDF Forensics CLI — analyze a PDF for structural tampering."
    )
    parser.add_argument("pdf_path", help="Path to the PDF file to analyze")
    parser.add_argument(
        "--budget",
        type=float,
        default=20.0,
        help="Per-document time budget in seconds (default: 20)",
    )
    parser.add_argument(
        "--min-font-size",
        type=float,
        default=2.0,
        help="Minimum font size threshold (pt) for tiny_text detection (default: 2.0)",
    )
    parser.add_argument(
        "--min-contrast",
        type=float,
        default=1.5,
        help="Minimum WCAG contrast ratio for hidden_text detection (default: 1.5)",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose debug logging",
    )
    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    import pathlib
    pdf_path = pathlib.Path(args.pdf_path)
    if not pdf_path.exists():
        print(f"Error: file not found: {pdf_path}", file=sys.stderr)
        sys.exit(1)

    pdf_bytes = pdf_path.read_bytes()
    settings = ForensicsSettings(
        budget_seconds=args.budget,
        min_font_size_pt=args.min_font_size,
        min_contrast_ratio=args.min_contrast,
    )

    report = analyze(pdf_bytes, settings)

    # Serialize to JSON
    output = report.model_dump(mode="json")
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    _cli_main()
