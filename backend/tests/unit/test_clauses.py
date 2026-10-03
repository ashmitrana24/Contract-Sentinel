"""Unit tests for heuristic clause segmenter."""

from __future__ import annotations

import pytest

from clauseguard.parsing.clauses import segment_clauses
from clauseguard.schemas.parsed import PageModel


def _make_page(text: str, page_no: int = 1) -> PageModel:
    return PageModel(
        page_no=page_no,
        width=595.0,
        height=842.0,
        text=text,
        char_count=len(text),
        spans=[],
    )


@pytest.mark.unit
def test_clauses_standard_numeric_with_preamble() -> None:
    doc_text = """MASTER SERVICES AGREEMENT
This Agreement is entered into between Party A and Party B.

1. Definitions
In this Agreement, the following terms have meanings set forth below.

2. Services
The Service Provider shall provide the Services described herein.
"""
    pages = [_make_page(doc_text)]
    clauses = segment_clauses(pages)

    assert len(clauses) == 3
    # Preamble
    assert clauses[0].clause_id == "0"
    assert clauses[0].kind == "preamble"
    assert "MASTER SERVICES AGREEMENT" in clauses[0].text

    # Clause 1
    assert clauses[1].clause_id == "1"
    assert clauses[1].heading == "Definitions"
    assert "In this Agreement" in clauses[1].text
    assert clauses[1].level == 1

    # Clause 2
    assert clauses[2].clause_id == "2"
    assert clauses[2].heading == "Services"
    assert clauses[2].level == 1


@pytest.mark.unit
def test_clauses_nested_numbering() -> None:
    doc_text = """1. Term and Termination
This agreement commences on Effective Date.

1.1 Early Termination
Either party may terminate early.

1.2 Notice Period
Notice must be in writing.

1.2.1 Emergency Notice
Immediate notice allowed for breach.
"""
    pages = [_make_page(doc_text)]
    clauses = segment_clauses(pages)

    # Note: no preamble because doc starts directly with clause 1
    ids = [c.clause_id for c in clauses]
    assert "1" in ids
    assert "1.1" in ids
    assert "1.2" in ids
    assert "1.2.1" in ids

    c_1 = next(c for c in clauses if c.clause_id == "1")
    c_1_1 = next(c for c in clauses if c.clause_id == "1.1")
    c_1_2_1 = next(c for c in clauses if c.clause_id == "1.2.1")

    assert c_1.level == 1
    assert c_1_1.level == 2
    assert c_1_1.parent_clause_id == "1"
    assert c_1_2_1.level == 3
    assert c_1_2_1.parent_clause_id == "1.2"


@pytest.mark.unit
def test_clauses_keyword_headings() -> None:
    doc_text = """PREAMBLE TEXT

Section 1 Confidentiality
All information shall be kept confidential.

Clause 2 Liability
Neither party shall be liable for indirect damages.

Article III Governing Law
This agreement shall be governed by Delaware law.
"""
    pages = [_make_page(doc_text)]
    clauses = segment_clauses(pages)

    assert any(c.heading == "Confidentiality" for c in clauses)
    assert any(c.heading == "Liability" for c in clauses)
    assert any(c.heading == "Governing Law" for c in clauses)


@pytest.mark.unit
def test_clauses_lettered_subitems_preserved_in_body() -> None:
    doc_text = """1. Obligations
The supplier shall fulfill the following:
(a) Provide monthly reports.
(b) Attend steering meetings.
(i) Prepare meeting minutes.

2. Warranties
Standard warranties apply.
"""
    pages = [_make_page(doc_text)]
    clauses = segment_clauses(pages)

    c1 = next(c for c in clauses if c.clause_id == "1")
    assert "(a) Provide monthly reports." in c1.text
    assert "(b) Attend steering meetings." in c1.text
    assert "(i) Prepare meeting minutes." in c1.text


@pytest.mark.unit
def test_clauses_rejects_dates_decimals_and_page_numbers() -> None:
    doc_text = """1. Financial Terms
The interest rate is 2.5 percent per annum.
The agreement is signed on 1.1.2026 by all parties.
1

2. Miscellaneous
General legal terms.
2
"""
    pages = [_make_page(doc_text)]
    clauses = segment_clauses(pages)

    assert len(clauses) == 2
    c1 = clauses[0]
    assert c1.clause_id == "1"
    assert "2.5 percent" in c1.text
    assert "1.1.2026" in c1.text

    c2 = clauses[1]
    assert c2.clause_id == "2"


@pytest.mark.unit
def test_clauses_unsegmented_fallback() -> None:
    doc_text = """A simple letter without any formal clause numbering.
Just normal paragraphs of text describing terms between two parties.
No numbered sections appear here.
"""
    pages = [_make_page(doc_text)]
    clauses = segment_clauses(pages)

    assert len(clauses) == 1
    assert clauses[0].kind == "unsegmented"
    assert clauses[0].clause_id == "U"
    assert "A simple letter" in clauses[0].text
