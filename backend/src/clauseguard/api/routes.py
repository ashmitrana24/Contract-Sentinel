"""API route handlers.

POST /v1/documents        – upload PDF
GET  /v1/jobs/{job_id}    – job status
GET  /v1/documents/{id}   – document metadata + job status + clause count
GET  /v1/documents/{id}/pages   – paginated pages
GET  /v1/documents/{id}/clauses – paginated clauses
GET  /healthz             – postgres + redis health
"""

from __future__ import annotations

import hashlib
import io
import logging
import uuid
from datetime import UTC, datetime
from typing import Annotated

import pymupdf
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import JSONResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from clauseguard.api.deps import get_cfg, get_db, get_store
from clauseguard.config import Settings
from clauseguard.db.models import AnalysisRun, Clause, Document, FindingRow, Job, Page
from clauseguard.db.session import check_connection as pg_check
from clauseguard.queue import streams as qs
from clauseguard.schemas.api import (
    AnalysisRunResponse,
    ClauseResponse,
    DocumentResponse,
    ErrorResponse,
    FindingResponse,
    HealthResponse,
    JobStatusResponse,
    PageResponse,
    PaginatedClauses,
    PaginatedFindings,
    PaginatedPages,
    UploadResponse,
)
from clauseguard.storage.file_store import FileStore

logger = logging.getLogger(__name__)
router = APIRouter()


def _err(code: str, detail: str, status: int) -> JSONResponse:
    return JSONResponse(
        status_code=status,
        content=ErrorResponse(error=code, detail=detail).model_dump(),
    )


# ---------------------------------------------------------------------------
# POST /v1/documents
# ---------------------------------------------------------------------------


@router.post(
    "/v1/documents",
    response_model=UploadResponse,
    status_code=202,
)
async def upload_document(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    store: FileStore = Depends(get_store),
    cfg: Settings = Depends(get_cfg),
) -> JSONResponse:
    """Upload a PDF.  Returns 202 (new) or 200 (duplicate)."""
    # --- Stream + validate without loading unbounded into memory ---
    max_bytes = cfg.max_upload_bytes
    buf = io.BytesIO()
    total = 0
    first_chunk = True
    pdf_header_ok = False

    while True:
        chunk = await file.read(65536)
        if not chunk:
            break
        total += len(chunk)
        if total > max_bytes:
            return _err("file_too_large", f"File exceeds {max_bytes} bytes", 413)
        if first_chunk:
            # Check PDF magic bytes in first 1024 bytes
            peek = chunk[:1024]
            if b"%PDF-" not in peek:
                return _err("not_a_pdf", "File does not have a PDF header", 400)
            pdf_header_ok = True
            first_chunk = False
        buf.write(chunk)

    if total == 0:
        return _err("empty_file", "Uploaded file is empty", 400)
    if not pdf_header_ok:
        return _err("not_a_pdf", "File does not have a PDF header", 400)

    pdf_bytes = buf.getvalue()

    # --- PyMuPDF validation ---
    try:
        doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    except Exception as exc:
        return _err("invalid_pdf", f"Cannot open PDF: {exc}", 422)

    try:
        if doc.is_encrypted:
            if doc.authenticate("") == 0:
                return _err("encrypted_pdf", "PDF requires a password", 422)

        page_count = doc.page_count
        if page_count > cfg.max_pages:
            return _err(
                "too_many_pages",
                f"PDF has {page_count} pages; max is {cfg.max_pages}",
                422,
            )
    finally:
        if not doc.is_closed:
            doc.close()

    # --- SHA-256 deduplication ---
    sha256 = hashlib.sha256(pdf_bytes).hexdigest()

    existing_doc = db.execute(
        select(Document).where(Document.sha256 == sha256)
    ).scalar_one_or_none()

    if existing_doc is not None:
        # Return latest job for this document
        latest_job = db.execute(
            select(Job)
            .where(Job.document_id == existing_doc.id)
            .order_by(Job.created_at.desc())
        ).scalar_one_or_none()
        return JSONResponse(
            status_code=200,
            content=UploadResponse(
                document_id=existing_doc.id,
                job_id=latest_job.id if latest_job else uuid.uuid4(),
                deduplicated=True,
            ).model_dump(mode="json"),
        )

    # --- Store file and create DB records in ONE transaction ---
    storage_key = store.save(pdf_bytes, sha256)

    new_doc = Document(
        id=uuid.uuid4(),
        sha256=sha256,
        original_filename=file.filename or "upload.pdf",
        size_bytes=total,
        storage_key=storage_key,
        page_count=None,
        needs_ocr=False,
        created_at=datetime.now(UTC),
    )
    new_job = Job(
        id=uuid.uuid4(),
        document_id=new_doc.id,
        status="queued",
        attempts=0,
        max_attempts=cfg.max_attempts,
        created_at=datetime.now(UTC),
    )
    db.add(new_doc)
    db.add(new_job)
    db.flush()  # Get IDs assigned

    job_id = new_job.id
    doc_id = new_doc.id
    # Commit happens when dependency exits; we need it committed before XADD
    db.commit()

    # --- XADD to Redis stream (best effort; sweeper recovers failures) ---
    try:
        redis_client = qs._make_client(cfg.redis_url)
        qs.ensure_consumer_group(redis_client, cfg.redis_stream, cfg.redis_consumer_group)
        entry_id = qs.enqueue(redis_client, cfg.redis_stream, job_id)
        # Update enqueued_at
        now = datetime.now(UTC)
        db.execute(
            Job.__table__.update()
            .where(Job.__table__.c.id == job_id)
            .values(enqueued_at=now)
        )
        db.commit()
        logger.info("Job %s enqueued as stream entry %s", job_id, entry_id)
    except Exception as exc:
        # XADD failed – sweeper will re-enqueue
        logger.error("XADD failed for job %s: %s (sweeper will recover)", job_id, exc)

    return JSONResponse(
        status_code=202,
        content=UploadResponse(
            document_id=doc_id,
            job_id=job_id,
            deduplicated=False,
        ).model_dump(mode="json"),
    )


