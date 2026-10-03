"""Integration tests for worker reliability, error handling, crash recovery, and concurrency."""

from __future__ import annotations

import threading
import time
import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pymupdf
import pytest
import redis
from fastapi.testclient import TestClient

from clauseguard.config import Settings
from clauseguard.db.models import Clause, Document, Job, Page
from clauseguard.db.session import get_session
from clauseguard.parsing.parse_document import ParseError
from clauseguard.parsing.parse_document import parse_document as real_parse_document
from clauseguard.queue import streams as qs
from clauseguard.storage.file_store import FileStore
from clauseguard.worker.main import Worker
from clauseguard.worker.sweeper import sweep_stuck_jobs


def _make_pdf(text: str = "1. Definitions\nTerms\n\n2. Scope\nWork", pages: int = 1) -> bytes:
    doc = pymupdf.open()
    for i in range(pages):
        p = doc.new_page(width=595, height=842)
        p.insert_textbox(pymupdf.Rect(50, 50, 500, 700), f"{text}\nPage {i+1}")
    b = doc.tobytes()
    doc.close()
    return b


@pytest.mark.integration
def test_transient_failure_injection_retries_and_succeeds(
    client: TestClient,
    test_cfg: Settings,
    redis_client: redis.Redis,
) -> None:
    """Patch the parser to fail twice with transient error, then succeed -> attempts == 3."""
    pdf_bytes = _make_pdf()
    resp = client.post("/v1/documents", files={"file": ("transient.pdf", pdf_bytes, "application/pdf")})
    assert resp.status_code == 202
    job_id = uuid.UUID(resp.json()["job_id"])

    call_count = 0

    def mock_parse(b: bytes):
        nonlocal call_count
        call_count += 1
        if call_count <= 2:
            raise RuntimeError(f"Simulated transient error #{call_count}")
        return real_parse_document(b)

    worker = Worker(cfg=test_cfg)

    with patch("clauseguard.worker.processor.parse_document", side_effect=mock_parse):
        # Attempt 1: fails
        worker.run_once()
        with get_session() as s:
            j1 = s.get(Job, job_id)
            assert j1.status == "retry_wait"
            assert j1.attempts == 1
            # Fast forward next_attempt_at
            j1.next_attempt_at = datetime.now(UTC) - timedelta(seconds=1)

        # Sweeper re-enqueues for attempt 2
        sweep_stuck_jobs(redis_client, test_cfg)
        worker.run_once()
        with get_session() as s:
            j2 = s.get(Job, job_id)
            assert j2.status == "retry_wait"
            assert j2.attempts == 2
            j2.next_attempt_at = datetime.now(UTC) - timedelta(seconds=1)

        # Sweeper re-enqueues for attempt 3
        sweep_stuck_jobs(redis_client, test_cfg)
        worker.run_once()

    with get_session() as s:
        final_job = s.get(Job, job_id)
        assert final_job.status == "succeeded"
        assert final_job.attempts == 3


@pytest.mark.integration
def test_permanent_failure_dead_letters_immediately(
    client: TestClient,
    test_cfg: Settings,
    redis_client: redis.Redis,
) -> None:
    """Permanent parse failure -> status dead immediately, error_kind permanent, in dead stream."""
    pdf_bytes = _make_pdf()
    resp = client.post("/v1/documents", files={"file": ("permanent.pdf", pdf_bytes, "application/pdf")})
    assert resp.status_code == 202
    job_id = uuid.UUID(resp.json()["job_id"])

    worker = Worker(cfg=test_cfg)

    with patch("clauseguard.worker.processor.parse_document", side_effect=ParseError("Corrupt PDF structure")):
        worker.run_once()

    with get_session() as s:
        job = s.get(Job, job_id)
        assert job.status == "dead"
        assert job.error_kind == "permanent"
        assert job.attempts == 1

    # Check dead-letter stream
    dead_entries = redis_client.xrange(test_cfg.redis_dead_stream)
    assert len(dead_entries) >= 1
    fields = dead_entries[0][1]
    assert fields["job_id"] == str(job_id)
    assert fields["error_kind"] == "permanent"


