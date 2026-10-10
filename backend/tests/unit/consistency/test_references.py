"""Unit tests for cross-reference consistency detector."""

import pytest

from clauseguard.consistency.models import ConsistencySettings
from clauseguard.consistency.references import detect_cross_references
from clauseguard.consistency.text_index import build_text_index
from clauseguard.schemas.findings import Severity
from clauseguard.schemas.parsed import ClauseModel, PageModel, ParsedDocument

pytestmark = pytest.mark.unit


def _make_doc(clauses: list[tuple[str, str]], page_text: str | None = None) -> ParsedDocument:
    clause_objs = []
    for idx, (cid, text) in enumerate(clauses):
        clause_objs.append(
            ClauseModel(
                order_idx=idx,
                clause_id=cid,
                heading=f"Clause {cid}",
                text=text,
                level=1,
                page_start=1,
                page_end=1,
                kind="clause",
            )
        )
    full_text = page_text or "\n".join(f"Clause {cid}\n{text}" for cid, text in clauses)
    pages = [PageModel(page_no=1, width=612.0, height=792.0, text=full_text, char_count=len(full_text))]
    return ParsedDocument(page_count=1, pages=pages, clauses=clause_objs)


def test_subitem_clause_resolves():
    """Clause 4.2(a) resolves against existing Clause 4.2."""
    doc = _make_doc([
        ("1", "Preamble and intro."),
        ("2", "As set forth in Clause 4.2(a), the vendor must comply."),
        ("3", "Standard confidentiality terms."),
        ("4.1", "Initial scope."),
        ("4.2", "Detailed specifications and conditions in paragraph (a)."),
        ("5", "Governing law."),
    ])
    index = build_text_index(doc)
    settings = ConsistencySettings()
    findings, stats = detect_cross_references(doc, index, settings)

    assert len(findings) == 0
    assert stats["dangling_detected"] == 0


def test_ranges_and_lists_resolve():
    """Ranges (Sections 2 to 4) and lists (Clauses 2 and 3) resolve against existing clauses."""
    doc = _make_doc([
        ("1", "Pursuant to Sections 2 to 4, fees shall be disbursed."),
        ("2", "First milestone."),
        ("3", "Second milestone, subject to Clauses 2 and 4."),
        ("4", "Final milestone."),
        ("5", "Term and termination."),
        ("6", "Notices."),
    ])
    index = build_text_index(doc)
    settings = ConsistencySettings()
    findings, stats = detect_cross_references(doc, index, settings)

    assert len(findings) == 0
    assert stats["dangling_detected"] == 0


def test_external_references_ignored():
    """External statutory references like Section 138 of Negotiable Instruments Act are ignored."""
    doc = _make_doc([
        ("1", "The parties agree to submit to jurisdiction."),
        ("2", "Proceedings under Section 138 of the Negotiable Instruments Act, 1881 may be instituted."),
        ("3", "Compliance with Section 135 of the Companies Act, 2013 is mandatory."),
        ("4", "Nothing herein prejudices rights under the Arbitration and Conciliation Act."),
        ("5", "Termination terms."),
    ])
    index = build_text_index(doc)
    settings = ConsistencySettings()
    findings, stats = detect_cross_references(doc, index, settings)

    assert len(findings) == 0
    assert stats["external_ignored"] >= 2


def test_dangling_reference_flagged():
    """Reference to non-existent clause is flagged with MEDIUM severity."""
    doc = _make_doc([
        ("1", "Agreement overview."),
        ("2", "See Clause 99 for penalty calculations."),
        ("3", "Payment terms."),
        ("4", "Deliverables."),
        ("5", "Closing remarks."),
    ])
    index = build_text_index(doc)
    settings = ConsistencySettings()
    findings, _stats = detect_cross_references(doc, index, settings)

    assert len(findings) == 1
    f = findings[0]
    assert f.type == "dangling_reference"
    assert f.severity == Severity.MEDIUM
    assert f.details["missing_target"] == "99"
    assert "Clause 99" in f.evidence


def test_page_text_safeguard():
    """If clause number is in raw page text at line start, it is not flagged even if unsegmented."""
    # Segmenter only captured clauses 1, 2, 3, 5, 6, but page text clearly has line starting with "4. Special Terms"
    page_text = (
        "1. Agreement\nOverview\n"
        "2. Scope\nAs defined in Section 4.\n"
        "3. Payment\nRs 100\n"
        "4. Special Terms\nUnsegmented by segmenter\n"
        "5. Termination\nNotice\n"
        "6. Law\nIndia"
    )
    doc = _make_doc(
        [
            ("1", "Overview"),
            ("2", "As defined in Section 4."),
            ("3", "Rs 100"),
            ("5", "Notice"),
            ("6", "India"),
        ],
        page_text=page_text,
    )
    index = build_text_index(doc)
    settings = ConsistencySettings()
    findings, _stats = detect_cross_references(doc, index, settings)

    # Safeguard should recognize that "4" exists in raw page text at line start
    assert len(findings) == 0


def test_unsegmented_skips():
    """Unsegmented or fewer than 5 clauses skips cross-reference checks."""
    doc = _make_doc([
        ("1", "See Clause 99."),
        ("2", "General."),
    ])
    index = build_text_index(doc)
    settings = ConsistencySettings()
    findings, stats = detect_cross_references(doc, index, settings)

    assert len(findings) == 0
    assert stats["skipped_reason"] == "unsegmented_or_too_few_clauses"
