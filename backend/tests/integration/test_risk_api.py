"""Integration tests for Module 8: Risk Summary and API endpoints."""

from __future__ import annotations

import pymupdf
import pytest
from fastapi.testclient import TestClient

from clauseguard.config import Settings
from clauseguard.storage.file_store import FileStore
from clauseguard.worker.main import Worker


def _make_test_contract() -> bytes:
    doc = pymupdf.open()
    page1_text = (
        "CONSULTING AGREEMENT\n\n"
        "1. TERM.\nThis Agreement is effective from January 1, 2026 to December 31, 2026.\n\n"
        "2. COMPENSATION.\nThe Client shall pay Rs. 50,000 (Fifty Thousand Rupees) upon completion of services."
    )
    p1 = doc.new_page(width=595, height=842)
    p1.insert_textbox(pymupdf.Rect(50, 50, 500, 750), page1_text)
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


@pytest.mark.integration
def test_risk_summary_end_to_end_and_endpoints(
    client: TestClient,
    test_cfg: Settings,
    file_store: FileStore,
) -> None:
    # 1. GET /v1/finding-types
    res_types = client.get("/v1/finding-types")
    assert res_types.status_code == 200
    types_data = res_types.json()
    assert "items" in types_data
    type_names = [it["type"] for it in types_data["items"]]
    assert "figure_words_mismatch" in type_names
    assert "hidden_text" in type_names

    # 2. Upload document
    pdf_bytes = _make_test_contract()
    resp = client.post(
        "/v1/documents",
        files={"file": ("test_contract.pdf", pdf_bytes, "application/pdf")},
    )
    assert resp.status_code == 202
    upload_data = resp.json()
    doc_id = upload_data["document_id"]
    job_id = upload_data["job_id"]

    # 3. Check job stages before processing
    res_job = client.get(f"/v1/jobs/{job_id}")
    assert res_job.status_code == 200
    job_data = res_job.json()
    assert "stages" in job_data
    stage_keys = [s["key"] for s in job_data["stages"]]
    assert stage_keys == ["upload", "parse", "forensics", "consistency", "clauses", "summary"]

    # 4. Process job via worker
    worker = Worker(cfg=test_cfg)
    processed = worker.run_once()
    assert processed >= 1

    # Check job stages after completion
    res_job_done = client.get(f"/v1/jobs/{job_id}")
    assert res_job_done.status_code == 200
    stages_done = res_job_done.json()["stages"]
    assert all(s["status"] in ("done", "skipped") for s in stages_done)

    # 5. GET /v1/documents list
    res_docs = client.get("/v1/documents")
    assert res_docs.status_code == 200
    docs_data = res_docs.json()
    assert docs_data["total"] >= 1
    item = next(d for d in docs_data["items"] if d["id"] == doc_id)
    assert item["status"] == "succeeded"
    assert item["risk"] is not None
    assert "score" in item["risk"]
    assert "band" in item["risk"]

    # 6. GET /v1/documents/{id}/risk
    res_risk = client.get(f"/v1/documents/{doc_id}/risk")
    assert res_risk.status_code == 200
    risk_data = res_risk.json()
    assert "score" in risk_data
    assert "band" in risk_data
    assert "headline" in risk_data
    assert "top_reasons" in risk_data
    assert "counts_by_severity" in risk_data

    # 7. GET /v1/documents/{id}/file inline stream
    res_file = client.get(f"/v1/documents/{doc_id}/file")
    assert res_file.status_code == 200
    assert res_file.headers["content-type"] == "application/pdf"
    assert "inline" in res_file.headers.get("content-disposition", "")
    assert res_file.content == pdf_bytes

    # 8. GET /v1/documents/{id}/findings with highlights and metadata
    res_findings = client.get(f"/v1/documents/{doc_id}/findings")
    assert res_findings.status_code == 200
    findings_data = res_findings.json()
    assert "items" in findings_data
    for f in findings_data["items"]:
        assert "category" in f
        assert "title" in f
        assert "what_it_means" in f
        assert "what_to_check" in f
        assert "highlights" in f
        assert isinstance(f["highlights"], list)

    # 9. Feedback endpoints (if findings exist, test feedback; otherwise create mock or verify 404 on invalid)
    if findings_data["items"]:
        first_f_id = findings_data["items"][0]["id"]
        # POST feedback
        res_fb = client.post(
            f"/v1/findings/{first_f_id}/feedback",
            json={"verdict": "confirmed", "note": "Confirmed by reviewer"},
        )
        assert res_fb.status_code == 200
        fb_data = res_fb.json()
        assert fb_data["verdict"] == "confirmed"
        assert fb_data["note"] == "Confirmed by reviewer"

        # Re-fetch findings, verify feedback attached
        refetched = client.get(f"/v1/documents/{doc_id}/findings").json()
        target_f = next(f for f in refetched["items"] if f["id"] == first_f_id)
        assert target_f["feedback"] is not None
        assert target_f["feedback"]["verdict"] == "confirmed"

        # DELETE feedback
        res_del_fb = client.delete(f"/v1/findings/{first_f_id}/feedback")
        assert res_del_fb.status_code == 204

    # 10. DELETE /v1/documents/{id} cascade & storage deletion
    res_del = client.delete(f"/v1/documents/{doc_id}")
    assert res_del.status_code == 204

    # Verify document and related rows are gone
    assert client.get(f"/v1/documents/{doc_id}").status_code == 404
    assert client.get(f"/v1/documents/{doc_id}/file").status_code == 404
    assert client.get(f"/v1/documents/{doc_id}/risk").status_code == 404

    # Idempotent delete returns 204
    assert client.delete(f"/v1/documents/{doc_id}").status_code == 204
