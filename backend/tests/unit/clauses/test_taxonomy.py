"""Unit tests for ClauseGuard taxonomy."""


from clauseguard.clauses.taxonomy import (
    ALL_LABELS,
    CORE_CUAD_LABELS,
    CUAD_CATEGORY_TO_ID,
    EXTRA_RULE_LABELS,
    METADATA_CATEGORIES,
    get_label_definition,
    is_cuad_label,
    normalize_category_to_label,
)


def test_taxonomy_label_counts():
    assert len(CORE_CUAD_LABELS) == 36
    assert len(EXTRA_RULE_LABELS) == 9
    assert len(ALL_LABELS) == 45
    assert len(set(ALL_LABELS)) == 45  # All unique


def test_metadata_categories_excluded():
    assert len(METADATA_CATEGORIES) == 5
    for meta in METADATA_CATEGORIES:
        assert normalize_category_to_label(meta) is None


def test_cuad_category_mapping():
    for cuad_cat, label_id in CUAD_CATEGORY_TO_ID.items():
        assert normalize_category_to_label(cuad_cat) == label_id
        assert label_id in CORE_CUAD_LABELS
        assert is_cuad_label(label_id) is True
        defn = get_label_definition(label_id)
        assert defn is not None
        assert defn.source == "cuad"
        assert defn.cuad_category == cuad_cat


def test_extra_rule_labels():
    expected_extras = {
        "indemnification",
        "confidentiality",
        "payment_terms",
        "unilateral_amendment",
        "force_majeure",
        "arbitration_or_dispute_resolution",
        "waiver_of_rights",
        "termination_for_cause",
        "auto_renewal",
    }
    assert set(EXTRA_RULE_LABELS) == expected_extras
    for extra in EXTRA_RULE_LABELS:
        assert not is_cuad_label(extra)
        defn = get_label_definition(extra)
        assert defn is not None
        assert defn.source == "rule_only"
