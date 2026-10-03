"""Pydantic models for parsed document output.

These are the in-memory representations produced by parse_document and
persisted to the DB by the worker.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class SpanModel(BaseModel):
    """One text span from PyMuPDF's get_text('dict')."""

    text: str
    bbox: tuple[float, float, float, float]
    size: float
    font: str
    color: int
    flags: int


class PageModel(BaseModel):
    """Parsed output for a single PDF page."""

    page_no: int = Field(description="1-based page number")
    width: float
    height: float
    text: str = Field(description="Normalized full-page text in reading order")
    char_count: int
    spans: list[SpanModel] = Field(default_factory=list)


class ClauseModel(BaseModel):
    """One segmented clause."""

    order_idx: int = Field(description="0-based insertion order")
    clause_id: str = Field(
        description="Dotted clause number e.g. '4.2', '0' for preamble, 'U' for unsegmented"
    )
    heading: str
    text: str
    level: int = Field(description="Nesting depth: 1=top, 2=sub, 3=sub-sub, etc.")
    parent_clause_id: str | None = None
    page_start: int = Field(description="1-based page number where clause begins")
    page_end: int = Field(description="1-based page number where clause ends")
    kind: str = Field(description="'preamble', 'clause', or 'unsegmented'")


class ParsedDocument(BaseModel):
    """Complete parsed output for one PDF."""

    pdf_metadata: dict[str, str] = Field(default_factory=dict)
    page_count: int
    needs_ocr: bool = False
    pages: list[PageModel]
    clauses: list[ClauseModel]
