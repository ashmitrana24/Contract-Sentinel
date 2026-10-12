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


def test_us_statutes_and_external_agreements_ignored():
    """US statutes, Bankruptcy Code, Indenture, and civil codes are whitelisted."""
    doc = _make_doc([
        ("1", "General overview."),
        ("2", "Parties are entitled to protections of section 363(m) and 364(e) of the Bankruptcy Code."),
        ("3", "Pursuant to California Civil Code section 1654, ambiguity shall be resolved."),
        ("4", "Meaning is as defined in Section 2.14 of the Indenture and Section 14 of the General Terms."),
        ("5", "Subject to subsection (k) of Section 351 of the PHSA and Section 306 of the FDCA."),
    ])
    index = build_text_index(doc)
    settings = ConsistencySettings()
    findings, stats = detect_cross_references(doc, index, settings)

    assert len(findings) == 0
    assert stats["external_ignored"] >= 3


def test_statute_shorthand_defined_in_contract():
    """References to sections defined in the contract as shorthand for a statute are ignored."""
    doc = _make_doc(
        [
            ("1", "General provisions and definitions."),
            ("2", "As defined in Section 222 of the Communications Act of 1934 (as amended, \"Section 222\")."),
            ("3", "CPNI restrictions contained in Section 222 shall be respected by vendor."),
            ("4", "\"Section 365\" has the meaning ascribed to it in Title 11 of the Bankruptcy Code."),
            ("5", "Licenses under Section 365 shall continue in full force."),
            ("6", "General boilerplate and notices."),
        ]
    )
    index = build_text_index(doc)
    settings = ConsistencySettings()
    findings, stats = detect_cross_references(doc, index, settings)

    assert len(findings) == 0
    assert stats["external_ignored"] >= 2


def test_statute_subparagraph_chain():
    """Statute-style sub-paragraph chains like '351(l)(3)(A)' or '351(l) (3)(A)' are ignored."""
    doc = _make_doc([
        ("1", "Overview and patent terms."),
        ("2", "Lists exchanged pursuant to Section 351(l) (3)(A) and Section 351(l)(5)(b)(i)(II) of law."),
        ("3", "Action under Section 101(a)(15)(H) shall be maintained."),
        ("4", "Confidentiality obligations."),
        ("5", "Term and termination."),
    ])
    index = build_text_index(doc)
    settings = ConsistencySettings()
    findings, stats = detect_cross_references(doc, index, settings)

    assert len(findings) == 0
    assert stats["external_ignored"] >= 1


def test_amending_agreement_references_ignored():
    """References inside amending agreements modifying existing agreement or in inserted quotes are ignored."""
    doc = _make_doc(
        [
            ("1", "AMENDMENT NO. 2 TO MANUFACTURING AND SUPPLY AGREEMENT."),
            ("2", "Section 14.2 of the Existing Agreement is hereby amended by deleting in its entirety subsection (b)."),
            ("3", "The Distributor Agreement is hereby amended by adding thereto a new Section 15.11."),
            ("4", "Added as a new Section 2.1 (d): \"2.1 (d) Subject to regulatory requirements, supplier shall deliver.\""),
            ("5", "Miscellaneous terms and governing law."),
        ]
    )
    index = build_text_index(doc)
    settings = ConsistencySettings()
    findings, stats = detect_cross_references(doc, index, settings)

    assert len(findings) == 0
    assert stats["external_ignored"] >= 2


def test_mutatis_mutandis_and_external_agreement_ranges():
    """References with mutatis mutandis or 'through ... of the ... Agreement' are ignored."""
    doc = _make_doc([
        ("1", "Background and recitals."),
        ("2", "Information disclosures shall be governed, mutatis mutandis, by Section 6.08 and Section 6.09."),
        ("3", "Requirements of Sections 3.4.4(b) through 3.4.4(h) of the AZ License Agreement apply."),
        ("4", "Except as provided in the License Agreement under Section 9.2, 9.3 or 9.4 thereof."),
        ("5", "Termination and survival."),
    ])
    index = build_text_index(doc)
    settings = ConsistencySettings()
    findings, stats = detect_cross_references(doc, index, settings)

    assert len(findings) == 0
    assert stats["external_ignored"] >= 3


def test_roman_arabic_clause_equivalence():
    """Reference to Article 5 resolves against existing ARTICLE V."""
    doc = _make_doc([
        ("I", "Definitions."),
        ("II", "Scope."),
        ("III", "Representations."),
        ("IV", "Covenants."),
        ("V", "License Grants."),
        ("VI", "Except as set forth in Article 5, no further rights are granted."),
    ])
    index = build_text_index(doc)
    settings = ConsistencySettings()
    findings, stats = detect_cross_references(doc, index, settings)

    assert len(findings) == 0
    assert stats["dangling_detected"] == 0


