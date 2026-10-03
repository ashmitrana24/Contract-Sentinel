"""PDF text extraction using PyMuPDF.

Extracts per-page text (in reading order), positioned text spans, and
document-level PDF metadata.  Does NOT use OCR; if extraction yields
very little text the caller sets needs_ocr=True.

Always import ``pymupdf`` (not the legacy ``fitz`` alias).
"""

from __future__ import annotations

import logging
from typing import Any

import pymupdf

from clauseguard.parsing.normalize import normalize_text
from clauseguard.schemas.parsed import PageModel, SpanModel

logger = logging.getLogger(__name__)


def extract_pdf_metadata(doc: pymupdf.Document) -> dict[str, str]:
    """Return a sanitised copy of doc.metadata (string values only)."""
    raw: dict[str, Any] = doc.metadata or {}
    return {k: str(v) for k, v in raw.items() if v is not None}


def extract_pages(doc: pymupdf.Document) -> list[PageModel]:
    """Extract text and spans from every page.

    Span fields preserved: text (raw), bbox (4 floats), size, font, color (int), flags.
    Image blocks are skipped.
    Text is assembled in reading order via get_text('text') then normalized.
    """
    pages: list[PageModel] = []

    for page_no_0, page in enumerate(doc):
        page_no = page_no_0 + 1  # 1-based
        rect = page.rect
        width = rect.width
        height = rect.height

        # Full-page text in reading order (fast path)
        raw_text: str = page.get_text("text")  # type: ignore[attr-defined]
        normalized = normalize_text(raw_text)

        # Spans from structured dict
        spans: list[SpanModel] = []
        try:
            page_dict = page.get_text("dict")  # type: ignore[attr-defined]
            for block in page_dict.get("blocks", []):
                # Skip image blocks (type == 1)
                if block.get("type") != 0:
                    continue
                for line in block.get("lines", []):
                    for span in line.get("spans", []):
                        span_text: str = span.get("text", "")
                        if not span_text:
                            continue
                        raw_bbox = span.get("bbox", (0, 0, 0, 0))
                        spans.append(
                            SpanModel(
                                text=span_text,
                                bbox=(
                                    float(raw_bbox[0]),
                                    float(raw_bbox[1]),
                                    float(raw_bbox[2]),
                                    float(raw_bbox[3]),
                                ),
                                size=float(span.get("size", 0)),
                                font=str(span.get("font", "")),
                                color=int(span.get("color", 0)),
                                flags=int(span.get("flags", 0)),
                            )
                        )
        except Exception as exc:
            logger.warning("Page %d span extraction failed: %s", page_no, exc)

        pages.append(
            PageModel(
                page_no=page_no,
                width=width,
                height=height,
                text=normalized,
                char_count=len(normalized),
                spans=spans,
            )
        )

    return pages
