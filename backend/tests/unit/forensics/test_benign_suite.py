"""Benign suite: 17 clean PDFs that must NEVER yield medium, high, or critical findings.

If any fires, the detector is too aggressive and must be tuned.
"""

import pytest

from clauseguard.forensics.models import ForensicsSettings
from clauseguard.forensics.run import analyze
from clauseguard.schemas.findings import Severity

pytestmark = pytest.mark.unit


def _assert_zero_above_low(report, test_name: str):
    above_low = [
        f for f in report.findings
        if f.severity in (Severity.MEDIUM, Severity.HIGH, Severity.CRITICAL)
    ]
    assert len(above_low) == 0, (
        f"False alarm on benign PDF '{test_name}': {[(f.type, f.severity, f.explanation) for f in above_low]}"
    )


def test_benign_1_plain_text(benign_plain_pdf):
    report = analyze(benign_plain_pdf, ForensicsSettings())
    _assert_zero_above_low(report, "plain_text")
    assert len(report.findings) == 0


def test_benign_2_headers_footers(benign_headers_footers_pdf):
    report = analyze(benign_headers_footers_pdf, ForensicsSettings())
    _assert_zero_above_low(report, "headers_footers")
    assert len(report.findings) == 0


def test_benign_3_links(benign_links_pdf):
    report = analyze(benign_links_pdf, ForensicsSettings())
    _assert_zero_above_low(report, "links")
    assert len(report.findings) == 0


def test_benign_4_highlights(benign_highlights_pdf):
    report = analyze(benign_highlights_pdf, ForensicsSettings())
    _assert_zero_above_low(report, "highlights")
    assert len(report.findings) == 0


def test_benign_5_form_fields(benign_form_fields_pdf):
    report = analyze(benign_form_fields_pdf, ForensicsSettings())
    _assert_zero_above_low(report, "form_fields")
    assert len(report.findings) == 0


def test_benign_6_word_export(benign_word_pdf):
    report = analyze(benign_word_pdf, ForensicsSettings())
    _assert_zero_above_low(report, "word_export")
    assert len(report.findings) == 0


def test_benign_7_gdocs_export(benign_gdocs_pdf):
    report = analyze(benign_gdocs_pdf, ForensicsSettings())
    _assert_zero_above_low(report, "gdocs_export")
    assert len(report.findings) == 0


def test_benign_8_scanned_page(benign_scanned_pdf):
    report = analyze(benign_scanned_pdf, ForensicsSettings())
    _assert_zero_above_low(report, "scanned_page")
    assert len(report.findings) == 0


def test_benign_9_mixed_fonts(benign_mixed_fonts_pdf):
    report = analyze(benign_mixed_fonts_pdf, ForensicsSettings())
    _assert_zero_above_low(report, "mixed_fonts")
    assert len(report.findings) == 0


def test_benign_10_embedded_images(benign_images_pdf):
    report = analyze(benign_images_pdf, ForensicsSettings())
    _assert_zero_above_low(report, "embedded_images")
    assert len(report.findings) == 0


def test_benign_11_acroform_incremental(benign_filled_acroform_pdf):
    report = analyze(benign_filled_acroform_pdf, ForensicsSettings())
    _assert_zero_above_low(report, "acroform_incremental")


def test_benign_12_ocr_scanned(benign_ocr_scanned_pdf):
    report = analyze(benign_ocr_scanned_pdf, ForensicsSettings())
    _assert_zero_above_low(report, "ocr_scanned")


def test_benign_13_white_on_dark_header(benign_white_on_dark_header_pdf):
    report = analyze(benign_white_on_dark_header_pdf, ForensicsSettings())
    _assert_zero_above_low(report, "white_on_dark_header")


def test_benign_14_legitimately_signed(benign_signed_pdf):
    report = analyze(benign_signed_pdf, ForensicsSettings())
    _assert_zero_above_low(report, "legitimately_signed")


def test_benign_15_linearized(benign_linearized_pdf):
    report = analyze(benign_linearized_pdf, ForensicsSettings())
    _assert_zero_above_low(report, "linearized")


def test_benign_16_resaved(benign_resaved_pdf):
    report = analyze(benign_resaved_pdf, ForensicsSettings())
    _assert_zero_above_low(report, "resaved")


def test_benign_17_footnote_6pt(benign_footnote_pdf):
    report = analyze(benign_footnote_pdf, ForensicsSettings())
    _assert_zero_above_low(report, "footnote_6pt")
