"""Integration tests for Module 3: PDF Forensics pipeline."""

from __future__ import annotations

import io

import pytest
import redis
from fastapi.testclient import TestClient

from clauseguard.config import Settings
from clauseguard.storage.file_store import FileStore
from clauseguard.worker.processor import process_job_message
from tests.unit.forensics.conftest import make_incremental_pdf, make_plain_pdf

pytestmark = pytest.mark.integration


def test_clean_pdf_pipeline_has_zero_findings(
    client: TestClient,
    redis_client: redis.Redis,
    test_cfg: Settings,
    file_store: FileStore,
):
    pdf_bytes = make_plain_pdf()
    resp = client.post(
        "/v1/documents",
        files={"file": ("contract.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
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

    # Check document metadata
    doc_resp = client.get(f"/v1/documents/{doc_id}")
    assert doc_resp.status_code == 200
    doc_data = doc_resp.json()
    assert doc_data["finding_count"] == 0

    # Query findings endpoint
    findings_resp = client.get(f"/v1/documents/{doc_id}/findings")
    assert findings_resp.status_code == 200
    f_data = findings_resp.json()
    assert f_data["total"] == 0
    assert len(f_data["items"]) == 0

    # Query analysis run endpoint
    analysis_resp = client.get(f"/v1/documents/{doc_id}/analysis")
    assert analysis_resp.status_code == 200
    runs = analysis_resp.json()
    assert len(runs) == 1
    assert runs[0]["module"] == "pdf_forensics"
    assert runs[0]["status"] == "ok"


def test_tampered_pdf_pipeline_stores_and_returns_findings(
    client: TestClient,
    redis_client: redis.Redis,
    test_cfg: Settings,
    file_store: FileStore,
):
    tampered_bytes = make_incremental_pdf(edit_amount=True)
    resp = client.post(
        "/v1/documents",
        files={"file": ("tampered.pdf", io.BytesIO(tampered_bytes), "application/pdf")},
    )
    assert resp.status_code == 202
    data = resp.json()
    doc_id = data["document_id"]
    job_id = data["job_id"]

    messages = redis_client.xread({test_cfg.redis_stream: "0-0"}, count=1)
    entry_id, _payload = messages[0][1][0]

    # Process with worker
    success = process_job_message(job_id, entry_id, redis_client, store=file_store, cfg=test_cfg)
    assert success is True

    # Check document response includes finding_count >= 1
    doc_resp = client.get(f"/v1/documents/{doc_id}")
    assert doc_resp.status_code == 200
    doc_data = doc_resp.json()
    assert doc_data["finding_count"] >= 1

    # Query findings endpoint
    findings_resp = client.get(f"/v1/documents/{doc_id}/findings")
    assert findings_resp.status_code == 200
    f_data = findings_resp.json()
    assert f_data["total"] >= 1
    types = [f["type"] for f in f_data["items"]]
    assert "incremental_update" in types

    # Test filtering by severity
    crit_resp = client.get(f"/v1/documents/{doc_id}/findings?severity=critical")
    assert crit_resp.status_code == 200
    crit_data = crit_resp.json()
    assert crit_data["total"] >= 1
    assert all(f["severity"] == "critical" for f in crit_data["items"])
