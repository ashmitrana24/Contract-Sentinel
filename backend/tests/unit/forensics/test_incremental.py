"""Unit tests for incremental edit detector (forensics.incremental)."""

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
