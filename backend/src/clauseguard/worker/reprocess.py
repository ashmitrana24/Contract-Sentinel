"""Idempotent reprocessing CLI and pipeline for ClauseGuard.

Re-runs chosen pipeline stages on stored documents:
    python -m clauseguard.worker.reprocess [--all | --document ID] [--stages parse,forensics,consistency,clauses,summary]

Uses replace semantics:
- Deletes previous stage records before inserting updated ones within atomic transactions.
- Creates new analysis_runs rows.
- Preserves document integrity and foreign keys.
"""

from __future__ import annotations

import argparse
import logging
import sys
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from clauseguard.clauses.attributes import extract_all_document_attributes
from clauseguard.clauses.model import classify_clause
from clauseguard.config import Settings, get_settings
from clauseguard.consistency import ConsistencySettings
from clauseguard.consistency import analyze as analyze_consistency
from clauseguard.db.models import (
    AnalysisRun,
    Clause,
    ClauseLabelRow,
    Document,
    DocumentAttributeRow,
    FindingRow,
    Page,
    RiskSummaryRow,
)
from clauseguard.db.session import get_session
from clauseguard.forensics.models import ForensicsSettings
from clauseguard.forensics.run import analyze as analyze_forensics
from clauseguard.parsing.parse_document import parse_document
from clauseguard.risk.aggregate import summarize
from clauseguard.storage.file_store import FileStore

logger = logging.getLogger("clauseguard.worker.reprocess")

ALL_STAGES = {"parse", "forensics", "consistency", "clauses", "summary"}


def parse_stages_arg(stages_str: str) -> set[str]:
    """Parse and validate comma-separated stages."""
    stages = {s.strip().lower() for s in stages_str.split(",") if s.strip()}
    invalid = stages - ALL_STAGES
    if invalid:
        raise ValueError(f"Invalid stage(s): {', '.join(sorted(invalid))}. Valid stages are: {', '.join(sorted(ALL_STAGES))}")
    if not stages:
        raise ValueError("At least one stage must be specified.")
    return stages


