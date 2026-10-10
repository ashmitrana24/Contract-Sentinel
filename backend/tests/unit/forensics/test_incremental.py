import os
import tempfile

import pymupdf
import pytest

from clauseguard.forensics.incremental import detect_incremental
from clauseguard.forensics.models import ForensicsSettings
from clauseguard.schemas.findings import Severity
from tests.unit.forensics.conftest import make_incremental_pdf, make_plain_pdf

pytestmark = pytest.mark.unit


def test_clean_pdf_no_incremental_findings():
    pdf = make_plain_pdf()
    findings = detect_incremental(pdf, ForensicsSettings())
    assert len(findings) == 0


def test_incremental_edit_text_detected():
    pdf = make_incremental_pdf(edit_text=True)
    findings = detect_incremental(pdf, ForensicsSettings())
    assert len(findings) >= 1
    # Should flag incremental_update with HIGH severity
    inc_findings = [f for f in findings if f.type == "incremental_update"]
    assert len(inc_findings) >= 1
    assert any(f.severity in (Severity.HIGH, Severity.CRITICAL) for f in inc_findings)


def test_incremental_edit_amount_escalates_to_critical():
    pdf = make_incremental_pdf(edit_amount=True)
    findings = detect_incremental(pdf, ForensicsSettings())
    assert len(findings) >= 1
    inc_findings = [f for f in findings if f.type == "incremental_update"]
    assert any(f.severity == Severity.CRITICAL for f in inc_findings)


def test_incremental_metadata_only_is_low():
    pdf = make_incremental_pdf(metadata_only=True)
    findings = detect_incremental(pdf, ForensicsSettings())
    # Should not have HIGH or CRITICAL findings
    high_or_crit = [f for f in findings if f.severity in (Severity.HIGH, Severity.CRITICAL)]
    assert len(high_or_crit) == 0


def test_incremental_blank_field_filled_is_low():
    doc = pymupdf.open()
    p = doc.new_page()
    p.insert_text((50, 100), "Agreement text")
    w = pymupdf.Widget()
    w.rect = pymupdf.Rect(100, 100, 200, 120)
    w.field_type = pymupdf.PDF_WIDGET_TYPE_TEXT
    w.field_name = "user_name"
    p.add_widget(w)
    fd, path = tempfile.mkstemp(suffix=".pdf")
    os.close(fd)
    try:
        doc.save(path)
        doc.close()

        doc2 = pymupdf.open(path)
        p0 = doc2[0]
        w2 = next(p0.widgets())
        w2.field_value = "Alice"
        w2.update()
        doc2.save(path, incremental=True, encryption=pymupdf.PDF_ENCRYPT_KEEP)
        doc2.close()

        findings = detect_incremental(open(path, "rb").read(), ForensicsSettings())
        high_or_crit = [f for f in findings if f.severity in (Severity.HIGH, Severity.CRITICAL)]
        assert len(high_or_crit) == 0
    finally:
        os.unlink(path)


def test_incremental_filled_field_overwritten_amount_is_critical():
    doc = pymupdf.open()
    p = doc.new_page()
    p.insert_text((50, 100), "Agreement text")
    w = pymupdf.Widget()
    w.rect = pymupdf.Rect(100, 100, 200, 120)
    w.field_type = pymupdf.PDF_WIDGET_TYPE_TEXT
    w.field_name = "contract_amount"
    w.field_value = "Rs. 10,00,000"
    p.add_widget(w)
    fd, path = tempfile.mkstemp(suffix=".pdf")
    os.close(fd)
    try:
        doc.save(path)
        doc.close()

        doc2 = pymupdf.open(path)
        p0 = doc2[0]
        w2 = next(p0.widgets())
        w2.field_value = "Rs. 99,00,000"
        w2.update()
        doc2.save(path, incremental=True, encryption=pymupdf.PDF_ENCRYPT_KEEP)
        doc2.close()

        findings = detect_incremental(open(path, "rb").read(), ForensicsSettings())
        crits = [f for f in findings if f.severity == Severity.CRITICAL]
        assert len(crits) >= 1
        assert "contract_amount" in crits[0].evidence
        assert "Rs. 10,00,000" in crits[0].evidence
        assert "Rs. 99,00,000" in crits[0].evidence
    finally:
        os.unlink(path)
