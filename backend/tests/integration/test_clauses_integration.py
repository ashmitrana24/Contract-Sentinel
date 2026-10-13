"""Integration tests for Module 5: Clause classification and key-term extraction."""

from __future__ import annotations

import pymupdf
import pytest
from fastapi.testclient import TestClient

from clauseguard.config import Settings
from clauseguard.storage.file_store import FileStore
from clauseguard.worker.main import Worker


def _make_contract_pdf() -> bytes:
    doc = pymupdf.open()
    page1_text = (
        "CONTRACT FOR SERVICES\n\n"
        "1. DEFINITIONS.\nIn this Agreement, terms shall have their standard meanings.\n\n"
        "2. TERM AND RENEWAL.\nThis Agreement shall commence on the Effective Date and shall continue for one year. "
        "It shall automatically renew for successive terms of 1 year each unless either party provides written notice of non-renewal at least 60 days prior to expiration.\n\n"
        "3. TERMINATION.\nEither party may terminate this Agreement for convenience upon thirty (30) days prior written notice."
    )
    p1 = doc.new_page(width=595, height=842)
    p1.insert_textbox(pymupdf.Rect(50, 50, 500, 750), page1_text)

    page2_text = (
        "4. LIMITATION OF LIABILITY.\nIn no event shall either party's total aggregate liability under this agreement exceed $500,000.\n\n"
        "5. NON-COMPETITION.\nEmployee shall not compete directly or indirectly with the Company for a period of two (2) years following termination.\n\n"
        "6. PAYMENT TERMS.\nAll undisputed invoices shall be payable Net 30 days.\n\n"
        "7. GOVERNING LAW.\nThis Agreement shall be governed by and construed in accordance with the laws of the State of Delaware."
    )
    p2 = doc.new_page(width=595, height=842)
    p2.insert_textbox(pymupdf.Rect(50, 50, 500, 750), page2_text)

    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


@pytest.mark.integration
def test_clauses_end_to_end_pipeline_and_api(
    client: TestClient,
    test_cfg: Settings,
    file_store: FileStore,
) -> None:
    pdf_bytes = _make_contract_pdf()

    resp = client.post(
        "/v1/documents",
        files={"file": ("contract_clauses.pdf", pdf_bytes, "application/pdf")},
    )
    assert resp.status_code == 202
    data = resp.json()
    doc_id = data["document_id"]
    job_id = data["job_id"]

    # Process job via worker
    worker = Worker(cfg=test_cfg)
    processed = worker.run_once()
    assert processed >= 1

    # Verify job succeeded
    job_resp = client.get(f"/v1/jobs/{job_id}")
    assert job_resp.status_code == 200
    assert job_resp.json()["status"] == "succeeded"

    # 1. Test GET /v1/documents/{doc_id}/clauses with labels
    clauses_resp = client.get(f"/v1/documents/{doc_id}/clauses")
    assert clauses_resp.status_code == 200
    c_data = clauses_resp.json()
    assert c_data["total"] >= 6

    # Verify at least one clause has labels attached
    clauses_with_labels = [c for c in c_data["items"] if len(c["labels"]) > 0]
    assert len(clauses_with_labels) > 0

    gov_clause = next(
        (c for c in c_data["items"] if any(lbl["label"] == "governing_law" for lbl in c["labels"])),
        None,
    )
    assert gov_clause is not None
    gov_label = next(lbl for lbl in gov_clause["labels"] if lbl["label"] == "governing_law")
    assert gov_label["score"] > 0
    assert gov_label["method"] in ("rules", "model", "both")
    assert "Delaware" in gov_label["evidence"]

    # 2. Test GET /v1/documents/{doc_id}/clause-types
    types_resp = client.get(f"/v1/documents/{doc_id}/clause-types")
    assert types_resp.status_code == 200
    t_data = types_resp.json()
    assert t_data["total_types"] >= 3
    found_labels = {item["label"] for item in t_data["items"]}
    assert "governing_law" in found_labels

    # 3. Test GET /v1/documents/{doc_id}/attributes
    attrs_resp = client.get(f"/v1/documents/{doc_id}/attributes")
    assert attrs_resp.status_code == 200
    a_data = attrs_resp.json()
    assert a_data["governing_law_jurisdiction"] == "Delaware"
    assert a_data["auto_renews"] is True
    assert a_data["renewal_term_months"] == 12
    assert a_data["non_renewal_notice_days"] == 60
    assert a_data["termination_notice_days"] == 30
    assert a_data["liability_cap"] == {"type": "fixed_amount", "amount": 500000.0, "currency": "USD"}
    assert a_data["non_compete_duration_months"] == 24
    assert a_data["payment_terms_days"] == 30


@pytest.mark.integration
def test_reprocessing_clauses_is_idempotent(
    client: TestClient,
    test_cfg: Settings,
    file_store: FileStore,
) -> None:
    pdf_bytes = _make_contract_pdf()

    resp = client.post(
        "/v1/documents",
        files={"file": ("contract_idempotent.pdf", pdf_bytes, "application/pdf")},
    )
    assert resp.status_code == 202
    doc_id = resp.json()["document_id"]

    worker = Worker(cfg=test_cfg)
    assert worker.run_once() >= 1

    # First fetch count
    types1 = client.get(f"/v1/documents/{doc_id}/clause-types").json()

    # Re-run parser directly
    import uuid

    from clauseguard.worker.processor import _execute_parsing
    _execute_parsing(uuid.UUID(doc_id), uuid.uuid4(), file_store, test_cfg)

    # Second fetch count
    types2 = client.get(f"/v1/documents/{doc_id}/clause-types").json()
    assert types1["total_types"] == types2["total_types"]
    assert len(types1["items"]) == len(types2["items"])
