"""Unit tests for metadata anomaly detector (forensics.metadata)."""

import pytest

from clauseguard.forensics.metadata import detect_metadata
from clauseguard.forensics.models import ForensicsSettings
from clauseguard.schemas.findings import Severity
from tests.unit.forensics.conftest import make_metadata_pdf, make_plain_pdf

pytestmark = pytest.mark.unit


def test_clean_pdf_no_metadata_findings():
    pdf = make_plain_pdf()
    findings = detect_metadata(pdf, ForensicsSettings())
    assert len(findings) == 0


def test_future_date_detected():
    pdf = make_metadata_pdf("future_date")
    findings = detect_metadata(pdf, ForensicsSettings())
    assert len(findings) >= 1
    assert any(f.type == "metadata_anomaly" for f in findings)
    # Metadata anomalies must remain LOW severity
    assert all(f.severity == Severity.LOW for f in findings)


def test_mod_before_create_detected():
    pdf = make_metadata_pdf("mod_before_create")
    findings = detect_metadata(pdf, ForensicsSettings())
    assert len(findings) >= 1
    assert any(f.type == "metadata_anomaly" for f in findings)
    assert all(f.severity == Severity.LOW for f in findings)


def test_online_editor_detected():
    pdf = make_metadata_pdf("ilovepdf")
    findings = detect_metadata(pdf, ForensicsSettings())
    assert len(findings) >= 1
    assert any(f.type == "metadata_anomaly" for f in findings)
    assert any("ilovepdf" in f.evidence.lower() or "ilovepdf" in f.explanation.lower() for f in findings)
