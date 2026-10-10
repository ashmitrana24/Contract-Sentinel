"""Unit tests for party name consistency detector."""


from clauseguard.consistency.models import ConsistencySettings
from clauseguard.consistency.parties import (
    detect_party_inconsistencies,
    normalize_entity_name,
)
from clauseguard.consistency.text_index import build_text_index
from clauseguard.schemas.findings import Severity
from clauseguard.schemas.parsed import (
    ClauseModel,
    PageModel,
    ParsedDocument,
)


def _make_doc(intro: str, clauses: list[tuple[str, str]]) -> ParsedDocument:
    clause_objs = [
        ClauseModel(
            order_idx=0,
            clause_id="0",
            heading="Preamble",
            text=intro,
            level=0,
            page_start=1,
            page_end=1,
            kind="preamble",
        )
    ]
    for idx, (cid, text) in enumerate(clauses, start=1):
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
    full_text = f"{intro}\n" + "\n".join(t for _, t in clauses)
    pages = [
        PageModel(
            page_no=1,
            width=612.0,
            height=792.0,
            text=full_text,
            char_count=len(full_text),
        )
    ]
    return ParsedDocument(
        page_count=1,
        pages=pages,
        clauses=clause_objs,
    )


def test_normalize_entity_suffixes():
    """Verify that different suffix spellings normalize identically."""
    n1 = normalize_entity_name("Acme Technologies Private Limited")
    n2 = normalize_entity_name("Acme Technologies Pvt. Ltd.")
    n3 = normalize_entity_name("Acme Technologies Pvt Ltd")
    n4 = normalize_entity_name("Acme Technologies Pvt. Ltd")

    assert n1 == n2 == n3 == n4 == "acme technologies pvt ltd"

    assert normalize_entity_name("Apex Solutions Limited") == normalize_entity_name("Apex Solutions Ltd.")
    assert normalize_entity_name("Delta Inc.") == normalize_entity_name("Delta Incorporated")
    assert normalize_entity_name("Global Corp.") == normalize_entity_name("Global Corporation")
    assert normalize_entity_name("Vanguard L.L.C.") == normalize_entity_name("Vanguard LLC")


def test_benign_suffix_spelling_never_flagged():
    """Pvt. Ltd. vs Private Limited in body must never be flagged."""
    intro = (
        "This Agreement is entered into between Acme Technologies Private Limited (Vendor) "
        "and Beta Solutions Ltd. (Client)."
    )
    doc = _make_doc(
        intro,
        [
            ("1", "Acme Technologies Pvt. Ltd. shall provide software services to Beta Solutions Limited."),
            ("2", "All fees shall be paid to Acme Technologies Private Limited promptly."),
        ],
    )
    index = build_text_index(doc)
    settings = ConsistencySettings()
    findings, stats = detect_party_inconsistencies(doc, index, settings)

    assert len(findings) == 0
    assert stats["variants_detected"] == 0


def test_one_letter_variant_flagged_medium():
    """Acme Technology Pvt Ltd vs Acme Technologies Pvt Ltd must be flagged MEDIUM."""
    intro = (
        "Between: Acme Technologies Private Limited (Vendor) and Beta Solutions Ltd. (Client)"
    )
    doc = _make_doc(
        intro,
        [
            ("1", "Acme Technology Pvt. Ltd. shall deliver monthly progress reports to Beta Solutions Ltd."),
        ],
    )
    index = build_text_index(doc)
    settings = ConsistencySettings()
    findings, _stats = detect_party_inconsistencies(doc, index, settings)

    variant_findings = [f for f in findings if f.type == "party_name_variant"]
    assert len(variant_findings) == 1
    assert variant_findings[0].severity == Severity.MEDIUM
    assert variant_findings[0].clause_ref == "1"
    assert "Acme Technology" in variant_findings[0].evidence


def test_third_party_entity_flagged_low_only():
    """Clearly distinct third-party legal entity (bank/vendor) only yields unknown_party_entity (LOW)."""
    intro = (
        "Between: Acme Technologies Pvt. Ltd. (Vendor) and Beta Solutions Ltd. (Client)"
    )
    doc = _make_doc(
        intro,
        [
            ("1", "Payments shall be made via escrow through Standard Chartered Bank Ltd. in Mumbai."),
        ],
    )
    index = build_text_index(doc)
    settings = ConsistencySettings()
    findings, _stats = detect_party_inconsistencies(doc, index, settings)

    # Standard Chartered Bank Ltd. should not be a variant
    assert not any(f.type == "party_name_variant" for f in findings)
    # It should be unknown_party_entity (LOW)
    unknown = [f for f in findings if f.type == "unknown_party_entity"]
    assert len(unknown) == 1
    assert unknown[0].severity == Severity.LOW


def test_fewer_than_two_parties_skips_detector():
    """If fewer than 2 parties are extracted, skip detector and record in stats."""
    intro = "This is a general policy document without named contracting parties."
    doc = _make_doc(
        intro,
        [
            ("1", "Acme Technology Pvt. Ltd. may perform audits annually."),
        ],
    )
    index = build_text_index(doc)
    settings = ConsistencySettings()
    findings, stats = detect_party_inconsistencies(doc, index, settings)

    assert len(findings) == 0
    assert stats["skipped_reason"] == "fewer_than_2_parties"
    assert stats["parties_found"] < 2