# ---------------------------------------------------------------------------
# GET /v1/jobs/{job_id}
# ---------------------------------------------------------------------------


@router.get("/v1/jobs/{job_id}", response_model=JobStatusResponse)
def get_job(
    job_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> JobStatusResponse:
    job = db.execute(select(Job).where(Job.id == job_id)).scalar_one_or_none()
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return JobStatusResponse(
        job_id=job.id,
        document_id=job.document_id,
        status=job.status,
        attempts=job.attempts,
        max_attempts=job.max_attempts,
        last_error=job.last_error,
        error_kind=job.error_kind,
        enqueued_at=job.enqueued_at.isoformat() if job.enqueued_at else None,
        started_at=job.started_at.isoformat() if job.started_at else None,
        finished_at=job.finished_at.isoformat() if job.finished_at else None,
        next_attempt_at=job.next_attempt_at.isoformat() if job.next_attempt_at else None,
    )


# ---------------------------------------------------------------------------
# GET /v1/documents/{document_id}
# ---------------------------------------------------------------------------


@router.get("/v1/documents/{document_id}", response_model=DocumentResponse)
def get_document(
    document_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> DocumentResponse:
    doc = db.execute(select(Document).where(Document.id == document_id)).scalar_one_or_none()
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found")

    latest_job = db.execute(
        select(Job)
        .where(Job.document_id == document_id)
        .order_by(Job.created_at.desc())
    ).scalar_one_or_none()

    clause_count = db.execute(
        select(func.count()).where(Clause.document_id == document_id)
    ).scalar_one()

    finding_count = db.execute(
        select(func.count()).where(FindingRow.document_id == document_id)
    ).scalar_one()

    return DocumentResponse(
        document_id=doc.id,
        sha256=doc.sha256,
        original_filename=doc.original_filename,
        size_bytes=doc.size_bytes,
        storage_key=doc.storage_key,
        page_count=doc.page_count,
        needs_ocr=doc.needs_ocr,
        pdf_metadata=doc.pdf_metadata,
        created_at=doc.created_at.isoformat(),
        latest_job_id=latest_job.id if latest_job else None,
        latest_job_status=latest_job.status if latest_job else None,
        clause_count=clause_count,
        finding_count=finding_count,
    )


# ---------------------------------------------------------------------------
# GET /v1/documents/{document_id}/findings
# ---------------------------------------------------------------------------


@router.get("/v1/documents/{document_id}/findings", response_model=PaginatedFindings)
def get_findings(
    document_id: uuid.UUID,
    db: Session = Depends(get_db),
    severity: str | None = Query(None, description="Filter by severity: low|medium|high|critical"),
    module: str | None = Query(None, description="Filter by module: pdf_forensics"),
    limit: Annotated[int, Query(ge=1, le=500)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> PaginatedFindings:
    _assert_doc_exists(db, document_id)

    query = select(FindingRow).where(FindingRow.document_id == document_id)
    count_query = select(func.count()).where(FindingRow.document_id == document_id)

    if severity:
        query = query.where(FindingRow.severity == severity.lower())
        count_query = count_query.where(FindingRow.severity == severity.lower())
    if module:
        query = query.where(FindingRow.module == module)
        count_query = count_query.where(FindingRow.module == module)

    total = db.execute(count_query).scalar_one()
    rows = (
        db.execute(
            query.order_by(FindingRow.created_at, FindingRow.id)
            .limit(limit)
            .offset(offset)
        )
        .scalars()
        .all()
    )

    return PaginatedFindings(
        total=total,
        limit=limit,
        offset=offset,
        items=[
            FindingResponse(
                id=f.id,
                document_id=f.document_id,
                module=f.module,
                type=f.type,
                severity=f.severity,
                page=f.page,
                clause_ref=f.clause_ref,
                bbox=list(f.bbox) if f.bbox else None,
                evidence=f.evidence,
                explanation=f.explanation,
                confidence=f.confidence,
                details=f.details or {},
                created_at=f.created_at.isoformat(),
            )
            for f in rows
        ],
    )


# ---------------------------------------------------------------------------
# GET /v1/documents/{document_id}/analysis
# ---------------------------------------------------------------------------


@router.get("/v1/documents/{document_id}/analysis", response_model=list[AnalysisRunResponse])
def get_analysis_runs(
    document_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> list[AnalysisRunResponse]:
    _assert_doc_exists(db, document_id)
    rows = (
        db.execute(
            select(AnalysisRun)
            .where(AnalysisRun.document_id == document_id)
            .order_by(AnalysisRun.created_at.desc())
        )
        .scalars()
        .all()
    )
    return [
        AnalysisRunResponse(
            id=r.id,
            document_id=r.document_id,
            module=r.module,
            version=r.version,
            status=r.status,
            duration_ms=r.duration_ms,
            error=r.error,
            detector_status=r.detector_status or {},
            created_at=r.created_at.isoformat(),
        )
        for r in rows
    ]


# ---------------------------------------------------------------------------
# GET /v1/documents/{document_id}/pages
# ---------------------------------------------------------------------------


@router.get("/v1/documents/{document_id}/pages", response_model=PaginatedPages)
def get_pages(
    document_id: uuid.UUID,
    db: Session = Depends(get_db),
    limit: Annotated[int, Query(ge=1, le=200)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> PaginatedPages:
    _assert_doc_exists(db, document_id)
    total = db.execute(
        select(func.count()).where(Page.document_id == document_id)
    ).scalar_one()
    rows = db.execute(
        select(Page)
        .where(Page.document_id == document_id)
        .order_by(Page.page_no)
        .limit(limit)
        .offset(offset)
    ).scalars().all()
    return PaginatedPages(
        total=total,
        limit=limit,
        offset=offset,
        items=[
            PageResponse(
                page_no=p.page_no,
                width=p.width,
                height=p.height,
                text=p.text,
                char_count=p.char_count,
                spans=p.spans or [],
            )
            for p in rows
        ],
    )


# ---------------------------------------------------------------------------
# GET /v1/documents/{document_id}/clauses
# ---------------------------------------------------------------------------


@router.get("/v1/documents/{document_id}/clauses", response_model=PaginatedClauses)
def get_clauses(
    document_id: uuid.UUID,
    db: Session = Depends(get_db),
    limit: Annotated[int, Query(ge=1, le=500)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> PaginatedClauses:
    _assert_doc_exists(db, document_id)
    total = db.execute(
        select(func.count()).where(Clause.document_id == document_id)
    ).scalar_one()
    rows = db.execute(
        select(Clause)
        .where(Clause.document_id == document_id)
        .order_by(Clause.order_idx)
        .limit(limit)
        .offset(offset)
    ).scalars().all()
    return PaginatedClauses(
        total=total,
        limit=limit,
        offset=offset,
        items=[
            ClauseResponse(
                order_idx=c.order_idx,
                clause_id=c.clause_id,
                heading=c.heading,
                text=c.text,
                level=c.level,
                parent_clause_id=c.parent_clause_id,
                page_start=c.page_start,
                page_end=c.page_end,
                kind=c.kind,
            )
            for c in rows
        ],
    )


# ---------------------------------------------------------------------------
# GET /healthz
# ---------------------------------------------------------------------------


@router.get("/healthz", response_model=HealthResponse)
def healthz(cfg: Settings = Depends(get_cfg)) -> JSONResponse:
    pg_ok = pg_check()
    redis_ok = qs.check_connection(cfg.redis_url)

    status = "ok" if (pg_ok and redis_ok) else "degraded"
    http_code = 200 if (pg_ok and redis_ok) else 503

    return JSONResponse(
        status_code=http_code,
        content=HealthResponse(
            status=status,
            postgres="ok" if pg_ok else "unreachable",
            redis="ok" if redis_ok else "unreachable",
        ).model_dump(),
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _assert_doc_exists(db: Session, document_id: uuid.UUID) -> None:
    exists = db.execute(
        select(Document.id).where(Document.id == document_id)
    ).scalar_one_or_none()
    if exists is None:
        raise HTTPException(status_code=404, detail="Document not found")