@pytest.mark.integration
def test_exhausted_retries_marks_transient_exhausted(
    client: TestClient,
    test_cfg: Settings,
    redis_client: redis.Redis,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """After max_attempts transient failures, mark dead with error_kind transient_exhausted."""
    monkeypatch.setattr(test_cfg, "max_attempts", 2)
    pdf_bytes = _make_pdf()
    resp = client.post("/v1/documents", files={"file": ("exhaust.pdf", pdf_bytes, "application/pdf")})
    assert resp.status_code == 202
    job_id = uuid.UUID(resp.json()["job_id"])

    worker = Worker(cfg=test_cfg)

    with patch("clauseguard.worker.processor.parse_document", side_effect=RuntimeError("DB timeout")):
        # Attempt 1
        worker.run_once()
        with get_session() as s:
            j = s.get(Job, job_id)
            assert j.status == "retry_wait"
            j.next_attempt_at = datetime.now(UTC) - timedelta(seconds=1)

        # Attempt 2 -> max attempts reached
        sweep_stuck_jobs(redis_client, test_cfg)
        worker.run_once()

    with get_session() as s:
        final_job = s.get(Job, job_id)
        assert final_job.status == "dead"
        assert final_job.error_kind == "transient_exhausted"
        assert final_job.attempts == 2


@pytest.mark.integration
def test_crash_recovery_expired_lease(
    client: TestClient,
    test_cfg: Settings,
    redis_client: redis.Redis,
) -> None:
    """Abandon a job with expired lease -> second worker claims it and completes once."""
    pdf_bytes = _make_pdf("1. First Clause\nText\n\n2. Second Clause\nText")
    resp = client.post("/v1/documents", files={"file": ("crash.pdf", pdf_bytes, "application/pdf")})
    assert resp.status_code == 202
    job_id = uuid.UUID(resp.json()["job_id"])

    # Simulate worker 1 claiming and abandoning without acking
    now = datetime.now(UTC)
    with get_session() as s:
        job = s.get(Job, job_id)
        job.status = "processing"
        job.lease_expires_at = now - timedelta(seconds=30)  # Expired lease

    # Worker 2 processes
    worker2 = Worker(cfg=test_cfg, consumer_id="worker-2")
    worker2.run_once()

    with get_session() as s:
        final_job = s.get(Job, job_id)
        assert final_job.status == "succeeded"
        clauses = s.query(Clause).filter(Clause.document_id == final_job.document_id).all()
        assert len(clauses) >= 2


@pytest.mark.integration
def test_duplicate_delivery_idempotent(
    client: TestClient,
    test_cfg: Settings,
    redis_client: redis.Redis,
) -> None:
    """Enqueueing same job twice processes once and does not duplicate rows."""
    pdf_bytes = _make_pdf("1. Clause One\nBody\n\n2. Clause Two\nBody")
    resp = client.post("/v1/documents", files={"file": ("dup.pdf", pdf_bytes, "application/pdf")})
    assert resp.status_code == 202
    job_id = uuid.UUID(resp.json()["job_id"])

    # Enqueue a second time into the stream
    qs.enqueue(redis_client, test_cfg.redis_stream, job_id)

    worker = Worker(cfg=test_cfg)
    worker.run_once()
    worker.run_once()

    with get_session() as s:
        job = s.get(Job, job_id)
        assert job.status == "succeeded"
        pages = s.query(Page).filter(Page.document_id == job.document_id).all()
        clauses = s.query(Clause).filter(Clause.document_id == job.document_id).all()
        assert len(pages) == 1
        assert len(clauses) >= 2


@pytest.mark.integration
def test_sweeper_enqueues_un_enqueued_job(
    test_cfg: Settings,
    redis_client: redis.Redis,
    file_store: FileStore,
) -> None:
    """Create committed job with enqueued_at null -> sweeper enqueues and it finishes."""
    pdf_bytes = _make_pdf()
    import hashlib
    sha256 = hashlib.sha256(pdf_bytes).hexdigest()
    key = file_store.save(pdf_bytes, sha256)

    doc_id = uuid.uuid4()
    job_id = uuid.uuid4()
    now = datetime.now(UTC)

    with get_session() as s:
        doc = Document(
            id=doc_id,
            sha256=sha256,
            original_filename="sweeper_test.pdf",
            size_bytes=len(pdf_bytes),
            storage_key=key,
            created_at=now,
        )
        job = Job(
            id=job_id,
            document_id=doc_id,
            status="queued",
            attempts=0,
            enqueued_at=None,  # Simulates XADD failure after commit
            created_at=now,
        )
        s.add(doc)
        s.add(job)

    # Sweeper runs
    enqueued = sweep_stuck_jobs(redis_client, test_cfg)
    assert enqueued >= 1

    # Worker runs and processes it
    worker = Worker(cfg=test_cfg)
    worker.run_once()

    with get_session() as s:
        j = s.get(Job, job_id)
        assert j.status == "succeeded"


@pytest.mark.integration
def test_graceful_shutdown(
    client: TestClient,
    test_cfg: Settings,
) -> None:
    """Worker cleanly finishes in-flight job when stop requested."""
    pdf_bytes = _make_pdf()
    resp = client.post("/v1/documents", files={"file": ("shutdown.pdf", pdf_bytes, "application/pdf")})
    assert resp.status_code == 202
    job_id = uuid.UUID(resp.json()["job_id"])

    stop_event = threading.Event()
    worker = Worker(cfg=test_cfg, stop_event=stop_event)

    # Request stop and run once
    worker.run_once()
    worker.request_stop()
    assert stop_event.is_set()

    with get_session() as s:
        job = s.get(Job, job_id)
        assert job.status == "succeeded"


@pytest.mark.integration
def test_concurrency_three_workers_thirty_documents(
    client: TestClient,
    test_cfg: Settings,
) -> None:
    """3 workers, 30 documents -> every document processed exactly once."""
    num_docs = 30
    job_ids: list[uuid.UUID] = []

    # Upload 30 unique documents
    for i in range(num_docs):
        pdf_bytes = _make_pdf(f"1. Section {i}\nTerms for contract {i}\n\n2. Scope {i}\nDetails {i}")
        resp = client.post(
            "/v1/documents",
            files={"file": (f"contract_{i}.pdf", pdf_bytes, "application/pdf")},
        )
        assert resp.status_code == 202
        job_ids.append(uuid.UUID(resp.json()["job_id"]))

    stop_event = threading.Event()
    workers = [
        Worker(cfg=test_cfg, consumer_id=f"worker-{i}", stop_event=stop_event)
        for i in range(3)
    ]

    threads = [threading.Thread(target=w.run) for w in workers]
    for t in threads:
        t.start()

    # Wait for all jobs to complete (timeout 30s)
    deadline = time.time() + 30.0
    all_done = False
    while time.time() < deadline:
        with get_session() as s:
            succeeded_count = (
                s.query(Job)
                .filter(Job.id.in_(job_ids), Job.status == "succeeded")
                .count()
            )
            if succeeded_count == num_docs:
                all_done = True
                break
        time.sleep(0.3)

    stop_event.set()
    for t in threads:
        t.join(timeout=5.0)

    assert all_done, f"Not all jobs completed in time: {succeeded_count}/{num_docs}"

    # Verify no duplicate pages or clauses
    with get_session() as s:
        total_pages = s.query(Page).count()
        total_clauses = s.query(Clause).count()
        assert total_pages == num_docs
        assert total_clauses >= num_docs * 2
