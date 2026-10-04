"""Unit tests for the forensics orchestrator (forensics.run)."""

from unittest.mock import patch

import pytest

from clauseguard.forensics.models import ForensicsReport, ForensicsSettings
from clauseguard.forensics.run import analyze
from tests.unit.forensics.conftest import make_plain_pdf

pytestmark = pytest.mark.unit


def test_analyze_orchestrator_returns_report():
    pdf = make_plain_pdf()
    report = analyze(pdf, ForensicsSettings())
    assert isinstance(report, ForensicsReport)
    assert report.status == "ok"
    assert len(report.detector_status) == 5
    assert all(d.status == "ok" for d in report.detector_status)


def test_analyze_detector_isolation_on_exception():
    """If one detector raises an unhandled exception, it should not fail the entire run."""
    pdf = make_plain_pdf()

    with patch("clauseguard.forensics.run.detect_metadata", side_effect=RuntimeError("Simulated boom")):
        report = analyze(pdf, ForensicsSettings())
        assert report.status in ("partial", "degraded")
        meta_status = next(d for d in report.detector_status if d.name == "metadata")
        assert meta_status.status == "error"
        assert "Simulated boom" in (meta_status.error or "")

        # Other detectors ran fine
        inc_status = next(d for d in report.detector_status if d.name == "incremental")
        assert inc_status.status == "ok"


def test_analyze_respects_time_budget():
    pdf = make_plain_pdf()
    # Extremely tiny budget that is exceeded immediately
    settings = ForensicsSettings(budget_seconds=0.000001)

    cur_time = 0.0

    def fake_time():
        nonlocal cur_time
        cur_time += 5.0
        return cur_time

    with patch("time.monotonic", side_effect=fake_time):
        report = analyze(pdf, settings)
        # Should have skipped some detectors
        skipped = [d for d in report.detector_status if d.status == "skipped"]
        assert len(skipped) > 0
