"""Unit tests for Risk Aggregator (Module 8)."""

from __future__ import annotations

from clauseguard.config import Settings
from clauseguard.risk.aggregate import summarize
from clauseguard.schemas.findings import Finding, Severity


def _make_finding(
    type: str,
    severity: Severity | str,
    module: str = "consistency",
    details: dict | None = None,
    clause_ref: str | None = None,
    page: int | None = None,
    evidence: str = "sample evidence",
) -> Finding:
    sev = Severity(severity) if isinstance(severity, str) else severity
    return Finding(
        module=module,
        type=type,
        severity=sev,
        evidence=evidence,
        explanation=f"Finding of type {type}",
        details=details or {},
        clause_ref=clause_ref,
        page=page,
    )


def test_clean_document_zero_score_low_band() -> None:
    summary = summarize([])
    assert summary.score == 0
    assert summary.band == "low"
    assert "No significant integrity risks" in summary.headline
    assert summary.minor_notes_count == 0
    assert not summary.has_coverage_warning


def test_weights_and_diminishing_returns() -> None:
    settings = Settings()

    # 1 medium finding: weight is 8
    f1 = _make_finding("figure_words_mismatch", Severity.MEDIUM)
    s1 = summarize([f1], settings=settings)
    assert s1.score == 8
    assert s1.band == "medium"  # 8 >= settings.risk_medium_threshold

    # 2 medium findings of same type: 8 + 8 * 0.25 = 10
    f2 = _make_finding("figure_words_mismatch", Severity.MEDIUM)
    s2 = summarize([f1, f2], settings=settings)
    assert s2.score == 10

    # 3 medium findings of same type: 8 + 2 + 2 = 12
    f3 = _make_finding("figure_words_mismatch", Severity.MEDIUM)
    s3 = summarize([f1, f2, f3], settings=settings)
    assert s3.score == 12

    # Cap at twice weight (2 * 8 = 16)
    many_medium = [_make_finding("figure_words_mismatch", Severity.MEDIUM) for _ in range(10)]
    s_many = summarize(many_medium, settings=settings)
    assert s_many.score == 16


def test_critical_and_high_bands() -> None:
    settings = Settings()

    # Critical finding triggers high band immediately even if single finding
    crit = _make_finding("signature_invalid", Severity.CRITICAL, module="pdf_forensics")
    s_crit = summarize([crit], settings=settings)
    assert s_crit.score == 40
    assert s_crit.band == "high"

    # High consistency finding triggers medium band
    high_f = _make_finding("figure_words_mismatch", Severity.HIGH, module="consistency")
    s_high = summarize([high_f], settings=settings)
    assert s_high.score == 20
    assert s_high.band == "medium"

    # High tampering finding escalates to high band
    high_tamper = _make_finding("post_signature_modification", Severity.HIGH, module="pdf_forensics")
    s_tamper = summarize([high_tamper], settings=settings)
    assert s_tamper.band == "high"

    # Multiple high consistency findings cross 60 -> high band
    h1 = _make_finding("figure_words_mismatch", Severity.HIGH, module="consistency")
    h2 = _make_finding("date_order_conflict", Severity.HIGH, module="consistency")
    h3 = _make_finding("party_name_variant", Severity.HIGH, module="consistency")
    s_triple_high = summarize([h1, h2, h3], settings=settings)
    assert s_triple_high.score == 60
    assert s_triple_high.band == "high"


def test_low_and_uncertain_are_minor_notes_never_scored() -> None:
    low_f = _make_finding("numbering_gap", Severity.LOW)
    uncert_f = _make_finding(
        "dangling_reference",
        Severity.HIGH,
        details={"uncertain": True},
    )

    summary = summarize([low_f, uncert_f])
    assert summary.score == 0
    assert summary.band == "low"
    assert summary.minor_notes_count == 2
    assert len(summary.top_reasons) == 0


def test_headline_generation() -> None:
    f1 = _make_finding("figure_words_mismatch", Severity.HIGH, clause_ref="4.2", page=3)
    f2 = _make_finding("date_order_conflict", Severity.MEDIUM, clause_ref="8.1", page=5)

    summary = summarize([f1, f2])
    assert "1 high-severity issue and 1 medium-severity issue found" in summary.headline
    assert "Start with the amount in words doesn't match the figure in clause 4.2 on page 3" in summary.headline


def test_coverage_notes_generation() -> None:
    # Needs OCR warning
    s_ocr = summarize([], coverage_inputs={"needs_ocr": True})
    assert s_ocr.has_coverage_warning
    assert any(n.code == "needs_ocr" for n in s_ocr.coverage_notes)

    # Unsegmented / few clauses warning
    s_unseg = summarize([], coverage_inputs={"clause_count": 3, "unsegmented": True})
    assert s_unseg.has_coverage_warning
    assert any(n.code == "unsegmented_clauses" for n in s_unseg.coverage_notes)

    # Partial / error analysis runs
    cov_runs = [
        {
            "module": "consistency",
            "status": "partial",
            "error": "Time budget exceeded",
            "detector_status": {"detectors": [{"detector": "parties", "status": "skipped"}]},
        }
    ]
    s_runs = summarize([], coverage_inputs={"analysis_runs": cov_runs})
    assert s_runs.has_coverage_warning
    assert any("skipped" in n.code for n in s_runs.coverage_notes)


def test_summary_determinism() -> None:
    findings = [
        _make_finding("figure_words_mismatch", Severity.HIGH, clause_ref="2.1"),
        _make_finding("hidden_text", Severity.CRITICAL, page=1),
        _make_finding("date_order_conflict", Severity.LOW),
    ]
    s1 = summarize(findings)
    s2 = summarize(findings)
    assert s1.score == s2.score
    assert s1.band == s2.band
    assert s1.headline == s2.headline
    assert s1.minor_notes_count == s2.minor_notes_count
