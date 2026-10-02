"""Incremental edit tamper (file-level).

Tamper 8: simulate a post-signing edit. Open the rendered PDF with PyMuPDF,
redact one numeric or date value, insert a replacement at the same position,
and save with incremental=True. The resulting file must contain at least
two %%EOF markers.

Windows note: PyMuPDF holds a file lock until doc.close() is called.
We must close before any unlink/read.

PyMuPDF note: ReportLab PDFs may trigger an auto-repair on open. We
pre-save the PDF non-incrementally first so the repaired version is the
base; then we do the incremental save on top of that.
"""

from __future__ import annotations

import logging
import random
import re
import tempfile
from pathlib import Path

import pymupdf as fitz  # PyMuPDF

from datagen.models import TamperDetail, TamperType
from datagen.tamper.base import FileTamper, TamperNotApplicable

logger = logging.getLogger(__name__)

# Patterns to find targets for redaction
_AMOUNT_RE = re.compile(r"Rs\.\s*[\d,]+")
_DATE_RE = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")


def _pick_target(doc: fitz.Document, rng: random.Random) -> tuple[int, fitz.Rect, str, str]:
    """Find a redaction target in the document.

    Returns (page_index, rect, original_value, replacement_value).
    """
    candidates: list[tuple[int, fitz.Rect, str, str]] = []

    for page_idx in range(len(doc)):
        page = doc[page_idx]
        text_dict = page.get_text("dict")  # type: ignore[arg-type]
        for block in text_dict.get("blocks", []):
            if block.get("type") != 0:
                continue
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    span_text = span.get("text", "")
                    # Try amount match
                    m = _AMOUNT_RE.search(span_text)
                    if m:
                        rect = fitz.Rect(span["bbox"])
                        original = m.group()
                        # Replace with a different value
                        digits = re.sub(r"[^\d]", "", original)
                        if digits:
                            new_digits = str(int(digits) + 100000)
                            # Reformat with comma
                            replacement = f"Rs. {_reformat_amount(new_digits)}"
                            candidates.append((page_idx, rect, original, replacement))
                        continue
                    # Try date match
                    m = _DATE_RE.search(span_text)
                    if m:
                        rect = fitz.Rect(span["bbox"])
                        original = m.group()
                        year = int(original[:4])
                        replacement = f"{year + 1}{original[4:]}"
                        candidates.append((page_idx, rect, original, replacement))

    if not candidates:
        raise TamperNotApplicable("No amount or date text found for incremental redaction.")

    return rng.choice(candidates)


def _reformat_amount(digits: str) -> str:
    """Indian-comma format a digit string."""
    if len(digits) <= 3:
        return digits
    last3 = digits[-3:]
    rest = digits[:-3]
    groups = []
    while len(rest) > 2:
        groups.append(rest[-2:])
        rest = rest[:-2]
    if rest:
        groups.append(rest)
    groups.reverse()
    return ",".join(groups) + "," + last3


class IncrementalEditTamper(FileTamper):
    """Tamper 8: post-signing incremental PDF edit."""

    tamper_type = TamperType.INCREMENTAL_EDIT

    def apply(self, artifact: bytes, rng: random.Random) -> tuple[bytes, TamperDetail]:
        # Step 1: write original bytes to a temp file
        tmp_dir = Path(tempfile.mkdtemp())
        base_path = tmp_dir / "base.pdf"
        clean_path = tmp_dir / "clean.pdf"
        final_path = tmp_dir / "final.pdf"

        try:
            base_path.write_bytes(artifact)

            # Step 2: open and re-save as standard PDF to eliminate
            # any auto-repair issues (ReportLab PDFs get repaired on open)
            doc = fitz.open(str(base_path))
            try:
                doc.save(str(clean_path))  # full save, not incremental
            finally:
                doc.close()

            # Step 3: open the clean PDF and pick a redaction target
            doc = fitz.open(str(clean_path))
            try:
                page_idx, rect, original, replacement = _pick_target(doc, rng)
                page = doc[page_idx]

                # Add redaction annotation
                page.add_redact_annot(rect, fill=(1, 1, 1))
                page.apply_redactions()

                # Insert replacement text
                fontsize = 9.0
                page.insert_text(
                    fitz.Point(rect.x0, rect.y1 - 2),
                    replacement,
                    fontname="helv",
                    fontsize=fontsize,
                    color=(0, 0, 0),
                )

                # Step 4: incremental save to SAME path (required by PyMuPDF)
                doc.save(
                    str(clean_path),
                    incremental=True,
                    encryption=fitz.PDF_ENCRYPT_KEEP,
                )
            finally:
                doc.close()

            result_bytes = clean_path.read_bytes()

        finally:
            # Clean up temp directory
            for p in [base_path, clean_path, final_path]:
                try:
                    p.unlink(missing_ok=True)
                except Exception:
                    pass
            try:
                tmp_dir.rmdir()
            except Exception:
                pass

        # Verify %%EOF count
        eof_count = result_bytes.count(b"%%EOF")
        if eof_count < 2:
            raise TamperNotApplicable(
                f"Incremental save produced only {eof_count} %%EOF marker(s); expected at least 2."
            )

        detail = TamperDetail(
            tamper_type=TamperType.INCREMENTAL_EDIT,
            page=page_idx,
            original_value=original,
            tampered_value=replacement,
            subtype="incremental_redact_insert",
            extra={"eof_count": eof_count},
        )
        return result_bytes, detail
