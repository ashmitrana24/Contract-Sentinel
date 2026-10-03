"""Pure parse_document function.

Takes PDF bytes → ParsedDocument pydantic model.
Raises ParseError for permanent failures (corrupt, password-protected, no pages).

The function touches NO external resources (no DB, no Redis, no filesystem).
The worker calls this and then persists the result.
"""

from __future__ import annotations

import logging

import pymupdf

from clauseguard.parsing.clauses import segment_clauses
from clauseguard.parsing.extract import extract_pages, extract_pdf_metadata
from clauseguard.schemas.parsed import ParsedDocument

logger = logging.getLogger(__name__)


class ParseError(Exception):
    """Permanent parse failure – do not retry."""


def parse_document(pdf_bytes: bytes) -> ParsedDocument:
    """Parse PDF bytes into a structured ParsedDocument.

    Parameters
    ----------
    pdf_bytes:
        Raw PDF content.

    Returns
    -------
    ParsedDocument
        Fully populated parsed document model.

    Raises
    ------
    ParseError
        For permanent failures: empty bytes, password-protected, corrupt PDF,
        or PDF with zero pages.
    """
    if not pdf_bytes:
        raise ParseError("Empty PDF bytes")

    try:
        doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    except Exception as exc:
        raise ParseError(f"Cannot open PDF: {exc}") from exc

    try:
        if doc.is_encrypted:
            # Try with empty password first (if 0, authentication failed -> requires password)
            if doc.authenticate("") == 0:
                raise ParseError("PDF is password-protected")

        page_count = doc.page_count
        if page_count == 0:
            raise ParseError("PDF has no pages")

        # Extract metadata (raw strings)
        pdf_metadata = extract_pdf_metadata(doc)

        # Extract pages
        pages = extract_pages(doc)

    finally:
        doc.close()

    # Check needs_ocr heuristic
    total_chars = sum(p.char_count for p in pages)
    avg_chars = total_chars / page_count if page_count > 0 else 0
    needs_ocr = False
    from clauseguard.config import get_settings

    threshold = get_settings().ocr_chars_per_page_threshold
    if avg_chars < threshold:
        needs_ocr = True
        logger.warning(
            "Low text density: %.1f chars/page (threshold %d) – needs_ocr=True",
            avg_chars,
            threshold,
        )

    # Segment clauses
    clauses = segment_clauses(pages)

    return ParsedDocument(
        pdf_metadata=pdf_metadata,
        page_count=page_count,
        needs_ocr=needs_ocr,
        pages=pages,
        clauses=clauses,
    )
