"""Unit tests for consistency runner (run.py).

Verifies:
- Failing detector produces 'error' status in DetectorStatus while others still report.
- Time budget is enforced.
- Performance test: full analysis on 1 MB synthetic text in under 2 seconds.
"""

import time
from unittest.mock import patch

import pytest

from clauseguard.consistency.models import ConsistencySettings
from clauseguard.consistency.run import analyze
from clauseguard.schemas.parsed import ClauseModel, PageModel, ParsedDocument

pytestmark = pytest.mark.unit


def _make_doc(text: str, clause_id: str = "1") -> ParsedDocument:
    pages = [PageModel(page_no=1, width=612.0, height=792.0, text=text, char_count=len(text))]
    clauses = [
        ClauseModel(
            order_idx=0,
            clause_id=clause_id,
            heading="General Terms",
            text=text,
            level=1,
            page_start=1,
            page_end=1,
            kind="clause",
        )
    ]
    return ParsedDocument(page_count=1, pages=pages, clauses=clauses)


def test_failing_detector_isolated():
    """An exception in one detector records status='error' while other detectors still run."""
    doc = _make_doc(
        "The Vendor shall deliver fifty (60) widgets on 01/01/2026. "
        "The Agreement terminates on 01/01/2025."
    )
    settings = ConsistencySettings()

    # Mock dates detector to simulate an unexpected exception
    with patch(
        "clauseguard.consistency.run.detect_dates",
        side_effect=RuntimeError("Simulated date detector crash"),
    ):
        report = analyze(doc, settings)

    # Report overall status should be "partial"
    assert report.overall_status == "partial"
    # Dates detector status should be "error"
    date_status = next(d for d in report.detectors if d.detector == "dates")
    assert date_status.status == "error"
    assert "Simulated date detector crash" in (date_status.error or "")

    # Pairs detector should still have executed and reported its finding
    pairs_status = next(d for d in report.detectors if d.detector == "pairs")
    assert pairs_status.status == "ok"
    assert pairs_status.finding_count >= 1
    assert any(f.type == "figure_words_mismatch" for f in report.findings)


def test_time_budget_enforced():
    """When the time budget is exceeded, subsequent detectors are skipped."""
    doc = _make_doc("Standard contract clause with fifty (50) items.")
    # Set a very tight budget (e.g. 0.0001 seconds) and simulate sleep in pairs detector
    settings = ConsistencySettings(budget_seconds=0.01)

    def _slow_pairs(*args, **kwargs):
        time.sleep(0.02)
        return [], {}

    with patch("clauseguard.consistency.run.detect_pairs", side_effect=_slow_pairs):
        report = analyze(doc, settings)

    assert report.budget_exceeded is True
    # At least one detector must have been skipped due to budget
    skipped_detectors = [d for d in report.detectors if d.status == "skipped"]
    assert len(skipped_detectors) >= 1
    assert any(
        d.stats.get("skipped_reason") == "budget_exceeded" for d in skipped_detectors
    )


def test_performance_1mb_text_under_two_seconds():
    """Whole consistency analysis runs on a 1 MB synthetic contract text in under 2 seconds.

    Guarantees that all regexes are safe against catastrophic backtracking.
    """
    # Build realistic repeating clauses totaling ~1 MB
    clause_bank = [
        "Clause {idx}: The Service Provider shall supply twenty (20) workstations at Rs. 10,000 (Rupees Ten thousand only) each.",
        "Clause {idx}: Invoicing shall occur on the 1st day of each month with thirty (30) days payment window.",
        "Clause {idx}: Either party may terminate on 30 days notice under Clause 1 or Clause 2.",
        "Clause {idx}: Standard confidentiality covenants apply for a term of two (2) years.",
    ]

    lines = [
        "Between: Apex Systems Pvt. Ltd. (Vendor) and Zenith Global Ltd. (Client)",
        "Effective Date: 2025-01-01",
        "Termination Date: 2026-01-01",
    ]

    target_bytes = 1024 * 1024  # 1 MB
    idx = 1
    while sum(len(line) for line in lines) < target_bytes:
        template = clause_bank[(idx - 1) % len(clause_bank)]
        lines.append(template.format(idx=idx))
        idx += 1

    full_text = "\n".join(lines)
    assert len(full_text.encode("utf-8")) >= target_bytes, "Must be at least 1 MB"

    doc = _make_doc(full_text)
    settings = ConsistencySettings(budget_seconds=10.0)

    start = time.perf_counter()
    report = analyze(doc, settings)
    elapsed = time.perf_counter() - start

    assert elapsed < 2.0, f"Analysis took {elapsed:.2f}s, exceeding 2.0s limit on 1 MB text"
    assert report.overall_status in ("ok", "partial")
