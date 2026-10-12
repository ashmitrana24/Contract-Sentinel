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
import re
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
    for detail_idx, detail in enumerate(label.tamper_details):
        tt = detail.tamper_type

        # Check if overwritten by a later tamper in combined tampers
        is_overwritten = any(
            later.original_value and detail.tampered_value and detail.tampered_value in later.original_value
            for later in label.tamper_details[detail_idx + 1 :]
        )

        if tt == TamperType.AMOUNT_FIGURE_ONLY:
            if not is_overwritten and detail.tampered_value and detail.tampered_value not in text:
                failures.append(
                    f"amount_figure_only: tampered figure '{detail.tampered_value}' not in text."
                )

        elif tt == TamperType.AMOUNT_BOTH:
            if not is_overwritten and detail.tampered_value:
                figure_part = detail.tampered_value.split(" (")[0]
                if figure_part not in text:
                    failures.append(f"amount_both: tampered figure '{figure_part}' not in text.")

        elif tt == TamperType.DATE_SHIFT:
            if not is_overwritten and detail.tampered_value and detail.tampered_value not in text:
                failures.append(f"date_shift: tampered date '{detail.tampered_value}' not in text.")

        elif tt == TamperType.PARTY_SWAP:
            if not is_overwritten and detail.tampered_value and detail.tampered_value not in text:
                failures.append(
                    f"party_swap: tampered party '{detail.tampered_value}' not in text."
                )

        elif tt == TamperType.CLAUSE_DELETE:
            if detail.original_value:
                cid_esc = re.escape(detail.clause_id) if detail.clause_id else r"\d+"
                heading_esc = re.escape(detail.original_value)
                pat = re.compile(
                    rf"(?:^|\n)\s*(?:(?:Section|Clause|Article|ARTICLE|SECTION)\s+)?{cid_esc}[\.\:\s\-\u2013]+\s*{heading_esc}\b",
                    re.IGNORECASE,
                )
                if pat.search(text):
                    failures.append(
                        f"clause_delete: deleted heading '{detail.original_value}' still in text."
                    )

        elif tt == TamperType.XREF_BREAK:
            if not is_overwritten and detail.tampered_value and detail.tampered_value not in text:
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

        # 4b. Verifier check for detail.page and detail.clause_id accuracy
        val_for_loc: str | None = None
        if tt == TamperType.AMOUNT_BOTH and detail.tampered_value:
            val_for_loc = detail.tampered_value.split(" (")[0]
        elif tt == TamperType.HIDDEN_TEXT:
            val_for_loc = detail.tampered_value[:20] if detail.tampered_value else HIDDEN_TEXT_MARKER
        elif detail.tampered_value:
            val_for_loc = detail.tampered_value

        # Check page match if recorded
        if detail.page is not None:
            doc_obj = fitz.open(str(pdf_path))
            try:
                num_pages = len(doc_obj)
                if detail.page < 0 or detail.page >= num_pages:
                    failures.append(
                        f"{tt}: recorded page {detail.page} out of bounds (doc has {num_pages} pages)."
                    )
                elif val_for_loc:
                    val_norm = " ".join(val_for_loc.split())
                    target_page_text = " ".join(doc_obj[detail.page].get_text().split())
                    if val_norm not in target_page_text:
                        actual_pages = [
                            p_idx
                            for p_idx, p in enumerate(doc_obj)
                            if val_norm in " ".join(p.get_text().split())
                        ]
                        failures.append(
                            f"{tt}: tampered value '{val_for_loc}' not found on recorded page {detail.page} "
                            f"(actually appears on page(s): {actual_pages})."
                        )
            finally:
                doc_obj.close()

        # Check clause_id match if recorded
        if detail.clause_id is not None and val_for_loc and tt != TamperType.CLAUSE_DELETE:
            val_pat = re.compile(r"\s+".join(re.escape(w) for w in val_for_loc.split()))
            matches = list(val_pat.finditer(text))
            if matches:
                import re as re_mod
                heading_pat = re_mod.compile(
                    r"(?:^|\n)\s*(?:(?:Section|Clause|Article|ARTICLE|SECTION)\s+)?"
                    r"([0-9]+(?:\.[0-9]+)*|[IVXLCDM]+)[\.\:\s\-\u2013]\s*([A-Za-z].*?)(?=\n|$)",
                    re_mod.IGNORECASE,
                )
                headings = list(heading_pat.finditer(text))
                target_cid = detail.clause_id.strip()
                found_in_clause = False
                found_cids: list[str] = []

                for m in matches:
                    pos = m.start()
                    active_h = None
                    for h in headings:
                        if h.start() <= pos:
                            active_h = h
                        else:
                            break
                    if active_h:
                        h_cid = active_h.group(1).rstrip(".")
                        found_cids.append(h_cid)
                        if (
                            h_cid == target_cid
                            or h_cid.startswith(f"{target_cid}.")
                            or target_cid.startswith(f"{h_cid}.")
                            or ("." in target_cid and "." in h_cid and target_cid.split(".")[0] == h_cid.split(".")[0])
                        ):
                            found_in_clause = True
                            break
                    else:
                        found_cids.append("preamble")
                        if target_cid.lower() in {"preamble", "title", "0"}:
                            found_in_clause = True
                            break

                if not found_in_clause:
                    failures.append(
                        f"{tt}: tampered value '{val_for_loc}' appears under clause(s) {found_cids}, "
                        f"not recorded clause_id '{detail.clause_id}'."
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
