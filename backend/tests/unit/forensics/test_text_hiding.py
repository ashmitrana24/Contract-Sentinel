"""Unit tests for text hiding detector (forensics.text_hiding)."""

import pytest

from clauseguard.forensics.models import ForensicsSettings
from clauseguard.forensics.text_hiding import detect_text_hiding
from clauseguard.schemas.findings import Severity
from tests.unit.forensics.conftest import make_hidden_text_pdf, make_plain_pdf

pytestmark = pytest.mark.unit


def test_clean_pdf_no_hidden_text():
    pdf = make_plain_pdf()
    findings = detect_text_hiding(pdf, ForensicsSettings())
    assert len(findings) == 0


def test_white_on_white_text_detected():
    pdf = make_hidden_text_pdf("white_on_white")
    findings = detect_text_hiding(pdf, ForensicsSettings())
    assert len(findings) >= 1
    assert any(f.type == "hidden_text" and f.severity == Severity.HIGH for f in findings)


def test_sub_1pt_font_detected():
    pdf = make_hidden_text_pdf("sub_1pt")
    findings = detect_text_hiding(pdf, ForensicsSettings())
    assert len(findings) >= 1
    assert any(f.type == "hidden_text" and f.severity == Severity.HIGH for f in findings)


def test_render_mode_3_detected():
    pdf = make_hidden_text_pdf("render_mode_3")
    findings = detect_text_hiding(pdf, ForensicsSettings())
    assert len(findings) >= 1
    assert any(f.type == "hidden_text" for f in findings)


def test_offpage_text_detected():
    pdf = make_hidden_text_pdf("offpage")
    findings = detect_text_hiding(pdf, ForensicsSettings())
    assert len(findings) >= 1
    assert any(f.type == "hidden_text" for f in findings)


def test_occluded_text_detected():
    pdf = make_hidden_text_pdf("occluded")
    findings = detect_text_hiding(pdf, ForensicsSettings())
    assert len(findings) >= 1
    assert any(f.type == "hidden_text" for f in findings)


def test_white_on_dark_banner_not_flagged():
    """Conservative check: white text on dark background has strong contrast and must not be flagged."""
    pdf = make_hidden_text_pdf("white_on_dark")
    findings = detect_text_hiding(pdf, ForensicsSettings())
    # Should produce 0 high/critical findings
    high_findings = [f for f in findings if f.severity in (Severity.HIGH, Severity.CRITICAL)]
    assert len(high_findings) == 0
