"""Verifier - quality gate for the generated dataset.

For every PDF in the output directory, verifies the label claims
against the actual PDF content using PyMuPDF.

Exit codes:
  0 - all checks passed
  1 - one or more checks failed
"""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path

import pymupdf as fitz  # PyMuPDF

from datagen.models import DocLabel, TamperType

logger = logging.getLogger(__name__)

HIDDEN_TEXT_MARKER = "HIDDEN CLAUSE"


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _extract_text(path: Path) -> str:
    doc = fitz.open(str(path))
    try:
        return "".join(page.get_text() for page in doc)
    finally:
        doc.close()


def _count_eof(path: Path) -> int:
    return path.read_bytes().count(b"%%EOF")


def _check_label(label: DocLabel, pdf_path: Path) -> list[str]:
    """Return list of failure messages for one document (empty = pass)."""
    failures: list[str] = []

    # 1. SHA-256 check
    actual_sha = _sha256_file(pdf_path)
    if actual_sha != label.sha256:
        failures.append(f"sha256 mismatch: expected {label.sha256[:12]}… got {actual_sha[:12]}…")
        return failures  # no point checking further if file is wrong

    # 2. Extractable text check (applies to all)
    try:
        text = _extract_text(pdf_path)
    except Exception as exc:
        failures.append(f"text extraction failed: {exc}")
        return failures

    if len(text.strip()) < 50:
        failures.append("extracted text too short (< 50 chars); PDF may not be text-based.")

    # 3. Clean document checks
    if not label.is_tampered:
        eof_count = _count_eof(pdf_path)
        if eof_count != 1:
            failures.append(f"clean doc has {eof_count} %%EOF markers (expected 1).")
        if HIDDEN_TEXT_MARKER in text:
            failures.append("clean doc contains hidden text marker.")
        return failures

    # 4. Tampered document checks (per tamper type)
    for detail in label.tamper_details:
        tt = detail.tamper_type

        if tt == TamperType.AMOUNT_FIGURE_ONLY:
            if detail.tampered_value and detail.tampered_value not in text:
                failures.append(
                    f"amount_figure_only: tampered figure '{detail.tampered_value}' not in text."
                )
            # Note: we do NOT check original_value absence because the original
            # figure may appear in other clauses that were not tampered.

        elif tt == TamperType.AMOUNT_BOTH:
            if detail.tampered_value:
                # tampered_value is "figure (words)" string
                # check the figure part at minimum
                figure_part = detail.tampered_value.split(" (")[0]
                if figure_part not in text:
                    failures.append(f"amount_both: tampered figure '{figure_part}' not in text.")

        elif tt == TamperType.DATE_SHIFT:
            if detail.tampered_value and detail.tampered_value not in text:
                failures.append(f"date_shift: tampered date '{detail.tampered_value}' not in text.")

        elif tt == TamperType.PARTY_SWAP:
            if detail.tampered_value and detail.tampered_value not in text:
                failures.append(
                    f"party_swap: tampered party '{detail.tampered_value}' not in text."
                )

        elif tt == TamperType.CLAUSE_DELETE:
            if detail.original_value and detail.original_value in text:
                failures.append(
                    f"clause_delete: deleted heading '{detail.original_value}' still in text."
                )

        elif tt == TamperType.XREF_BREAK:
            if detail.tampered_value and detail.tampered_value not in text:
                failures.append(
                    f"xref_break: ghost reference '{detail.tampered_value}' not in text."
                )

        elif tt == TamperType.INCREMENTAL_EDIT:
            eof_count = _count_eof(pdf_path)
            if eof_count < 2:
                failures.append(
                    f"incremental_edit: only {eof_count} %%EOF marker(s); expected >= 2."
                )
            if detail.tampered_value and detail.tampered_value not in text:
                failures.append(
                    f"incremental_edit: new value '{detail.tampered_value}' not found in text."
                )

        elif tt == TamperType.HIDDEN_TEXT:
            if HIDDEN_TEXT_MARKER not in text:
                failures.append("hidden_text: hidden text marker not found in extracted text.")
            # Verify that the text has a very small font (we cannot easily check from outside;
            # we trust the injection; but we can check the sentence is there)
            if detail.tampered_value and detail.tampered_value[:20] not in text:
                failures.append(
                    f"hidden_text: injected sentence start not found in text: '{detail.tampered_value[:20]}'"
                )

    return failures


def verify_dataset(generated_dir: Path) -> bool:
    """Verify all documents in *generated_dir* against their labels.

    Returns True if all checks pass.
    """
    labels_path = generated_dir / "labels.jsonl"
    if not labels_path.exists():
        logger.error("labels.jsonl not found in %s", generated_dir)
        return False

    # Load labels
    labels: dict[str, DocLabel] = {}
    with labels_path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            lbl = DocLabel.model_validate_json(line)
            labels[lbl.doc_id] = lbl

    # Find all PDF files
    pdf_files = {p.stem: p for p in generated_dir.glob("*.pdf")}

    total = 0
    passed = 0
    failed_docs: list[str] = []

    # Check every label has a PDF
    for doc_id, label in labels.items():
        total += 1
        if doc_id not in pdf_files:
            logger.error("FAIL %s: PDF file missing.", doc_id)
            failed_docs.append(doc_id)
            continue

        failures = _check_label(label, pdf_files[doc_id])
        if failures:
            for msg in failures:
                logger.error("FAIL %s: %s", doc_id, msg)
            failed_docs.append(doc_id)
        else:
            passed += 1

    # Check every PDF has a label
    for stem, _path in pdf_files.items():
        if stem not in labels:
            logger.error("FAIL: PDF %s has no label.", stem)
            failed_docs.append(stem)
            total += 1

    all_pass = len(failed_docs) == 0
    pct = (passed / total * 100) if total > 0 else 0.0

    logger.info("=" * 60)
    logger.info("Verification result: %d/%d passed (%.1f%%)", passed, total, pct)
    if failed_docs:
        logger.info("FAILED documents (%d):", len(failed_docs))
        for d in failed_docs[:20]:
            logger.info("  - %s", d)
        if len(failed_docs) > 20:
            logger.info("  ... and %d more.", len(failed_docs) - 20)
    else:
        logger.info("All checks PASSED.")
    logger.info("=" * 60)

    return all_pass
