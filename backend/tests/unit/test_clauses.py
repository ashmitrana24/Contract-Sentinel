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


@pytest.mark.unit
def test_clauses_ignores_sec_exhibit_and_filing_headers() -> None:
    doc_text = """Exhibit 10.16
EX-10.3
1                                                                    Exhibit 10.17
MASTER SERVICES AGREEMENT
Between Alpha and Beta.

1. Definitions
All terms defined.

2. Services
Services specified here.
"""
    pages = [_make_page(doc_text)]
    clauses = segment_clauses(pages)

    clause_ids = [c.clause_id for c in clauses]
    assert "10.16" not in clause_ids
    assert "10.3" not in clause_ids
    assert "10.17" not in clause_ids
    # Clause 1 should be the Definitions clause, not the 1 Exhibit 10.17 line
    c1 = next(c for c in clauses if c.clause_id == "1")
    assert "Definitions" in c1.heading


@pytest.mark.unit
def test_clauses_ignores_toc_dot_leaders() -> None:
    doc_text = """TABLE OF CONTENTS
1. Definitions................................................1
2. Term and Termination.......................................5

1. Definitions
Definitions body text here.

2. Term and Termination
Termination body text here.
"""
    pages = [_make_page(doc_text)]
    clauses = segment_clauses(pages)

    # Should only have Preamble, Clause 1, Clause 2 (not duplicate TOC entries)
    clause_ids = [c.clause_id for c in clauses if c.clause_id != "0"]
    assert clause_ids == ["1", "2"]


@pytest.mark.unit
def test_clauses_restarted_numbering_inside_schedules_scoped() -> None:
    doc_text = """1. Definitions
Agreement definitions.

2. Obligations
Obligations of the parties.

Schedule A Statement of Work
1. Deliverables
Supplier deliverables under this schedule.

2. Timelines
Project timelines.
"""
    pages = [_make_page(doc_text)]
    clauses = segment_clauses(pages)

    clause_ids = [c.clause_id for c in clauses]
    assert "1" in clause_ids
    assert "2" in clause_ids
    assert "Schedule A" in clause_ids
    assert "Schedule A.1" in clause_ids
    assert "Schedule A.2" in clause_ids

    c_s1 = next(c for c in clauses if c.clause_id == "Schedule A.1")
    assert c_s1.parent_clause_id == "Schedule A"
    assert "Deliverables" in c_s1.heading


def test_clauses_roman_article_with_nested_sections():
    """ARTICLE V with Section 5.1 and 5.2 nested under it produces clauses for all."""
    doc_text = """
    AGREEMENT
    ARTICLE V
    TERMINATION
    Section 5.1 Early Termination.
    Either party may terminate early upon notice.
    5.2 Notice.
    Written notice must be provided within 30 days.
    ARTICLE VI
    GOVERNING LAW
    Section 6.1 Jurisdiction.
    Courts of Delaware have jurisdiction.
    """
    pages = [_make_page(doc_text)]
    clauses = segment_clauses(pages)
    clause_ids = [c.clause_id for c in clauses]

    assert "5" in clause_ids
    assert "5.1" in clause_ids
    assert "5.2" in clause_ids
    assert "6" in clause_ids
    assert "6.1" in clause_ids

    c_51 = next(c for c in clauses if c.clause_id == "5.1")
    assert c_51.parent_clause_id == "5"


def test_clauses_article_with_inline_sections():
    """Embedded ARTICLE VI and Section 6.1 in line-wrapped commercial filings."""
    doc_text = """
    Preamble text.
    ARTICLE VI REGISTRATION RIGHTS Section 6.1 Demand Registration.
    (a) If the Company receives a written request.
    Section 6.2 Piggyback Registration.
    (a) If the Company proposes to register.
    """
    pages = [_make_page(doc_text)]
    clauses = segment_clauses(pages)
    clause_ids = [c.clause_id for c in clauses]

    assert "6" in clause_ids
    assert "6.1" in clause_ids
    assert "6.2" in clause_ids


def test_clauses_article_with_nested_dotted_number_same_line():
    """ARTICLE 3 - RELATIONSHIP OF PARTIES 3.1 The Company..."""
    doc_text = """
    ARTICLE 3 - RELATIONSHIP OF PARTIES 3.1 The Company shall operate.
    3.2 Management.
    ARTICLE 4 - OFFICE LOCATION 4.1 The Company headquarters.
    """
    pages = [_make_page(doc_text)]
    clauses = segment_clauses(pages)
    clause_ids = [c.clause_id for c in clauses]

    assert "3" in clause_ids
    assert "3.1" in clause_ids
    assert "3.2" in clause_ids
    assert "4" in clause_ids
    assert "4.1" in clause_ids


def test_clauses_preamble_numbered_party_list_does_not_collide_with_clause_1():
    """Regression test for ContractNLI numbered list in preamble colliding with operative Clause 1."""
    doc_text = """NON-DISCLOSURE AGREEMENT
Between:
1. Last Man Stands, (the "Disclosing Party"); and
2. Recipient Corp, (the "Receiving Party").

WHEREAS the parties wish to evaluate a transaction;
NOW, THEREFORE, the parties agree as follows:

1. Confidential Information.
The Receiving Party agrees to maintain confidentiality.

2. Term and Termination.
This agreement shall continue for two years.
"""
    pages = [_make_page(doc_text)]
    clauses = segment_clauses(pages)
    clause_ids = [c.clause_id for c in clauses]

    # Exactly one preamble (0) and clauses 1 and 2
    assert clause_ids == ["0", "1", "2"]
    c1 = next(c for c in clauses if c.clause_id == "1")
    assert c1.heading == "Confidential Information."
    assert 'Last Man Stands, (the "Disclosing Party"); and' in clauses[0].text


def test_clauses_blank_line_after_heading_preserved():
    """Regression test: blank line after a number-only heading does not discard the heading."""
    doc_text = """
    Preamble text.

    ARTICLE VII.
    REPRESENTATIONS AND WARRANTIES
    Each party represents and warrants.

    ARTICLE VIII.

    INTELLECTUAL PROPERTY RIGHTS
    8.1 Limited Grant. Hydraspin hereby grants to Distributor an exclusive license.

    ARTICLE IX.
    CONFIDENTIALITY
    Each party agrees to keep confidential.
    """
    pages = [_make_page(doc_text)]
    clauses = segment_clauses(pages)
    clause_ids = [c.clause_id for c in clauses]

    assert "7" in clause_ids
    assert "8" in clause_ids
    assert "9" in clause_ids


