"""Unit tests for finding type catalog (Module 8)."""

from __future__ import annotations

from clauseguard.risk.catalog import get_catalog, get_finding_type_info

# All known finding types emitted by pdf_forensics and consistency modules
FORENSICS_TYPES = [
    "hidden_text",
    "signature_invalid",
    "post_signature_modification",
    "incremental_update",
    "metadata_anomaly",
    "active_content",
    "annotation_overlay",
    "detector_error",
]

CONSISTENCY_TYPES = [
    "figure_words_mismatch",
    "date_order_conflict",
    "effective_date_conflict",
    "term_length_conflict",
    "party_name_variant",
    "unknown_party_entity",
    "dangling_reference",
    "duplicate_clause_number",
    "numbering_gap",
]


def test_all_forensics_types_in_catalog() -> None:
    catalog = get_catalog()
    for ftype in FORENSICS_TYPES:
        assert ftype in catalog, f"Forensics type {ftype} missing from catalog"
        info = catalog[ftype]
        assert info.category == "tampering"
        assert len(info.title) > 0
        assert len(info.what_it_means) > 10
        assert len(info.what_to_check) > 10


def test_all_consistency_types_in_catalog() -> None:
    catalog = get_catalog()
    for ftype in CONSISTENCY_TYPES:
        assert ftype in catalog, f"Consistency type {ftype} missing from catalog"
        info = catalog[ftype]
        assert info.category == "inconsistency"
        assert len(info.title) > 0
        assert len(info.what_it_means) > 10
        assert len(info.what_to_check) > 10


def test_unknown_type_fallback_gracefully() -> None:
    info_tamper = get_finding_type_info("unseen_tamper_flag", module="pdf_forensics")
    assert info_tamper.category == "tampering"
    assert "Unseen tamper flag" in info_tamper.title
    assert len(info_tamper.what_it_means) > 0
    assert len(info_tamper.what_to_check) > 0

    info_inconsistency = get_finding_type_info("odd_clause_variance", module="consistency")
    assert info_inconsistency.category == "inconsistency"
    assert "Odd clause variance" in info_inconsistency.title


def test_catalog_immutability() -> None:
    cat = get_catalog()
    assert len(cat) >= len(FORENSICS_TYPES) + len(CONSISTENCY_TYPES)
    # Check figure_words_mismatch specifically
    fwm = cat["figure_words_mismatch"]
    assert fwm.title == "Amount in words doesn't match the figure"
