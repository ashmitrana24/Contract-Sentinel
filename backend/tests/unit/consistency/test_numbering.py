"""Unit tests for clause numbering consistency detector."""

import pytest

from clauseguard.consistency.models import ConsistencySettings
from clauseguard.consistency.numbering import detect_clause_numbering
from clauseguard.consistency.text_index import build_text_index
from clauseguard.schemas.findings import Severity
from clauseguard.schemas.parsed import ClauseModel, PageModel, ParsedDocument

pytestmark = pytest.mark.unit


def _make_doc(clauses: list[tuple[str, str, str]]) -> ParsedDocument:
    clause_objs = []
    for idx, (cid, heading, text) in enumerate(clauses):
        clause_objs.append(
            ClauseModel(
                order_idx=idx,
                clause_id=cid,
                heading=heading,
                text=text,
                level=1,
                page_start=1,
                page_end=1,
                kind="clause",
            )
        )
    full_text = "\n".join(f"{h}\n{t}" for _, h, t in clauses)
    pages = [PageModel(page_no=1, width=612.0, height=792.0, text=full_text, char_count=len(full_text))]
    return ParsedDocument(page_count=1, pages=pages, clauses=clause_objs)


def test_numbering_gap_flagged_low():
    """Missing clause in sequential top-level numbering is flagged LOW."""
    # Sequence: 1, 2, 4, 5, 6 (missing 3)
    doc = _make_doc([
        ("1", "Definitions", "Terms defined herein."),
        ("2", "Scope of Work", "Services provided."),
        ("4", "Payment Terms", "Fees paid monthly."),
        ("5", "Confidentiality", "Non-disclosure terms."),
        ("6", "Governing Law", "Laws of India."),
    ])
    index = build_text_index(doc)
    settings = ConsistencySettings()
    findings, _stats = detect_clause_numbering(doc, index, settings)

    gap_findings = [f for f in findings if f.type == "numbering_gap"]
    assert len(gap_findings) == 1
    assert gap_findings[0].severity == Severity.LOW
    assert gap_findings[0].clause_ref == "3"
    assert "Missing clause 3" in gap_findings[0].evidence


def test_numbering_gap_with_dangling_xref_upgraded_high():
    """Missing clause with dangling reference to it is escalated to HIGH."""
    # Sequence: 1, 2, 4, 5, 6 (missing 3) and dangling target "3"
    doc = _make_doc([
        ("1", "Definitions", "Terms defined herein."),
        ("2", "Scope of Work", "Services provided."),
        ("4", "Payment Terms", "Fees paid monthly."),
        ("5", "Confidentiality", "Non-disclosure terms."),
        ("6", "Governing Law", "Laws of India."),
    ])
    index = build_text_index(doc)
    settings = ConsistencySettings()
    findings, _stats = detect_clause_numbering(doc, index, settings, dangling_targets=["3"])

    gap_findings = [f for f in findings if f.type == "numbering_gap"]
    assert len(gap_findings) == 1
    assert gap_findings[0].severity == Severity.HIGH
    assert gap_findings[0].clause_ref == "3"
    assert gap_findings[0].details["dangling_xref_correlated"] is True


def test_gap_next_to_reserved_not_flagged():
    """A gap next to [Reserved] or Intentionally Omitted heading is not flagged."""
    doc = _make_doc([
        ("1", "Definitions", "Terms defined herein."),
        ("2", "Scope of Work [Reserved]", "This clause is intentionally omitted."),
        ("4", "Payment Terms", "Fees paid monthly."),
        ("5", "Confidentiality", "Non-disclosure terms."),
        ("6", "Governing Law", "Laws of India."),
    ])
    index = build_text_index(doc)
    settings = ConsistencySettings()
    findings, _stats = detect_clause_numbering(doc, index, settings)

    gap_findings = [f for f in findings if f.type == "numbering_gap"]
    assert len(gap_findings) == 0


def test_duplicate_clause_numbers_flagged_medium():
    """Duplicate top-level clause numbers are flagged with MEDIUM severity."""
    doc = _make_doc([
        ("1", "Definitions", "Terms defined herein."),
        ("2", "Scope of Work", "Services provided."),
        ("3", "Payment Terms", "Fees paid monthly."),
        ("3", "Alternate Payment Schedule", "Milestone payments."),
        ("4", "Confidentiality", "Non-disclosure terms."),
        ("5", "Governing Law", "Laws of India."),
    ])
    index = build_text_index(doc)
    settings = ConsistencySettings()
    findings, _stats = detect_clause_numbering(doc, index, settings)

    dup_findings = [f for f in findings if f.type == "duplicate_clause_number"]
    assert len(dup_findings) == 1
    assert dup_findings[0].severity == Severity.MEDIUM
    assert dup_findings[0].clause_ref == "3"
    assert dup_findings[0].details["occurrence_count"] == 2
