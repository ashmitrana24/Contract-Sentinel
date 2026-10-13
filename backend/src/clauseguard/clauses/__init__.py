"""Clause classification and key-term extraction package for ClauseGuard."""

from clauseguard.clauses.taxonomy import (
    ALL_LABELS,
    CORE_CUAD_LABELS,
    EXTRA_RULE_LABELS,
    METADATA_CATEGORIES,
    LabelDefinition,
    get_label_definition,
    normalize_category_to_label,
)

__all__ = [
    "ALL_LABELS",
    "CORE_CUAD_LABELS",
    "EXTRA_RULE_LABELS",
    "METADATA_CATEGORIES",
    "LabelDefinition",
    "get_label_definition",
    "normalize_category_to_label",
]
