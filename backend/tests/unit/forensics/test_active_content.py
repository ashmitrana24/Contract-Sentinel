"""Unit tests for active content and annotation overlay detector (forensics.active_content)."""

import pytest

from clauseguard.forensics.active_content import detect_active_content
from clauseguard.forensics.models import ForensicsSettings
from clauseguard.schemas.findings import Severity
from tests.unit.forensics.conftest import (
    make_active_content_pdf,
    make_pdf_with_highlights,
    make_pdf_with_links,
    make_plain_pdf,
)

pytestmark = pytest.mark.unit


def test_clean_pdf_no_active_content():
    pdf = make_plain_pdf()
    findings = detect_active_content(pdf, ForensicsSettings())
    assert len(findings) == 0


def test_javascript_action_detected():
    pdf = make_active_content_pdf("javascript")
    findings = detect_active_content(pdf, ForensicsSettings())
    assert len(findings) >= 1
    assert any(f.type == "active_content" and f.severity == Severity.MEDIUM for f in findings)


def test_launch_action_detected():
    pdf = make_active_content_pdf("launch")
    findings = detect_active_content(pdf, ForensicsSettings())
    assert len(findings) >= 1
    assert any(f.type == "active_content" and f.severity == Severity.MEDIUM for f in findings)


def test_open_action_detected():
    pdf = make_active_content_pdf("open_action")
    findings = detect_active_content(pdf, ForensicsSettings())
    assert len(findings) >= 1
    assert any(f.type == "active_content" for f in findings)


def test_annotation_overlay_detected():
    pdf = make_active_content_pdf("overlay")
    findings = detect_active_content(pdf, ForensicsSettings())
    assert len(findings) >= 1
    assert any(f.type == "annotation_overlay" for f in findings)


def test_benign_links_not_flagged():
    pdf = make_pdf_with_links()
    findings = detect_active_content(pdf, ForensicsSettings())
    assert len(findings) == 0


def test_benign_highlights_not_flagged():
    pdf = make_pdf_with_highlights()
    findings = detect_active_content(pdf, ForensicsSettings())
    assert len(findings) == 0
