"""Integration tests for Module 4: Consistency Checks pipeline."""

from __future__ import annotations

import io
from pathlib import Path
from unittest.mock import patch

import pytest
import redis
from fastapi.testclient import TestClient

from clauseguard.config import Settings
from clauseguard.storage.file_store import FileStore
from clauseguard.worker.processor import process_job_message

pytestmark = pytest.mark.integration

DATA_DIR = Path(__file__).resolve().parents[3] / "data" / "generated"


def test_amount_figure_only_pipeline_finds_mismatch(
    client: TestClient,
    redis_client: redis.Redis,
    test_cfg: Settings,
    file_store: FileStore,
):
    """Upload a datagen amount_figure_only PDF -> processed -> figure_words_mismatch finding via API."""
    sample_pdf = DATA_DIR / "synth_0000_v0.pdf"
    assert sample_pdf.exists(), f"Sample PDF not found at {sample_pdf}"
    pdf_bytes = sample_pdf.read_bytes()

    resp = client.post(
        "/v1/documents",
        files={"file": (sample_pdf.name, io.BytesIO(pdf_bytes), "application/pdf")},
    )
    assert resp.status_code == 202
    data = resp.json()
    doc_id = data["document_id"]
    job_id = data["job_id"]

    # Read message from Redis stream and process via worker
    messages = redis_client.xread({test_cfg.redis_stream: "0-0"}, count=1)
    assert len(messages) == 1
    _stream_name, entries = messages[0]
    entry_id, payload = entries[0]
    assert payload["job_id"] == str(job_id)

    # Process job with worker
    success = process_job_message(job_id, entry_id, redis_client, store=file_store, cfg=test_cfg)
    assert success is True

    # Check job succeeded
    job_resp = client.get(f"/v1/jobs/{job_id}")
    assert job_resp.status_code == 200
    assert job_resp.json()["status"] == "succeeded"

    # Check document endpoint includes finding_counts_by_module
    doc_resp = client.get(f"/v1/documents/{doc_id}")
    assert doc_resp.status_code == 200
    doc_data = doc_resp.json()
    assert "consistency" in doc_data["finding_counts_by_module"]
    assert doc_data["finding_counts_by_module"]["consistency"] >= 1

    # Query findings endpoint with module=consistency
    findings_resp = client.get(f"/v1/documents/{doc_id}/findings?module=consistency")
    assert findings_resp.status_code == 200
    f_data = findings_resp.json()
    assert f_data["total"] >= 1
    types = [item["type"] for item in f_data["items"]]
    assert "figure_words_mismatch" in types

    # Check analysis run endpoint includes consistency module
    analysis_resp = client.get(f"/v1/documents/{doc_id}/analysis")
    assert analysis_resp.status_code == 200
    runs = analysis_resp.json()
    consistency_runs = [r for r in runs if r["module"] == "consistency"]
    assert len(consistency_runs) == 1
    assert consistency_runs[0]["status"] == "ok"
    assert "detectors" in consistency_runs[0]["detector_status"]


def test_clean_pdf_has_no_findings_above_low(
    client: TestClient,
    redis_client: redis.Redis,
    test_cfg: Settings,
    file_store: FileStore,
):
    """Upload a clean synthetic PDF -> nothing above LOW severity for consistency."""
    sample_pdf = DATA_DIR / "synth_0000_clean.pdf"
    assert sample_pdf.exists(), f"Sample PDF not found at {sample_pdf}"
    pdf_bytes = sample_pdf.read_bytes()

    resp = client.post(
        "/v1/documents",
        files={"file": (sample_pdf.name, io.BytesIO(pdf_bytes), "application/pdf")},
    )
    assert resp.status_code == 202
    data = resp.json()
    doc_id = data["document_id"]
    job_id = data["job_id"]

    messages = redis_client.xread({test_cfg.redis_stream: "0-0"}, count=1)
    entry_id, _payload = messages[0][1][0]
    success = process_job_message(job_id, entry_id, redis_client, store=file_store, cfg=test_cfg)
    assert success is True

    job_resp = client.get(f"/v1/jobs/{job_id}")
    assert job_resp.status_code == 200
    assert job_resp.json()["status"] == "succeeded"

    # Check findings for module=consistency
    findings_resp = client.get(f"/v1/documents/{doc_id}/findings?module=consistency")
    assert findings_resp.status_code == 200
    f_data = findings_resp.json()
    for item in f_data["items"]:
        assert item["severity"] == "low", f"Clean document produced non-low finding: {item}"


def test_reprocessing_is_idempotent(
    client: TestClient,
    redis_client: redis.Redis,
    test_cfg: Settings,
    file_store: FileStore,
):
    """Reprocessing the same document does not duplicate findings or analysis runs."""
    sample_pdf = DATA_DIR / "synth_0000_v0.pdf"
    assert sample_pdf.exists()
    pdf_bytes = sample_pdf.read_bytes()

    resp = client.post(
        "/v1/documents",
        files={"file": (sample_pdf.name, io.BytesIO(pdf_bytes), "application/pdf")},
    )
    assert resp.status_code == 202
    data = resp.json()
    doc_id = data["document_id"]
    job_id = data["job_id"]

    messages = redis_client.xread({test_cfg.redis_stream: "0-0"}, count=1)
    entry_id, _payload = messages[0][1][0]
    success = process_job_message(job_id, entry_id, redis_client, store=file_store, cfg=test_cfg)
    assert success is True

    findings_1 = client.get(f"/v1/documents/{doc_id}/findings?module=consistency").json()["total"]
    runs_1 = len(client.get(f"/v1/documents/{doc_id}/analysis").json())

    # Re-process directly with worker execute function
    from clauseguard.worker.processor import _execute_parsing

    _execute_parsing(data["document_id"], data["job_id"], file_store, test_cfg)

    findings_2 = client.get(f"/v1/documents/{doc_id}/findings?module=consistency").json()["total"]
    runs_2 = len(client.get(f"/v1/documents/{doc_id}/analysis").json())

    assert findings_1 == findings_2
    assert runs_1 == runs_2


def test_forced_consistency_exception_succeeds_with_error_run(
    client: TestClient,
    redis_client: redis.Redis,
    test_cfg: Settings,
    file_store: FileStore,
):
    """Forced consistency exception must not fail job; job succeeds and analysis_runs.status='error'."""
    sample_pdf = DATA_DIR / "synth_0000_clean.pdf"
    assert sample_pdf.exists()
    pdf_bytes = sample_pdf.read_bytes()

    resp = client.post(
        "/v1/documents",
        files={"file": ("test_error.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
    )
    assert resp.status_code == 202
    data = resp.json()
    doc_id = data["document_id"]
    job_id = data["job_id"]

    messages = redis_client.xread({test_cfg.redis_stream: "0-0"}, count=1)
    entry_id, _payload = messages[0][1][0]

    with patch(
        "clauseguard.worker.processor.analyze_consistency",
        side_effect=RuntimeError("Forced consistency crash"),
    ):
        success = process_job_message(job_id, entry_id, redis_client, store=file_store, cfg=test_cfg)

    assert success is True
    job_resp = client.get(f"/v1/jobs/{job_id}")
    assert job_resp.status_code == 200
    assert job_resp.json()["status"] == "succeeded"

    # Analysis runs must record status="error"
    analysis_resp = client.get(f"/v1/documents/{doc_id}/analysis")
    assert analysis_resp.status_code == 200
    runs = analysis_resp.json()
    c_run = next(r for r in runs if r["module"] == "consistency")
    assert c_run["status"] == "error"
    assert "Forced consistency crash" in (c_run["error"] or "")