def reprocess_document(
    document_id: uuid.UUID,
    stages: set[str],
    *,
    session: Session,
    store: FileStore,
    cfg: Settings,
) -> dict[str, Any]:
    """Reprocess a single document for the selected stages idempotently."""
    doc = session.get(Document, document_id)
    if doc is None:
        raise ValueError(f"Document {document_id} not found in database.")

    try:
        pdf_bytes = store.read(doc.storage_key)
    except FileNotFoundError as exc:
        raise RuntimeError(f"File not found in storage for key {doc.storage_key}") from exc

    # Parse PDF (always parse to have in-memory representation, but only persist if 'parse' in stages)
    parsed = parse_document(pdf_bytes)

    # 1. PARSE STAGE
    if "parse" in stages:
        session.execute(delete(Page).where(Page.document_id == document_id))
        session.execute(delete(Clause).where(Clause.document_id == document_id))

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

        clause_entities = [
            Clause(
                document_id=document_id,
                order_idx=c.order_idx,
                clause_id=c.clause_id,
                heading=(c.heading or "")[:512],
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

        doc.page_count = parsed.page_count
        doc.pdf_metadata = parsed.pdf_metadata
        doc.needs_ocr = parsed.needs_ocr

    # 2. FORENSICS STAGE
    forensics_report = None
    if "forensics" in stages and cfg.forensics_enabled:
        f_settings = ForensicsSettings(budget_seconds=cfg.forensics_budget_seconds)
        forensics_report = analyze_forensics(pdf_bytes, f_settings)

        session.execute(delete(FindingRow).where(
            (FindingRow.document_id == document_id) & (FindingRow.module == "pdf_forensics")
        ))
        session.execute(delete(AnalysisRun).where(
            (AnalysisRun.document_id == document_id) & (AnalysisRun.module == "pdf_forensics")
        ))

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

    # 3. CONSISTENCY STAGE
    consistency_report = None
    if "consistency" in stages and cfg.consistency_enabled:
        c_settings = ConsistencySettings(budget_seconds=cfg.consistency_budget_seconds)
        c_error = None
        try:
            consistency_report = analyze_consistency(parsed, c_settings)
        except Exception as exc:
            c_error = str(exc)

        session.execute(delete(FindingRow).where(
            (FindingRow.document_id == document_id) & (FindingRow.module == "consistency")
        ))
        session.execute(delete(AnalysisRun).where(
            (AnalysisRun.document_id == document_id) & (AnalysisRun.module == "consistency")
        ))

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
        elif c_error is not None:
            c_run_entity = AnalysisRun(
                document_id=document_id,
                module="consistency",
                version="1.0.0",
                status="error",
                duration_ms=0,
                error=c_error[:2048],
                detector_status={"error": c_error},
            )
            session.add(c_run_entity)

    # 4. CLAUSES STAGE
    clause_label_records: list[dict[str, Any]] = []
    doc_attributes = None
    if "clauses" in stages and cfg.clauses_enabled:
        session.execute(delete(ClauseLabelRow).where(ClauseLabelRow.document_id == document_id))
        session.execute(delete(DocumentAttributeRow).where(DocumentAttributeRow.document_id == document_id))
        session.execute(delete(AnalysisRun).where(
            (AnalysisRun.document_id == document_id) & (AnalysisRun.module == "clauses")
        ))

        start_clauses_t = datetime.now(UTC)
        clauses_error = None
        try:
            clause_labels_list = []
            for c in parsed.clauses:
                preds = classify_clause(c.text, heading=c.heading)
                clause_labels_list.append([p["label"] for p in preds])
                for p in preds:
                    clause_label_records.append({
                        "clause_id": c.clause_id,
                        "label": p["label"],
                        "score": p["score"],
                        "method": p["method"],
                        "evidence": p["evidence"],
                    })

            clause_combined_texts = [
                f"{c.heading}\n{c.text}".strip() if c.heading else c.text
                for c in parsed.clauses
            ]
            doc_attributes = extract_all_document_attributes(
                clause_combined_texts,
                clause_labels=clause_labels_list,
            )
            clauses_duration_ms = round((datetime.now(UTC) - start_clauses_t).total_seconds() * 1000)
        except Exception as exc:
            clauses_error = str(exc)
            clauses_duration_ms = 0

        if clause_label_records:
            lbl_entities = [
                ClauseLabelRow(
                    document_id=document_id,
                    clause_id=r["clause_id"],
                    label=r["label"],
                    score=r["score"],
                    method=r["method"],
                    evidence=r["evidence"],
                )
                for r in clause_label_records
            ]
            session.add_all(lbl_entities)

        if doc_attributes is not None:
            attr_entity = DocumentAttributeRow(
                document_id=document_id,
                governing_law_jurisdiction=doc_attributes.governing_law_jurisdiction,
                termination_notice_days=doc_attributes.termination_notice_days,
                auto_renews=doc_attributes.auto_renews,
                renewal_term_months=doc_attributes.renewal_term_months,
                non_renewal_notice_days=doc_attributes.non_renewal_notice_days,
                liability_cap=doc_attributes.liability_cap,
                limitation_of_liability=doc_attributes.limitation_of_liability,
                non_compete_duration_months=doc_attributes.non_compete_duration_months,
                payment_terms_days=doc_attributes.payment_terms_days,
            )
            session.add(attr_entity)

        cl_run_entity = AnalysisRun(
            document_id=document_id,
            module="clauses",
            version="1.0.0",
            status="ok" if clauses_error is None else "error",
            duration_ms=clauses_duration_ms,
            error=clauses_error[:2048] if clauses_error else None,
            detector_status={
                "labels_count": len(clause_label_records),
                "attributes_extracted": doc_attributes is not None,
            },
        )
        session.add(cl_run_entity)

    # 5. RISK SUMMARY STAGE
    risk_band = None
    risk_score = None
    if "summary" in stages:
        session.execute(delete(RiskSummaryRow).where(RiskSummaryRow.document_id == document_id))

        # Query all active findings from DB
        all_db_findings = session.execute(
            select(FindingRow).where(FindingRow.document_id == document_id)
        ).scalars().all()

        # Query active analysis runs from DB
        db_runs = session.execute(
            select(AnalysisRun).where(AnalysisRun.document_id == document_id)
        ).scalars().all()

        cov_runs = [
            {
                "module": r.module,
                "status": r.status,
                "detector_status": r.detector_status,
            }
            for r in db_runs
        ]

        cov_inputs = {
            "needs_ocr": parsed.needs_ocr,
            "clause_count": len(parsed.clauses),
            "unsegmented": len(parsed.clauses) < 2 or any(c.kind == "unsegmented" for c in parsed.clauses),
            "analysis_runs": cov_runs,
        }

        # Convert FindingRow back to Finding-compatible objects for summarize
        from clauseguard.schemas.findings import Finding, Severity

        raw_findings = [
            Finding(
                module=f.module,
                type=f.type,
                severity=Severity(f.severity),
                page=f.page,
                clause_ref=f.clause_ref,
                bbox=tuple(f.bbox) if f.bbox else None,
                evidence=f.evidence,
                explanation=f.explanation,
                confidence=f.confidence,
                details=f.details,
            )
            for f in all_db_findings
        ]

        risk_res = summarize(raw_findings, cov_inputs, cfg)
        risk_band = risk_res.band
        risk_score = risk_res.score

        session.add(
            RiskSummaryRow(
                document_id=document_id,
                score=risk_res.score,
                band=risk_res.band,
                summary=risk_res.model_dump(mode="json"),
                version=risk_res.version,
            )
        )

    session.flush()

    # Query current clause and label counts
    total_clauses = session.execute(
        select(func.count()).where(Clause.document_id == document_id)
    ).scalar_one()
    total_labels = session.execute(
        select(func.count()).where(ClauseLabelRow.document_id == document_id)
    ).scalar_one()

    return {
        "document_id": str(document_id),
        "stages": sorted(stages),
        "total_clauses": total_clauses,
        "total_labels": total_labels,
        "risk_band": risk_band,
        "risk_score": risk_score,
    }


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

    parser = argparse.ArgumentParser(description="Reprocess stored ClauseGuard documents.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--all", action="store_true", help="Reprocess all stored documents.")
    group.add_argument("--document", type=str, help="Specific document ID to reprocess.")
    parser.add_argument(
        "--stages",
        type=str,
        default="parse,forensics,consistency,clauses,summary",
        help="Comma-separated list of stages (parse,forensics,consistency,clauses,summary).",
    )

    args = parser.parse_args()
    stages = parse_stages_arg(args.stages)
    cfg = get_settings()
    store = FileStore(cfg.storage_dir)

    print(f"=== ClauseGuard Reprocessing CLI ===")
    print(f"Stages: {', '.join(sorted(stages))}")

    with get_session() as session:
        if args.document:
            try:
                doc_uuid = uuid.UUID(args.document)
            except ValueError:
                print(f"Error: Invalid UUID: {args.document}", file=sys.stderr)
                sys.exit(1)
            doc_ids = [doc_uuid]
        else:
            doc_ids = session.execute(select(Document.id).order_by(Document.created_at.asc())).scalars().all()

        total_docs = len(doc_ids)
        print(f"Found {total_docs} document(s) to process.\n")

        results = []
        for idx, doc_id in enumerate(doc_ids, start=1):
            t0 = datetime.now(UTC)
            try:
                res = reprocess_document(doc_id, stages, session=session, store=store, cfg=cfg)
                dur = (datetime.now(UTC) - t0).total_seconds()
                results.append(res)
                print(
                    f"[{idx}/{total_docs}] {doc_id} -> clauses={res['total_clauses']}, "
                    f"labels={res['total_labels']}, risk_band={res['risk_band']} ({dur:.2f}s)"
                )
            except Exception as err:
                dur = (datetime.now(UTC) - t0).total_seconds()
                print(f"[{idx}/{total_docs}] {doc_id} -> FAILED: {err} ({dur:.2f}s)", file=sys.stderr)

    print("\n=== Reprocessing Complete ===")
    print(f"Documents reprocessed: {len(results)}")
    print(f"Total clauses across docs: {sum(r['total_clauses'] for r in results)}")
    print(f"Total clause labels: {sum(r['total_labels'] for r in results)}")


if __name__ == "__main__":
    main()
