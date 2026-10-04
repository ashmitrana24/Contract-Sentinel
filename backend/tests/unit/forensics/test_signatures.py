"""Unit tests for signature integrity detector (forensics.signatures)."""

import pytest

from clauseguard.forensics.models import ForensicsSettings
from clauseguard.forensics.signatures import detect_signatures
from clauseguard.schemas.findings import Severity
from tests.unit.forensics.conftest import make_plain_pdf, make_signed_pdf

pytestmark = pytest.mark.unit


def test_unsigned_pdf_no_signature_findings():
    pdf = make_plain_pdf()
    findings = detect_signatures(pdf, ForensicsSettings())
    assert len(findings) == 0


def test_valid_signed_pdf_no_findings():
    pdf = make_signed_pdf()
    findings = detect_signatures(pdf, ForensicsSettings())
    assert len(findings) == 0


def test_corrupted_byte_range_signature_invalid():
    pdf = make_signed_pdf(corrupt_bytes=True)
    findings = detect_signatures(pdf, ForensicsSettings())
    assert len(findings) >= 1
    assert any(f.type == "signature_invalid" and f.severity == Severity.CRITICAL for f in findings)


def test_post_signature_modification_detected():
    pdf = make_signed_pdf(modify_after=True)
    findings = detect_signatures(pdf, ForensicsSettings())
    assert len(findings) >= 1
    assert any(f.type == "post_signature_modification" and f.severity == Severity.CRITICAL for f in findings)
