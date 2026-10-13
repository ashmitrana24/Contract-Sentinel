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
from typing import Annotated, Any

import pymupdf
from fastapi import APIRouter, Depends, File, HTTPException, Query, Response, UploadFile
from fastapi.responses import JSONResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from clauseguard.api.deps import get_cfg, get_db, get_store
from clauseguard.clauses.taxonomy import get_label_definition
from clauseguard.config import Settings
from clauseguard.db.models import (
    AnalysisRun,
    Clause,
    ClauseLabelRow,
    Document,
    DocumentAttributeRow,
    FindingFeedbackRow,
    FindingRow,
    Job,
    Page,
    RiskSummaryRow,
)
from clauseguard.db.session import check_connection as pg_check
from clauseguard.queue import streams as qs
from clauseguard.risk.aggregate import RiskSummary, summarize
from clauseguard.risk.catalog import get_catalog, get_finding_type_info
from clauseguard.risk.highlights import compute_highlights
from clauseguard.schemas.api import (
    AnalysisRunResponse,
    ClauseLabelItem,
    ClauseResponse,
    ClauseTypesResponse,
    ClauseTypeSummaryItem,
    DocumentAttributesResponse,
    DocumentListItem,
    DocumentResponse,
    DocumentRiskSummaryBrief,
    ErrorResponse,
    FindingFeedbackItem,
    FindingFeedbackRequest,
    FindingHighlightItem,
    FindingResponse,
    FindingTypeListResponse,
    HealthResponse,
    JobStageItem,
    JobStatusResponse,
    PageResponse,
    PaginatedClauses,
    PaginatedDocumentsResponse,
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
# Helpers for Risk and Stages
# ---------------------------------------------------------------------------


def _compute_job_stages(job: Job, db: Session) -> list[JobStageItem]:
    stages: list[JobStageItem] = []
    # 1. upload
    stages.append(JobStageItem(key="upload", label="Upload", status="done"))

    # 2. parse
    page_count = db.execute(
        select(func.count()).where(Page.document_id == job.document_id)
    ).scalar_one()
    if page_count > 0:
        parse_status = "done"
    elif job.status == "processing":
        parse_status = "running"
    elif job.status == "dead":
        parse_status = "error"
    else:
        parse_status = "pending"
    stages.append(JobStageItem(key="parse", label="Document Parsing", status=parse_status))

    # Fetch runs
    runs = {
        r.module: r
        for r in db.execute(
            select(AnalysisRun).where(AnalysisRun.document_id == job.document_id)
        ).scalars().all()
    }

    def _module_status(mod: str) -> str:
        if mod in runs:
            r = runs[mod]
            if r.status in ("ok", "partial"):
                return "done"
            if r.status == "error":
                return "error"
            return "done"
        if job.status == "succeeded":
            return "skipped"
        if job.status == "processing" and parse_status == "done":
            return "running"
        if job.status == "dead":
            return "skipped"
        return "pending"

    # 3. forensics
    stages.append(JobStageItem(key="forensics", label="PDF Forensics", status=_module_status("pdf_forensics")))
    # 4. consistency
    stages.append(JobStageItem(key="consistency", label="Consistency Checks", status=_module_status("consistency")))
    # 5. clauses
    stages.append(JobStageItem(key="clauses", label="Clause Classification", status=_module_status("clauses")))

    # 6. summary
    has_risk = db.execute(
        select(RiskSummaryRow.document_id).where(RiskSummaryRow.document_id == job.document_id)
    ).scalar_one_or_none() is not None
    if has_risk or job.status == "succeeded":
        sum_status = "done"
    elif job.status == "processing" and _module_status("clauses") in ("done", "skipped"):
        sum_status = "running"
    elif job.status == "dead":
        sum_status = "skipped"
    else:
        sum_status = "pending"
    stages.append(JobStageItem(key="summary", label="Risk Summary", status=sum_status))

    return stages


def _get_or_compute_risk_summary(db: Session, document_id: uuid.UUID, cfg: Settings) -> RiskSummary:
    row = db.execute(
        select(RiskSummaryRow).where(RiskSummaryRow.document_id == document_id)
    ).scalar_one_or_none()

    if row is not None and row.version == cfg.risk_version:
        return RiskSummary.model_validate(row.summary)

    doc = db.get(Document, document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    findings = db.execute(
        select(FindingRow).where(FindingRow.document_id == document_id)
    ).scalars().all()

    runs = db.execute(
        select(AnalysisRun).where(AnalysisRun.document_id == document_id)
    ).scalars().all()

    clause_count = db.execute(
        select(func.count()).where(Clause.document_id == document_id)
    ).scalar_one()

    unsegmented_count = db.execute(
        select(func.count()).where(Clause.document_id == document_id, Clause.kind == "unsegmented")
    ).scalar_one()

    cov_runs = [
        {
            "module": r.module,
            "status": r.status,
            "error": r.error,
            "detector_status": r.detector_status or {},
        }
        for r in runs
    ]

    cov_inputs = {
        "needs_ocr": doc.needs_ocr,
        "clause_count": clause_count,
        "unsegmented": clause_count < 2 or unsegmented_count > 0,
        "analysis_runs": cov_runs,
    }

    summary = summarize(findings, cov_inputs, cfg)

    if row is not None:
        row.score = summary.score
        row.band = summary.band
        row.summary = summary.model_dump(mode="json")
        row.version = summary.version
    else:
        new_row = RiskSummaryRow(
            document_id=document_id,
            score=summary.score,
            band=summary.band,
            summary=summary.model_dump(mode="json"),
            version=summary.version,
        )
        db.add(new_row)
    db.commit()

    return summary


# ---------------------------------------------------------------------------
# GET /v1/finding-types
# ---------------------------------------------------------------------------


@router.get("/v1/finding-types", response_model=FindingTypeListResponse)
def list_finding_types() -> FindingTypeListResponse:
    catalog = get_catalog()
    return FindingTypeListResponse(items=list(catalog.values()))


# ---------------------------------------------------------------------------
# GET /v1/documents
# ---------------------------------------------------------------------------


@router.get("/v1/documents", response_model=PaginatedDocumentsResponse)
def list_documents(
    limit: Annotated[int, Query(ge=1, le=200)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
    status: str | None = Query(None, description="Filter by latest job status"),
    db: Session = Depends(get_db),
    cfg: Settings = Depends(get_cfg),
) -> PaginatedDocumentsResponse:
    all_docs = db.execute(
        select(Document).order_by(Document.created_at.desc())
    ).scalars().all()

    filtered_docs = []
    doc_job_map: dict[uuid.UUID, tuple[Job | None, str]] = {}
    for d in all_docs:
        latest_job = db.execute(
            select(Job).where(Job.document_id == d.id).order_by(Job.created_at.desc())
        ).scalar_one_or_none()
        j_status = latest_job.status if latest_job else "queued"
        doc_job_map[d.id] = (latest_job, j_status)
        if status is None or j_status == status.lower():
            filtered_docs.append(d)

    total = len(filtered_docs)
    page_docs = filtered_docs[offset : offset + limit]

    items = []
    for d in page_docs:
        latest_job, j_status = doc_job_map[d.id]

        risk_brief = None
        r_row = db.execute(
            select(RiskSummaryRow).where(RiskSummaryRow.document_id == d.id)
        ).scalar_one_or_none()
        if r_row is not None:
            risk_brief = DocumentRiskSummaryBrief(score=r_row.score, band=r_row.band)
        elif j_status == "succeeded":
            r_sum = _get_or_compute_risk_summary(db, d.id, cfg)
            risk_brief = DocumentRiskSummaryBrief(score=r_sum.score, band=r_sum.band)

        sev_counts_res = db.execute(
            select(FindingRow.severity, func.count())
            .where(FindingRow.document_id == d.id)
            .group_by(FindingRow.severity)
        ).all()
        sev_counts = {str(s).lower(): int(c) for s, c in sev_counts_res}

        items.append(
            DocumentListItem(
                id=d.id,
                filename=d.original_filename,
                size=d.size_bytes,
                uploaded_at=d.created_at.isoformat(),
                status=j_status,
                page_count=d.page_count,
                risk=risk_brief,
                finding_counts_by_severity=sev_counts,
            )
        )

    return PaginatedDocumentsResponse(
        total=total,
        limit=limit,
        offset=offset,
        items=items,
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

    stages = _compute_job_stages(job, db)
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
        stages=stages,
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

    module_counts_res = db.execute(
        select(FindingRow.module, func.count())
        .where(FindingRow.document_id == document_id)
        .group_by(FindingRow.module)
    ).all()
    finding_counts_by_module = {str(m): int(c) for m, c in module_counts_res}

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
        finding_counts_by_module=finding_counts_by_module,
    )


# ---------------------------------------------------------------------------
# GET /v1/documents/{document_id}/risk
# ---------------------------------------------------------------------------


@router.get("/v1/documents/{document_id}/risk", response_model=RiskSummary)
def get_document_risk(
    document_id: uuid.UUID,
    db: Session = Depends(get_db),
    cfg: Settings = Depends(get_cfg),
) -> RiskSummary:
    _assert_doc_exists(db, document_id)
    return _get_or_compute_risk_summary(db, document_id, cfg)


# ---------------------------------------------------------------------------
# GET /v1/documents/{document_id}/file
# ---------------------------------------------------------------------------


@router.get("/v1/documents/{document_id}/file")
def get_document_file(
    document_id: uuid.UUID,
    db: Session = Depends(get_db),
    store: FileStore = Depends(get_store),
) -> Response:
    doc = db.get(Document, document_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found")

    try:
        pdf_bytes = store.read(doc.storage_key)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Stored PDF file not found") from None

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'inline; filename="{doc.original_filename}"',
            "Cache-Control": "private, max-age=3600",
        },
    )


# ---------------------------------------------------------------------------
# DELETE /v1/documents/{document_id}
# ---------------------------------------------------------------------------


@router.delete("/v1/documents/{document_id}", status_code=204)
def delete_document(
    document_id: uuid.UUID,
    db: Session = Depends(get_db),
    store: FileStore = Depends(get_store),
) -> Response:
    doc = db.get(Document, document_id)
    if doc is not None:
        storage_key = doc.storage_key
        db.delete(doc)
        db.commit()
        store.delete(storage_key)
    return Response(status_code=204)


# ---------------------------------------------------------------------------
# GET /v1/documents/{document_id}/findings
# ---------------------------------------------------------------------------


@router.get("/v1/documents/{document_id}/findings", response_model=PaginatedFindings)
def get_findings(
    document_id: uuid.UUID,
    db: Session = Depends(get_db),
    severity: str | None = Query(None, description="Filter by severity: low|medium|high|critical"),
    module: str | None = Query(None, description="Filter by module: pdf_forensics|consistency"),
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

    pages = db.execute(
        select(Page).where(Page.document_id == document_id).order_by(Page.page_no)
    ).scalars().all()

    clauses = db.execute(
        select(Clause).where(Clause.document_id == document_id).order_by(Clause.order_idx)
    ).scalars().all()

    # Pre-fetch feedbacks for this document
    finding_ids = [f.id for f in rows]
    feedback_map = {}
    if finding_ids:
        fbacks = db.execute(
            select(FindingFeedbackRow).where(FindingFeedbackRow.finding_id.in_(finding_ids))
        ).scalars().all()
        for fb in fbacks:
            feedback_map[fb.finding_id] = FindingFeedbackItem(
                verdict=fb.verdict,
                note=fb.note,
                created_at=fb.created_at.isoformat(),
            )

    items = []
    for f in rows:
        info = get_finding_type_info(f.type, f.module)
        uncertain = bool((f.details or {}).get("uncertain"))
        hl_objs = compute_highlights(f, pages, clauses)
        items.append(
            FindingResponse(
                id=f.id,
                document_id=f.document_id,
                module=f.module,
                type=f.type,
                severity=f.severity,
                category=info.category,
                title=info.title,
                what_it_means=info.what_it_means,
                what_to_check=info.what_to_check,
                uncertain=uncertain,
                feedback=feedback_map.get(f.id),
                highlights=[
                    FindingHighlightItem(
                        page=hl.page,
                        bbox=hl.bbox,
                        page_width=hl.page_width,
                        page_height=hl.page_height,
                        rotation=hl.rotation,
                        approximate=hl.approximate,
                    )
                    for hl in hl_objs
                ],
                page=f.page,
                clause_ref=f.clause_ref,
                bbox=list(f.bbox) if f.bbox else None,
                evidence=f.evidence,
                explanation=f.explanation,
                confidence=f.confidence,
                details=f.details or {},
                created_at=f.created_at.isoformat(),
            )
        )

    return PaginatedFindings(
        total=total,
        limit=limit,
        offset=offset,
        items=items,
    )


# ---------------------------------------------------------------------------
# POST & DELETE /v1/findings/{finding_id}/feedback
# ---------------------------------------------------------------------------


@router.post("/v1/findings/{finding_id}/feedback", response_model=FindingFeedbackItem)
def create_or_update_feedback(
    finding_id: uuid.UUID,
    payload: FindingFeedbackRequest,
    db: Session = Depends(get_db),
) -> FindingFeedbackItem:
    f_row = db.get(FindingRow, finding_id)
    if f_row is None:
        raise HTTPException(status_code=404, detail="Finding not found")

    if payload.verdict not in ("confirmed", "dismissed"):
        raise HTTPException(status_code=422, detail="Verdict must be 'confirmed' or 'dismissed'")

    now = datetime.now(UTC)
    fb = db.get(FindingFeedbackRow, finding_id)
    if fb is not None:
        fb.verdict = payload.verdict
        fb.note = payload.note
        fb.created_at = now
    else:
        fb = FindingFeedbackRow(
            finding_id=finding_id,
            verdict=payload.verdict,
            note=payload.note,
            created_at=now,
        )
        db.add(fb)
    db.commit()

    return FindingFeedbackItem(
        verdict=fb.verdict,
        note=fb.note,
        created_at=fb.created_at.isoformat(),
    )


@router.delete("/v1/findings/{finding_id}/feedback", status_code=204)
def delete_feedback(
    finding_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> Response:
    fb = db.get(FindingFeedbackRow, finding_id)
    if fb is not None:
        db.delete(fb)
        db.commit()
    return Response(status_code=204)


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

    # Fetch labels for these clauses
    clause_ids = [c.clause_id for c in rows]
    labels_by_clause: dict[str, list[ClauseLabelItem]] = {}
    if clause_ids:
        label_rows = db.execute(
            select(ClauseLabelRow)
            .where(
                ClauseLabelRow.document_id == document_id,
                ClauseLabelRow.clause_id.in_(clause_ids),
            )
        ).scalars().all()
        for lr in label_rows:
            labels_by_clause.setdefault(lr.clause_id, []).append(
                ClauseLabelItem(
                    label=lr.label,
                    score=lr.score,
                    method=lr.method,
                    evidence=lr.evidence,
                )
            )

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
                labels=labels_by_clause.get(c.clause_id, []),
            )
            for c in rows
        ],
    )


# ---------------------------------------------------------------------------
# GET /v1/documents/{document_id}/clause-types
# ---------------------------------------------------------------------------


@router.get("/v1/documents/{document_id}/clause-types", response_model=ClauseTypesResponse)
def get_clause_types(
    document_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> ClauseTypesResponse:
    _assert_doc_exists(db, document_id)
    labels = db.execute(
        select(ClauseLabelRow)
        .where(ClauseLabelRow.document_id == document_id)
    ).scalars().all()

    grouped: dict[str, dict[str, Any]] = {}
    for lr in labels:
        if lr.label not in grouped:
            defn = get_label_definition(lr.label)
            name = defn.name if defn else lr.label
            grouped[lr.label] = {
                "label": lr.label,
                "name": name,
                "count": 0,
                "max_score": 0.0,
                "clause_ids": set(),
            }
        grouped[lr.label]["count"] += 1
        grouped[lr.label]["max_score"] = max(grouped[lr.label]["max_score"], lr.score)
        grouped[lr.label]["clause_ids"].add(lr.clause_id)

    items = [
        ClauseTypeSummaryItem(
            label=g["label"],
            name=g["name"],
            count=g["count"],
            max_score=round(g["max_score"], 4),
            clause_ids=sorted(g["clause_ids"]),
        )
        for g in grouped.values()
    ]
    items.sort(key=lambda x: (-x.count, x.label))
    return ClauseTypesResponse(
        document_id=document_id,
        total_types=len(items),
        items=items,
    )


# ---------------------------------------------------------------------------
# GET /v1/documents/{document_id}/attributes
# ---------------------------------------------------------------------------


@router.get("/v1/documents/{document_id}/attributes", response_model=DocumentAttributesResponse)
def get_document_attributes(
    document_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> DocumentAttributesResponse:
    _assert_doc_exists(db, document_id)
    attr_row = db.execute(
        select(DocumentAttributeRow)
        .where(DocumentAttributeRow.document_id == document_id)
    ).scalar_one_or_none()

    if attr_row is None:
        return DocumentAttributesResponse(document_id=document_id)

    return DocumentAttributesResponse(
        document_id=document_id,
        governing_law_jurisdiction=attr_row.governing_law_jurisdiction,
        termination_notice_days=attr_row.termination_notice_days,
        auto_renews=attr_row.auto_renews,
        renewal_term_months=attr_row.renewal_term_months,
        non_renewal_notice_days=attr_row.non_renewal_notice_days,
        liability_cap=attr_row.liability_cap,
        non_compete_duration_months=attr_row.non_compete_duration_months,
        payment_terms_days=attr_row.payment_terms_days,
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
