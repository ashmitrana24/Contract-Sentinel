"""Unit tests for words-and-figure pair consistency detector."""

import pytest

from clauseguard.consistency.models import ConsistencySettings
from clauseguard.consistency.pairs import detect_pairs
from clauseguard.consistency.text_index import build_text_index
from clauseguard.schemas.findings import Severity
from clauseguard.schemas.parsed import ClauseModel, PageModel, ParsedDocument

pytestmark = pytest.mark.unit


def _make_doc(text: str, clause_id: str = "4.2") -> ParsedDocument:
    return ParsedDocument(
        page_count=1,
        pages=[PageModel(page_no=1, width=612.0, height=792.0, text=text, char_count=len(text))],
        clauses=[
            ClauseModel(
                order_idx=0,
                clause_id=clause_id,
                heading="Payment Clause",
                text=text,
                level=1,
                page_start=1,
                page_end=1,
                kind="clause",
            )
        ],
    )


def test_matching_amount_pairs_produce_no_findings():
    doc = _make_doc("The service fee shall be Rs. 10,00,000 (Rupees Ten Lakh Only) payable on completion.")
    index = build_text_index(doc)
    findings, stats = detect_pairs(index, ConsistencySettings())
    assert len(findings) == 0
    assert stats["pairs_found"] == 1
    assert stats["pairs_verified"] == 1
    assert stats["pairs_mismatched"] == 0


def test_mismatching_amount_pairs_produce_high_finding():
    doc = _make_doc("The service fee shall be Rs. 28,00,000 (Rupees Ten Lakh Only) payable on completion.")
    index = build_text_index(doc)
    findings, stats = detect_pairs(index, ConsistencySettings())
    assert len(findings) == 1
    f = findings[0]
    assert f.type == "figure_words_mismatch"
    assert f.severity == Severity.HIGH
    assert f.clause_ref == "4.2"
    assert "28,00,000" in f.evidence
    assert "Ten Lakh" in f.evidence
    assert stats["pairs_mismatched"] == 1


def test_mismatching_words_before_figures():
    doc = _make_doc("The deposit is Rupees One Lakh (Rs. 5,00,000) received on signing.")
    index = build_text_index(doc)
    findings, stats = detect_pairs(index, ConsistencySettings())
    assert len(findings) == 1
    assert findings[0].severity == Severity.HIGH
    assert stats["pairs_mismatched"] == 1


def test_mismatching_percentage_pairs():
    doc = _make_doc("An interest rate of five percent (15%) shall accrue per annum.")
    index = build_text_index(doc)
    findings, stats = detect_pairs(index, ConsistencySettings())
    assert len(findings) == 1
    assert findings[0].severity == Severity.HIGH
    assert stats["pairs_mismatched"] == 1


def test_mismatching_quantity_pairs_produce_medium_finding():
    doc = _make_doc("Notice period shall be thirty (45) days from receipt.")
    index = build_text_index(doc)
    findings, stats = detect_pairs(index, ConsistencySettings())
    assert len(findings) == 1
    assert findings[0].severity == Severity.MEDIUM
    assert stats["pairs_mismatched"] == 1


def test_matching_quantity_pairs():
    doc = _make_doc("Notice period shall be thirty (30) days from receipt.")
    index = build_text_index(doc)
    findings, stats = detect_pairs(index, ConsistencySettings())
    assert len(findings) == 0
    assert stats["pairs_verified"] == 1


def test_non_adjacent_numbers_never_pair():
    doc = _make_doc("The term is 30 days and the total fee is Rs. 50,000 paid across 2 milestones.")
    index = build_text_index(doc)
    findings, stats = detect_pairs(index, ConsistencySettings())
    assert len(findings) == 0
    assert stats["pairs_found"] == 0


def test_unparseable_parenthetical_counted_in_stats_no_finding():
    doc = _make_doc("See Schedule 1 (referencing 5-year outlook and clause 2) for details.")
    index = build_text_index(doc)
    findings, stats = detect_pairs(index, ConsistencySettings())
    assert len(findings) == 0
    assert stats["pairs_unparseable"] >= 1
