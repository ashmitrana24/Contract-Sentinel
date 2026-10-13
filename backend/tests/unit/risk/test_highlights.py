"""Unit tests for Highlight Locator (Module 8)."""

from __future__ import annotations

import pymupdf

from clauseguard.risk.highlights import compute_highlights
from clauseguard.schemas.findings import Finding, Severity
from clauseguard.schemas.parsed import ClauseModel, PageModel, SpanModel


def _extract_page_model_from_pymupdf(page: pymupdf.Page, page_no: int) -> PageModel:
    """Extract a PageModel from a live PyMuPDF page."""
    rect = page.rect
    page_dict = page.get_text("dict")
    spans: list[SpanModel] = []
    for b in page_dict.get("blocks", []):
        if b.get("type") != 0:
            continue
        for line in b.get("lines", []):
            for sp in line.get("spans", []):
                raw_bbox = sp.get("bbox", (0, 0, 0, 0))
                spans.append(
                    SpanModel(
                        text=sp.get("text", ""),
                        bbox=(
                            float(raw_bbox[0]),
                            float(raw_bbox[1]),
                            float(raw_bbox[2]),
                            float(raw_bbox[3]),
                        ),
                        size=float(sp.get("size", 10.0)),
                        font=str(sp.get("font", "Helvetica")),
                        color=int(sp.get("color", 0)),
                        flags=int(sp.get("flags", 0)),
                    )
                )

    return PageModel(
        page_no=page_no,
        width=rect.width,
        height=rect.height,
        text=page.get_text("text"),
        char_count=len(page.get_text("text")),
        spans=spans,
    )


def test_standard_page_evidence_clipping() -> None:
    # 1. Create a live PyMuPDF document with text
    doc = pymupdf.open()
    page = doc.new_page(width=612, height=792)
    evidence_text = "Fifty Thousand Rupees"
    full_sentence = f"The fee shall be Rs. 50,000 ({evidence_text}) payable upon delivery."
    page.insert_text((72, 140), full_sentence, fontsize=12)

    page_model = _extract_page_model_from_pymupdf(page, page_no=1)

    # 2. Finding referencing that evidence
    finding = Finding(
        module="consistency",
        type="figure_words_mismatch",
        severity=Severity.HIGH,
        page=1,
        evidence=f"Amount mismatch: 50,000 vs '{evidence_text}'",
        explanation="Numerical figure contradicts words",
        details={"figure_text": "50,000", "words_text": evidence_text},
    )

    # 3. Locate highlights
    highlights = compute_highlights(finding, [page_model])
    assert len(highlights) == 1
    hl = highlights[0]
    assert hl.page == 1
    assert not hl.approximate

    # 4. Assert PyMuPDF clip of the box contains the evidence
    box_rect = pymupdf.Rect(hl.bbox)
    clipped_text = page.get_text("text", clip=box_rect)
    assert evidence_text in clipped_text, f"Clipped text '{clipped_text}' does not contain '{evidence_text}'"


def test_rotated_page_fixture_and_clipping() -> None:
    # 1. Create a 90-degree rotated PyMuPDF page
    doc = pymupdf.open()
    page = doc.new_page(width=612, height=792)
    target_clause_text = "Governing law shall be the State of Delaware."
    page.insert_text((100, 150), target_clause_text, fontsize=12)
    page.set_rotation(90)

    page_model = _extract_page_model_from_pymupdf(page, page_no=1)

    finding = Finding(
        module="consistency",
        type="party_name_variant",
        severity=Severity.MEDIUM,
        page=1,
        evidence="State of Delaware",
        explanation="Jurisdiction name variant",
        details={"party_name": "State of Delaware"},
    )

    highlights = compute_highlights(finding, [page_model], rotation=page.rotation)
    assert len(highlights) == 1
    hl = highlights[0]
    assert hl.rotation == 90
    assert not hl.approximate

    # Assert clip contains the target phrase
    box_rect = pymupdf.Rect(hl.bbox)
    clipped_text = page.get_text("text", clip=box_rect)
    assert "State of Delaware" in clipped_text or "Delaware" in clipped_text


def test_stored_bbox_passthrough() -> None:
    page_dummy = PageModel(page_no=1, width=612, height=792, text="Sample", char_count=6, spans=[])
    stored_box = [120.0, 240.0, 360.0, 280.0]

    finding = Finding(
        module="pdf_forensics",
        type="hidden_text",
        severity=Severity.CRITICAL,
        page=1,
        bbox=tuple(stored_box),
        evidence="Confidential bonus clause",
        explanation="Hidden text rendered with zero opacity",
    )

    highlights = compute_highlights(finding, [page_dummy])
    assert len(highlights) == 1
    assert highlights[0].bbox == stored_box
    assert not highlights[0].approximate


def test_fallback_approximate_clause_heading() -> None:
    doc = pymupdf.open()
    page = doc.new_page(width=612, height=792)
    heading_text = "4.2 Payment Terms and Penalties"
    page.insert_text((72, 100), heading_text, fontsize=14)
    page.insert_text((72, 130), "Some other general text", fontsize=11)

    page_model = _extract_page_model_from_pymupdf(page, page_no=2)

    clause = ClauseModel(
        order_idx=3,
        clause_id="4.2",
        heading=heading_text,
        text=heading_text + "\nSome other general text",
        level=1,
        page_start=2,
        page_end=2,
        kind="clause",
    )

    # Finding whose specific evidence string is missing or abstract
    finding = Finding(
        module="consistency",
        type="dangling_reference",
        severity=Severity.HIGH,
        clause_ref="4.2",
        evidence="Dangling xref to Section 9.9",
        explanation="Section 9.9 is not found",
        details={"referenced_clause": "9.9"},
    )

    highlights = compute_highlights(finding, [page_model], clauses=[clause])
    assert len(highlights) == 1
    hl = highlights[0]
    assert hl.page == 2
    assert hl.approximate is True
    # Box should wrap heading
    box_rect = pymupdf.Rect(hl.bbox)
    clipped = page.get_text("text", clip=box_rect)
    assert "4.2" in clipped or "Payment" in clipped
