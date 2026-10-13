"""Highlight locator for ClauseGuard integrity and forensics findings.

Maps findings to visual bounding box highlights on PDF pages:
- Uses stored bbox from detector if present
- Locates evidence in page spans by searching distinctive strings from finding details
  and evidence snippets, longest first, taking union of matching span bboxes
- Top-left origin PyMuPDF points [x0, y0, x1, y1]
- Fallback to approximate clause-level highlight or empty list
"""

from __future__ import annotations

import re
import unicodedata
from typing import Any

from pydantic import BaseModel, Field


class Highlight(BaseModel):
    """Visual bounding box highlight on a document page."""

    page: int = Field(description="1-based page number")
    bbox: list[float] = Field(description="[x0, y0, x1, y1] in PDF points")
    page_width: float
    page_height: float
    rotation: int = Field(default=0, description="Page rotation in degrees (0, 90, 180, 270)")
    approximate: bool = Field(default=False, description="True if highlight is estimated")


def normalize_str(s: str) -> str:
    """Normalize unicode and collapse whitespace."""
    if not s:
        return ""
    nfkc = unicodedata.normalize("NFKC", str(s))
    return " ".join(nfkc.split()).strip()


def _extract_candidate_strings(finding: Any) -> list[str]:
    """Extract distinctive search phrases from finding details and evidence."""
    candidates: list[str] = []

    # 1. From details dictionary
    details = getattr(finding, "details", None)
    if isinstance(details, dict):
        # Priority keys in detector details
        keys = [
            "figure_text",
            "words_text",
            "number_text",
            "target_clause",
            "referenced_clause",
            "variant_name",
            "party_name",
            "defined_name",
            "candidate_name",
            "unknown_party",
            "date_1_text",
            "date_2_text",
            "date_text",
            "effective_date",
            "term_text",
            "snippet",
            "quote",
            "evidence_text",
        ]
        for k in keys:
            v = details.get(k)
            if v and isinstance(v, str) and len(v.strip()) >= 2:
                candidates.append(v.strip())

        # Any other string values in details
        for k, v in details.items():
            if k not in keys and isinstance(v, str) and 3 <= len(v.strip()) <= 150:
                candidates.append(v.strip())

    # 2. From evidence snippet
    evidence = getattr(finding, "evidence", "")
    if evidence and isinstance(evidence, str):
        ev_clean = evidence.strip()
        # If evidence contains quotes like "XYZ", extract quoted portions
        quoted = re.findall(r'["\']([^"\']{3,80})["\']', ev_clean)
        candidates.extend(quoted)

        # Whole evidence or clauses
        if len(ev_clean) <= 120:
            candidates.append(ev_clean)
        else:
            # First and second sentence/phrases
            phrases = [p.strip() for p in re.split(r"[;\n\.]", ev_clean) if len(p.strip()) >= 4]
            candidates.extend(phrases[:3])

    # Deduplicate and sort longest first
    seen = set()
    unique_candidates: list[str] = []
    for c in candidates:
        norm = normalize_str(c)
        if norm and len(norm) >= 2 and norm.lower() not in seen:
            seen.add(norm.lower())
            unique_candidates.append(norm)

    unique_candidates.sort(key=lambda s: len(s), reverse=True)
    return unique_candidates


def _union_bboxes(bboxes: list[tuple[float, float, float, float] | list[float]]) -> list[float]:
    """Compute the enclosing bounding box of multiple bboxes."""
    if not bboxes:
        return [0.0, 0.0, 0.0, 0.0]
    x0 = min(float(b[0]) for b in bboxes)
    y0 = min(float(b[1]) for b in bboxes)
    x1 = max(float(b[2]) for b in bboxes)
    y1 = max(float(b[3]) for b in bboxes)
    return [round(x0, 2), round(y0, 2), round(x1, 2), round(y1, 2)]


def _search_page_spans(page_obj: Any, candidate: str) -> list[float] | None:
    """Find candidate string in page spans and return the union bounding box."""
    spans = getattr(page_obj, "spans", None)
    if not spans or not isinstance(spans, list):
        return None

    # Fast path: check if candidate is contained inside any single span
    cand_norm = normalize_str(candidate).lower()
    if not cand_norm:
        return None

    matching_spans: list[list[float]] = []

    # First attempt: single span exact match or containment
    for span in spans:
        span_text = span.get("text", "") if isinstance(span, dict) else getattr(span, "text", "")
        norm_st = normalize_str(span_text).lower()
        if cand_norm == norm_st or cand_norm in norm_st:
            bbox = span.get("bbox") if isinstance(span, dict) else getattr(span, "bbox", None)
            if bbox and len(bbox) == 4:
                matching_spans.append(list(bbox))

    if matching_spans:
        return _union_bboxes(matching_spans)

    # Multi-span search: build concatenated page span stream
    span_entries = []
    stream_tokens = []
    char_offset = 0

    for _idx, span in enumerate(spans):
        st = span.get("text", "") if isinstance(span, dict) else getattr(span, "text", "")
        norm_s = normalize_str(st)
        if not norm_s:
            continue
        bbox = span.get("bbox") if isinstance(span, dict) else getattr(span, "bbox", None)
        if not bbox or len(bbox) != 4:
            continue

        start_pos = char_offset
        end_pos = start_pos + len(norm_s)
        span_entries.append((start_pos, end_pos, list(bbox)))
        stream_tokens.append(norm_s)
        char_offset = end_pos + 1  # count space

    page_stream = " ".join(stream_tokens).lower()
    match_idx = page_stream.find(cand_norm)
    if match_idx != -1:
        match_end = match_idx + len(cand_norm)
        overlapping_bboxes = [
            bbox
            for (s_start, s_end, bbox) in span_entries
            if s_start < match_end and s_end > match_idx
        ]
        if overlapping_bboxes:
            return _union_bboxes(overlapping_bboxes)

    # Substring word token search (if candidate is a multi-word phrase)
    cand_words = cand_norm.split()
    if len(cand_words) >= 2:
        # Search for first 2-3 words
        shorter_cand = " ".join(cand_words[:3])
        match_idx = page_stream.find(shorter_cand)
        if match_idx != -1:
            match_end = match_idx + len(shorter_cand)
            overlapping_bboxes = [
                bbox
                for (s_start, s_end, bbox) in span_entries
                if s_start < match_end and s_end > match_idx
            ]
            if overlapping_bboxes:
                return _union_bboxes(overlapping_bboxes)

    return None


