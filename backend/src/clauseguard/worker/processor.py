"""Job processor for the ClauseGuard worker.

Processes one job message from the Redis stream:
- Loads the job from Postgres.
- Acquires a lease on the job (or detects it is already processing / done).
- Fetches the PDF bytes from FileStore.
- Runs parse_document(pdf_bytes).
- Persists pages and clauses to Postgres in a single transaction (idempotent: deletes old pages/clauses before insert).
- Distinguishes permanent vs transient failures:
    - Permanent: sets status='dead', error_kind='permanent', writes to dead-letter stream, ACKs message.
    - Transient: increments attempts, computes exponential backoff with jitter, sets status='retry_wait' with next_attempt_at.
      If attempts >= max_attempts, sets status='dead', error_kind='transient_exhausted', dead-letters, ACKs.
- ACKs the message after successful commit or permanent dead-letter.
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, select

from clauseguard.config import Settings, get_settings
from clauseguard.consistency import ConsistencySettings
from clauseguard.consistency import analyze as analyze_consistency
from clauseguard.db.models import AnalysisRun, Clause, Document, FindingRow, Job, Page
from clauseguard.db.session import get_session
from clauseguard.forensics.models import ForensicsSettings
from clauseguard.forensics.run import analyze
from clauseguard.parsing.parse_document import ParseError, parse_document
from clauseguard.queue import backoff as qb
from clauseguard.queue import streams as qs
from clauseguard.storage.file_store import FileStore

logger = logging.getLogger(__name__)


class PermanentError(Exception):
    """Explicit permanent error (do not retry)."""


def process_job_message(
    job_id_raw: str | uuid.UUID,
    entry_id: str,
    redis_client: qs._redis_mod.Redis,  # type: ignore[type-arg]
    *,
    store: FileStore | None = None,
    cfg: Settings | None = None,
) -> bool:
    """Process a single job message from the Redis stream.

    Returns True if job was processed (succeeded, marked dead, or already completed),
    False if job was skipped (e.g. held by another worker).
    """
    if cfg is None:
        cfg = get_settings()
    if store is None:
        store = FileStore(cfg.storage_dir)

    try:
        job_id = uuid.UUID(str(job_id_raw))
    except (ValueError, TypeError) as exc:
        logger.error("Invalid job_id in message %r: %s", job_id_raw, exc)
        qs.ack(redis_client, cfg.redis_stream, cfg.redis_consumer_group, entry_id)
        return True

    now = datetime.now(UTC)
    lease_expires = now + timedelta(seconds=cfg.lease_seconds)

    # 1. Claim the job in Postgres
    with get_session() as session:
        job = session.execute(
            select(Job).where(Job.id == job_id).with_for_update()
        ).scalar_one_or_none()

        if job is None:
            logger.warning("Job %s not found in DB; dropping entry %s", job_id, entry_id)
            qs.ack(redis_client, cfg.redis_stream, cfg.redis_consumer_group, entry_id)
            return True

        if job.status == "succeeded":
            logger.info("Job %s already succeeded; ACKing duplicate entry %s", job_id, entry_id)
            qs.ack(redis_client, cfg.redis_stream, cfg.redis_consumer_group, entry_id)
            return True

        if job.status == "dead":
            logger.info("Job %s is already dead; ACKing entry %s", job_id, entry_id)
            qs.ack(redis_client, cfg.redis_stream, cfg.redis_consumer_group, entry_id)
            return True

        if job.status == "processing":
            if job.lease_expires_at is not None and job.lease_expires_at > now:
                logger.info(
                    "Job %s is currently leased to another worker until %s; skipping",
                    job_id,
                    job.lease_expires_at,
                )
                return False
            logger.warning(
                "Job %s had an expired lease (expired at %s); reclaiming for crash recovery",
                job_id,
                job.lease_expires_at,
            )

        # Claim the lease and increment attempt count
        job.status = "processing"
        job.attempts += 1
        job.lease_expires_at = lease_expires
        if job.started_at is None:
            job.started_at = now
        session.flush()

        document_id = job.document_id
        attempts = job.attempts
        max_attempts = job.max_attempts

    # 2. Execute processing outside the lease-claiming transaction
    try:
        _execute_parsing(document_id, job_id, store, cfg)
    except (ParseError, PermanentError) as exc:
        logger.error("Permanent failure processing job %s: %s", job_id, exc)
        _mark_dead_permanent(job_id, str(exc), redis_client, entry_id, cfg)
        return True
    except Exception as exc:
        logger.warning(
            "Transient failure processing job %s (attempt %d/%d): %s",
            job_id,
            attempts,
            max_attempts,
            exc,
            exc_info=True,
        )
        _handle_transient_failure(job_id, str(exc), attempts, max_attempts, redis_client, entry_id, cfg)
        return True

    # 3. Successful completion -> mark succeeded and ACK
    now_done = datetime.now(UTC)
    with get_session() as session:
        j = session.get(Job, job_id)
        if j:
            j.status = "succeeded"
            j.finished_at = now_done
            j.last_error = None
            j.error_kind = None
            j.lease_expires_at = None

    qs.ack(redis_client, cfg.redis_stream, cfg.redis_consumer_group, entry_id)
    logger.info("Job %s completed successfully", job_id)
    return True


def _execute_parsing(
    document_id: uuid.UUID,
    job_id: uuid.UUID,
    store: FileStore,
    cfg: Settings,
) -> None:
    """Read document, parse PDF, and write pages/clauses atomically."""
    with get_session() as session:
        doc = session.get(Document, document_id)
        if doc is None:
            raise PermanentError(f"Document {document_id} not found in DB")
        storage_key = doc.storage_key

    try:
        pdf_bytes = store.read(storage_key)
    except FileNotFoundError as exc:
        raise PermanentError(f"File not found in storage: {storage_key}") from exc

    # Pure parsing
    parsed = parse_document(pdf_bytes)

    if parsed.page_count > cfg.max_pages:
        raise ParseError(f"PDF page count {parsed.page_count} exceeds limit {cfg.max_pages}")

    # Structure forensics (Module 3)
    forensics_report = None
    if cfg.forensics_enabled:
        try:
            f_settings = ForensicsSettings(budget_seconds=cfg.forensics_budget_seconds)
            forensics_report = analyze(pdf_bytes, f_settings)
        except Exception as exc:
            logger.warning("Forensics analysis failed on document %s: %s", document_id, exc)

    # Consistency checks (Module 4)
    consistency_report = None
    consistency_error = None
    if cfg.consistency_enabled:
        try:
            c_settings = ConsistencySettings(budget_seconds=cfg.consistency_budget_seconds)
            consistency_report = analyze_consistency(parsed, c_settings)
        except Exception as exc:
            logger.warning("Consistency analysis failed on document %s: %s", document_id, exc)
            consistency_error = str(exc)

    # Idempotent write: atomic replace in single transaction
    with get_session() as session:
        # Delete existing pages, clauses, findings, and analysis_runs (handles re-parse cleanly)
        session.execute(delete(Page).where(Page.document_id == document_id))
        session.execute(delete(Clause).where(Clause.document_id == document_id))
        session.execute(delete(FindingRow).where(FindingRow.document_id == document_id))
        session.execute(delete(AnalysisRun).where(AnalysisRun.document_id == document_id))

        # Insert pages
        page_entities = [
            Page(
                document_id=document_id,
                page_no=p.page_no,
                width=p.width,
                height=p.height,
                text=p.text,
                char_count=p.char_count,
                spans=[s.model_dump() for s in p.spans],
            )
            for p in parsed.pages
        ]
        session.add_all(page_entities)

        # Insert clauses
        clause_entities = [
            Clause(
                document_id=document_id,
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
            for c in parsed.clauses
        ]
        session.add_all(clause_entities)

        # Insert forensics findings and analysis run
        if forensics_report is not None:
            finding_entities = [
                FindingRow(
                    document_id=document_id,
                    module=f.module,
                    type=f.type,
                    severity=f.severity.value if hasattr(f.severity, "value") else str(f.severity),
                    page=f.page,
                    clause_ref=f.clause_ref,
                    bbox=list(f.bbox) if f.bbox else None,
                    evidence=f.evidence,
                    explanation=f.explanation,
                    confidence=f.confidence,
                    details=f.details,
                )
                for f in forensics_report.findings
            ]
            session.add_all(finding_entities)

            run_entity = AnalysisRun(
                document_id=document_id,
                module="pdf_forensics",
                version=forensics_report.version,
                status=forensics_report.status,
                duration_ms=round(forensics_report.total_duration_ms),
                detector_status={"detectors": [d.model_dump() for d in forensics_report.detectors]},
            )
            session.add(run_entity)

        # Insert consistency findings and analysis run
        if consistency_report is not None:
            c_finding_entities = [
                FindingRow(
                    document_id=document_id,
                    module=f.module,
                    type=f.type,
                    severity=f.severity.value if hasattr(f.severity, "value") else str(f.severity),
                    page=f.page,
                    clause_ref=f.clause_ref,
                    bbox=list(f.bbox) if f.bbox else None,
                    evidence=f.evidence,
                    explanation=f.explanation,
                    confidence=f.confidence,
                    details=f.details,
                )
                for f in consistency_report.findings
            ]
            session.add_all(c_finding_entities)

            c_run_entity = AnalysisRun(
                document_id=document_id,
                module="consistency",
                version=consistency_report.version,
                status=consistency_report.status,
                duration_ms=round(consistency_report.total_duration_ms),
                detector_status={
                    "detectors": [d.model_dump() for d in consistency_report.detectors],
                    "stats": consistency_report.stats,
                },
            )
            session.add(c_run_entity)
        elif consistency_error is not None:
            c_run_entity = AnalysisRun(
                document_id=document_id,
                module="consistency",
                version="1.0.0",
                status="error",
                duration_ms=0,
                error=consistency_error[:2048],
                detector_status={"error": consistency_error},
            )
            session.add(c_run_entity)

        # Update document metadata and OCR flag
        d = session.get(Document, document_id)
        if d:
            d.page_count = parsed.page_count
            d.pdf_metadata = parsed.pdf_metadata
            d.needs_ocr = parsed.needs_ocr


def _mark_dead_permanent(
    job_id: uuid.UUID,
    reason: str,
    redis_client: qs._redis_mod.Redis,  # type: ignore[type-arg]
    entry_id: str,
    cfg: Settings,
) -> None:
    now = datetime.now(UTC)
    with get_session() as session:
        j = session.get(Job, job_id)
        if j:
            j.status = "dead"
            j.error_kind = "permanent"
            j.last_error = reason[:2048]
            j.finished_at = now
            j.lease_expires_at = None

    try:
        qs.enqueue_dead(
            redis_client,
            cfg.redis_dead_stream,
            job_id,
            reason=reason,
            error_kind="permanent",
        )
    except Exception as e:
        logger.error("Failed to enqueue dead letter for job %s: %s", job_id, e)

    qs.ack(redis_client, cfg.redis_stream, cfg.redis_consumer_group, entry_id)


def _handle_transient_failure(
    job_id: uuid.UUID,
    reason: str,
    attempts: int,
    max_attempts: int,
    redis_client: qs._redis_mod.Redis,  # type: ignore[type-arg]
    entry_id: str,
    cfg: Settings,
) -> None:
    now = datetime.now(UTC)
    if attempts >= max_attempts:
        # Retries exhausted -> mark dead
        with get_session() as session:
            j = session.get(Job, job_id)
            if j:
                j.status = "dead"
                j.error_kind = "transient_exhausted"
                j.last_error = reason[:2048]
                j.finished_at = now
                j.lease_expires_at = None

        try:
            qs.enqueue_dead(
                redis_client,
                cfg.redis_dead_stream,
                job_id,
                reason=reason,
                error_kind="transient_exhausted",
            )
        except Exception as e:
            logger.error("Failed to enqueue dead letter for job %s: %s", job_id, e)

        qs.ack(redis_client, cfg.redis_stream, cfg.redis_consumer_group, entry_id)
    else:
        # Schedule retry with backoff + jitter
        delay = qb.compute_backoff(
            attempts,
            base=cfg.backoff_base_seconds,
            cap=cfg.backoff_cap_seconds,
        )
        next_attempt = now + timedelta(seconds=delay)
        with get_session() as session:
            j = session.get(Job, job_id)
            if j:
                j.status = "retry_wait"
                j.next_attempt_at = next_attempt
                j.last_error = reason[:2048]
                j.lease_expires_at = None

        # ACK old stream entry; the sweeper / retry loop will re-enqueue when next_attempt_at arrives
        qs.ack(redis_client, cfg.redis_stream, cfg.redis_consumer_group, entry_id)
        logger.info(
            "Job %s will retry in %.2fs (at %s)",
            job_id,
            delay,
            next_attempt.isoformat(),
        )
