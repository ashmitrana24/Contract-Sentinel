"""Benign suite: 10 clean PDFs that must NEVER yield high or critical findings.

If any fires, the detector is too aggressive and must be tuned.
"""

import pytest

from clauseguard.forensics.models import ForensicsSettings
from clauseguard.forensics.run import analyze
from clauseguard.schemas.findings import Severity

pytestmark = pytest.mark.unit


def _assert_zero_high_or_critical(report, test_name: str):
    high_or_critical = [
        f for f in report.findings
        if f.severity in (Severity.HIGH, Severity.CRITICAL)
    ]
    assert len(high_or_critical) == 0, (
        f"False alarm on benign PDF '{test_name}': {[(f.type, f.severity, f.explanation) for f in high_or_critical]}"
    )


def test_benign_1_plain_text(benign_plain_pdf):
    report = analyze(benign_plain_pdf, ForensicsSettings())
    _assert_zero_high_or_critical(report, "plain_text")
    assert len(report.findings) == 0


def test_benign_2_headers_footers(benign_headers_footers_pdf):
    report = analyze(benign_headers_footers_pdf, ForensicsSettings())
    _assert_zero_high_or_critical(report, "headers_footers")
    assert len(report.findings) == 0


def test_benign_3_links(benign_links_pdf):
    report = analyze(benign_links_pdf, ForensicsSettings())
    _assert_zero_high_or_critical(report, "links")
    assert len(report.findings) == 0


def test_benign_4_highlights(benign_highlights_pdf):
    report = analyze(benign_highlights_pdf, ForensicsSettings())
    _assert_zero_high_or_critical(report, "highlights")
    assert len(report.findings) == 0


def test_benign_5_form_fields(benign_form_fields_pdf):
    report = analyze(benign_form_fields_pdf, ForensicsSettings())
    _assert_zero_high_or_critical(report, "form_fields")
    assert len(report.findings) == 0


def test_benign_6_word_export(benign_word_pdf):
    report = analyze(benign_word_pdf, ForensicsSettings())
    _assert_zero_high_or_critical(report, "word_export")
    assert len(report.findings) == 0


def test_benign_7_gdocs_export(benign_gdocs_pdf):
    report = analyze(benign_gdocs_pdf, ForensicsSettings())
    _assert_zero_high_or_critical(report, "gdocs_export")
    assert len(report.findings) == 0


def test_benign_8_scanned_page(benign_scanned_pdf):
    report = analyze(benign_scanned_pdf, ForensicsSettings())
    _assert_zero_high_or_critical(report, "scanned_page")
    assert len(report.findings) == 0


def test_benign_9_mixed_fonts(benign_mixed_fonts_pdf):
    report = analyze(benign_mixed_fonts_pdf, ForensicsSettings())
    _assert_zero_high_or_critical(report, "mixed_fonts")
    assert len(report.findings) == 0


def test_benign_10_embedded_images(benign_images_pdf):
    report = analyze(benign_images_pdf, ForensicsSettings())
    _assert_zero_high_or_critical(report, "embedded_images")
    assert len(report.findings) == 0