def compute_highlights(
    finding: Any,
    pages: list[Any],
    clauses: list[Any] | None = None,
    rotation: int = 0,
) -> list[Highlight]:
    """Compute page highlights for a finding."""
    if not pages:
        return []

    # Map pages by page_no
    pages_by_num: dict[int, Any] = {}
    for p in pages:
        p_no = getattr(p, "page_no", 1)
        pages_by_num[p_no] = p

    finding_page_no = getattr(finding, "page", None)
    finding_bbox = getattr(finding, "bbox", None)

    # 1. Stored bbox is present
    if finding_bbox and len(finding_bbox) == 4:
        target_page_no = finding_page_no or 1
        page_obj = pages_by_num.get(target_page_no, pages[0])
        p_width = float(getattr(page_obj, "width", 612.0))
        p_height = float(getattr(page_obj, "height", 792.0))
        return [
            Highlight(
                page=target_page_no,
                bbox=[round(float(x), 2) for x in finding_bbox],
                page_width=p_width,
                page_height=p_height,
                rotation=rotation,
                approximate=False,
            )
        ]

    # 2. Search for candidate strings in page spans
    candidate_strings = _extract_candidate_strings(finding)

    # Determine pages to search
    pages_to_search: list[Any] = []
    if finding_page_no and finding_page_no in pages_by_num:
        pages_to_search.append(pages_by_num[finding_page_no])

    # If clause_ref is given, check clause's page range
    clause_ref = getattr(finding, "clause_ref", None)
    target_clause = None
    if clause_ref and clauses:
        for c in clauses:
            if getattr(c, "clause_id", "") == clause_ref:
                target_clause = c
                break

    if target_clause:
        c_start = getattr(target_clause, "page_start", 1)
        c_end = getattr(target_clause, "page_end", c_start)
        for p_idx in range(c_start, c_end + 1):
            if p_idx in pages_by_num and pages_by_num[p_idx] not in pages_to_search:
                pages_to_search.append(pages_by_num[p_idx])

    # Add remaining pages as fallback
    for p in pages:
        if p not in pages_to_search:
            pages_to_search.append(p)

    # Attempt string search across candidate strings, longest first
    for cand in candidate_strings:
        for p_obj in pages_to_search:
            box = _search_page_spans(p_obj, cand)
            if box:
                p_no = getattr(p_obj, "page_no", 1)
                p_width = float(getattr(p_obj, "width", 612.0))
                p_height = float(getattr(p_obj, "height", 792.0))
                return [
                    Highlight(
                        page=p_no,
                        bbox=box,
                        page_width=p_width,
                        page_height=p_height,
                        rotation=rotation,
                        approximate=False,
                    )
                ]

    # 3. Fallback: page-level approximate highlight at clause start
    if target_clause:
        c_start = getattr(target_clause, "page_start", 1)
        p_obj = pages_by_num.get(c_start, pages[0])
        p_width = float(getattr(p_obj, "width", 612.0))
        p_height = float(getattr(p_obj, "height", 792.0))

        # Try to locate clause heading span
        c_heading = getattr(target_clause, "heading", "")
        if c_heading:
            h_box = _search_page_spans(p_obj, c_heading)
            if h_box:
                return [
                    Highlight(
                        page=c_start,
                        bbox=h_box,
                        page_width=p_width,
                        page_height=p_height,
                        rotation=rotation,
                        approximate=True,
                    )
                ]

        # First span of the page if available
        spans = getattr(p_obj, "spans", [])
        if spans:
            first_span = spans[0]
            f_box = first_span.get("bbox") if isinstance(first_span, dict) else getattr(first_span, "bbox", None)
            if f_box and len(f_box) == 4:
                return [
                    Highlight(
                        page=c_start,
                        bbox=[float(x) for x in f_box],
                        page_width=p_width,
                        page_height=p_height,
                        rotation=rotation,
                        approximate=True,
                    )
                ]

        # Top section box
        return [
            Highlight(
                page=c_start,
                bbox=[72.0, 72.0, round(p_width - 72.0, 2), 140.0],
                page_width=p_width,
                page_height=p_height,
                rotation=rotation,
                approximate=True,
            )
        ]

    # If page is known without clause
    if finding_page_no and finding_page_no in pages_by_num:
        p_obj = pages_by_num[finding_page_no]
        p_width = float(getattr(p_obj, "width", 612.0))
        p_height = float(getattr(p_obj, "height", 792.0))
        return [
            Highlight(
                page=finding_page_no,
                bbox=[72.0, 72.0, round(p_width - 72.0, 2), 140.0],
                page_width=p_width,
                page_height=p_height,
                rotation=rotation,
                approximate=True,
            )
        ]

    return []
