"""Integration tests for upload API and end-to-end processing pipeline."""

from __future__ import annotations

from pathlib import Path

import pymupdf
import pytest
from fastapi.testclient import TestClient

from clauseguard.config import Settings
from clauseguard.db.models import Document, Job
from clauseguard.db.session import get_session
from clauseguard.storage.file_store import FileStore
from clauseguard.worker.main import Worker


def _make_pdf(text: str = "1. Preamble\nAgreement\n\n2. Scope\nWork", pages: int = 1, password: str | None = None) -> bytes:
    doc = pymupdf.open()
    for i in range(pages):
        p = doc.new_page(width=595, height=842)
        p.insert_textbox(pymupdf.Rect(50, 50, 500, 700), f"{text}\nPage {i+1}")
    if password:
        pdf_bytes = doc.tobytes(
            encryption=pymupdf.PDF_ENCRYPT_AES_256,
            user_pw=password,
            owner_pw="owner",
        )
    else:
        pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


@pytest.mark.integration
def test_upload_valid_pdf_and_process(
    client: TestClient,
    test_cfg: Settings,
    file_store: FileStore,
) -> None:
    pdf_bytes = _make_pdf("1. Definitions\nTerms\n\n2. Termination\nNotice required.", pages=2)
    resp = client.post(
        "/v1/documents",
        files={"file": ("contract.pdf", pdf_bytes, "application/pdf")},
    )
    assert resp.status_code == 202
    data = resp.json()
    doc_id = data["document_id"]
    job_id = data["job_id"]
    assert data["deduplicated"] is False

    # Process job via worker run_once
    worker = Worker(cfg=test_cfg)
    processed = worker.run_once()
    assert processed >= 1

    # Check job status via API
    job_resp = client.get(f"/v1/jobs/{job_id}")
    assert job_resp.status_code == 200
    jdata = job_resp.json()
    assert jdata["status"] == "succeeded"
    assert jdata["attempts"] == 1

    # Check document metadata
    doc_resp = client.get(f"/v1/documents/{doc_id}")
    assert doc_resp.status_code == 200
    ddata = doc_resp.json()
    assert ddata["page_count"] == 2
    assert ddata["latest_job_status"] == "succeeded"
    assert ddata["clause_count"] >= 2

    # Check pages endpoint
    pages_resp = client.get(f"/v1/documents/{doc_id}/pages")
    assert pages_resp.status_code == 200
    pdata = pages_resp.json()
    assert pdata["total"] == 2
    assert len(pdata["items"]) == 2

    # Check clauses endpoint
    clauses_resp = client.get(f"/v1/documents/{doc_id}/clauses")
    assert clauses_resp.status_code == 200
    cdata = clauses_resp.json()
    assert cdata["total"] >= 2


@pytest.mark.integration
def test_duplicate_upload_returns_200_deduplicated(
    client: TestClient,
    test_cfg: Settings,
) -> None:
    pdf_bytes = _make_pdf("1. First Clause\nContent\n\n2. Second Clause\nContent")

    # First upload
    r1 = client.post("/v1/documents", files={"file": ("test.pdf", pdf_bytes, "application/pdf")})
    assert r1.status_code == 202
    d1 = r1.json()
    assert d1["deduplicated"] is False

    # Second upload with same bytes
    r2 = client.post("/v1/documents", files={"file": ("duplicate.pdf", pdf_bytes, "application/pdf")})
    assert r2.status_code == 200
    d2 = r2.json()
    assert d2["deduplicated"] is True
    assert d2["document_id"] == d1["document_id"]
    assert d2["job_id"] == d1["job_id"]

    # Only one document row in DB
    with get_session() as s:
        doc_count = s.query(Document).count()
        job_count = s.query(Job).count()
        assert doc_count == 1
        assert job_count == 1


@pytest.mark.integration
def test_bad_inputs_validation(
    client: TestClient,
    test_cfg: Settings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # 1. Empty file -> 400
    r_empty = client.post("/v1/documents", files={"file": ("empty.pdf", b"", "application/pdf")})
    assert r_empty.status_code == 400
    assert r_empty.json()["error"] == "empty_file"

    # 2. Non-PDF file -> 400
    r_notpdf = client.post("/v1/documents", files={"file": ("test.txt", b"plain text content", "text/plain")})
    assert r_notpdf.status_code == 400
    assert r_notpdf.json()["error"] == "not_a_pdf"

    # 3. Oversized file -> 413
    huge_pdf = b"%PDF-" + (b"0" * 300)
    with monkeypatch.context() as m:
        from clauseguard.config import get_settings
        m.setattr(get_settings(), "max_upload_bytes", 50)
        r_large = client.post("/v1/documents", files={"file": ("big.pdf", huge_pdf, "application/pdf")})
        assert r_large.status_code == 413
        assert r_large.json()["error"] == "file_too_large"

    # 4. Truncated / corrupt PDF -> 422
    r_corrupt = client.post("/v1/documents", files={"file": ("corrupt.pdf", b"%PDF-1.4 but corrupt body", "application/pdf")})
    assert r_corrupt.status_code == 422
    assert r_corrupt.json()["error"] == "invalid_pdf"

    # 5. Password-protected PDF -> 422
    pw_pdf = _make_pdf("Secret", password="secret_password")
    r_pw = client.post("/v1/documents", files={"file": ("locked.pdf", pw_pdf, "application/pdf")})
    assert r_pw.status_code == 422
    assert r_pw.json()["error"] == "encrypted_pdf"

    # 6. Exceeds max pages -> 422
    multi_page = _make_pdf("Page", pages=5)
    with monkeypatch.context() as m:
        from clauseguard.config import get_settings
        m.setattr(get_settings(), "max_pages", 3)
        r_pages = client.post("/v1/documents", files={"file": ("long.pdf", multi_page, "application/pdf")})
        assert r_pages.status_code == 422
        assert r_pages.json()["error"] == "too_many_pages"

    # Assert nothing was stored or enqueued
    with get_session() as s:
        assert s.query(Document).count() == 0
        assert s.query(Job).count() == 0


@pytest.mark.integration
def test_tampered_pdfs_upload_and_parse(
    client: TestClient,
    test_cfg: Settings,
) -> None:
    """Test that incremental_edit and hidden_text tampered PDFs process cleanly."""
    dataset_dir = Path("data/generated")
    if not dataset_dir.exists():
        pytest.skip("data/generated not present")

    # Find sample incremental_edit and hidden_text PDFs
    pdf_files = list(dataset_dir.glob("*.pdf"))
    assert len(pdf_files) > 0

    # Pick up to 2 PDFs
    for pdf_file in pdf_files[:2]:
        resp = client.post(
            "/v1/documents",
            files={"file": (pdf_file.name, pdf_file.read_bytes(), "application/pdf")},
        )
        assert resp.status_code in (200, 202)
        if resp.status_code == 202:
            worker = Worker(cfg=test_cfg)
            worker.run_once()
            job_id = resp.json()["job_id"]
            jresp = client.get(f"/v1/jobs/{job_id}")
            assert jresp.json()["status"] == "succeeded"