def test_subclause_reference_resolves_when_parent_or_ancestor_exists():
    """References to Section 4.3(a) and 10.1(a)(i) resolve to existing parent clauses."""
    doc = _make_doc([
        ("1", "Preamble."),
        ("2", "Reference to Section 4.3(a) and Section 10.1(a)(i) herein."),
        ("3", "Milestones."),
        ("4.3", "License Grant terms."),
        ("10.1", "Confidentiality terms."),
        ("11", "Term and Termination."),
    ])
    index = build_text_index(doc)
    settings = ConsistencySettings()
    findings, stats = detect_cross_references(doc, index, settings)

    assert len(findings) == 0
    assert stats["dangling_detected"] == 0


def test_subclause_reference_flagged_when_parent_missing():
    """Reference to Section 99.1(a) where parent 99 does not exist must be flagged as dangling."""
    doc = _make_doc([
        ("1", "Preamble."),
        ("2", "In accordance with Section 99.1(a), payments shall accelerate."),
        ("3", "Milestones."),
        ("4", "Performance."),
        ("5", "General."),
        ("6", "Termination."),
    ])
    index = build_text_index(doc)
    settings = ConsistencySettings()
    findings, stats = detect_cross_references(doc, index, settings)

    assert len(findings) == 1
    f = findings[0]
    assert f.type == "dangling_reference"
    assert f.severity == Severity.MEDIUM
    assert "99.1(a)" in f.evidence
    assert stats["dangling_detected"] == 1


def test_uncertain_reference_reported_as_low():
    """Reference where document has redactions or internal pointer 'below' is reported as LOW (uncertain)."""
    doc = _make_doc([
        ("1", "Overview [***]."),
        ("2", "Obligations under section 88.1 shall continue."),
        ("3", "Milestones."),
        ("4", "General Performance Obligations."),
        ("5", "Exit Fee as defined in section 7.6(c) below."),
        ("6", "Survival includes Sections 2.3, 4.4.2, 5.7, 5.9, 6.3.6, 11.1."),
    ])
    index = build_text_index(doc)
    settings = ConsistencySettings()
    findings, stats = detect_cross_references(doc, index, settings)

    # Missing targets (7.6 below, list of sections) should be LOW (uncertain)
    for f in findings:
        assert f.severity in (Severity.LOW, Severity.MEDIUM)
    assert stats["uncertain_moved_to_low"] > 0


def test_statutory_citations_ignored_when_statutory_context():
    """Statutory citations like Section 409A, Section 12(g), Section 16(b) are ignored when context is statutory."""
    doc = _make_doc([
        ("1", "Overview and introductory terms."),
        ("2", "This agreement is intended to comply with Section 409A of the Internal Revenue Code."),
        ("3", "The Common Stock is registered under Section 12(g) of the Securities Exchange Act of 1934."),
        ("4", "Transactions exempt from liability under Section 16(b) of the Exchange Act."),
        ("5", "Executive may make an election under Section 83(b) of the Code."),
        ("6", "Parachute payments governed by Section 280G of the Internal Revenue Code."),
        ("7", "License rights subject to Section 365(n) of the Bankruptcy Code."),
    ])
    index = build_text_index(doc)
    settings = ConsistencySettings()
    findings, stats = detect_cross_references(doc, index, settings)

    assert len(findings) == 0
    assert stats["dangling_detected"] == 0
    assert stats["external_ignored"] >= 6


def test_non_existent_contract_clause_number_still_flagged():
    """Non-existent clause numbers in the contract's own numbering remain flagged even if Act/Code is mentioned."""
    doc = _make_doc([
        ("1", "Pursuant to the Companies Act, the parties agree as follows."),
        ("2", "Obligations set forth in Clause 99 shall be strictly enforced."),
        ("3", "Standard dispute resolution terms."),
        ("4", "Confidentiality terms."),
        ("5", "Termination provisions."),
    ])
    index = build_text_index(doc)
    settings = ConsistencySettings()
    findings, _ = detect_cross_references(doc, index, settings)

    # Clause 99 is a numeric reference in the contract's numbering, NOT a statutory citation like 409A
    assert len(findings) == 1
    assert findings[0].type == "dangling_reference"
    assert findings[0].severity == Severity.MEDIUM
    assert "99" in findings[0].evidence


def test_dotted_clause_number_not_resolved_to_parent():
    """Clause 4.9 must not resolve to Clause 4 when 4.9 does not exist."""
    doc = _make_doc([
        ("1", "Introduction."),
        ("2", "Payment schedule."),
        ("3", "Deliverables."),
        ("4", "Intellectual property terms."),
        ("5", "Vendor must adhere to specifications in Clause 4.9."),
        ("6", "Governing law."),
    ])
    index = build_text_index(doc)
    settings = ConsistencySettings()
    findings, _ = detect_cross_references(doc, index, settings)

    assert len(findings) == 1
    assert findings[0].type == "dangling_reference"
    assert "4.9" in findings[0].evidence


