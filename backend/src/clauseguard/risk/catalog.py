"""Canonical finding type catalog for ClauseGuard.

Provides category, human-readable title, plain English explanation,
and actionable review steps for all finding types emitted by PDF forensics
and consistency check detectors.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

FindingCategory = Literal["tampering", "inconsistency"]


class FindingTypeInfo(BaseModel):
    """Catalog metadata for one finding type."""

    type: str = Field(description="Machine-readable finding type identifier")
    category: FindingCategory = Field(description="'tampering' or 'inconsistency'")
    title: str = Field(description="Short title in plain English")
    what_it_means: str = Field(description="One or two plain sentences explaining what this means")
    what_to_check: str = Field(description="One actionable review line")


CATALOG: dict[str, FindingTypeInfo] = {
    # -----------------------------------------------------------------------
    # Forensics (Tampering)
    # -----------------------------------------------------------------------
    "hidden_text": FindingTypeInfo(
        type="hidden_text",
        category="tampering",
        title="Hidden or invisible text detected",
        what_it_means=(
            "Text was rendered using invisible color, microscopic font size, or an invisible render mode. "
            "This is often used to conceal clauses or deceive optical inspection."
        ),
        what_to_check="Inspect the hidden text snippet and compare against standard contract provisions.",
    ),
    "signature_invalid": FindingTypeInfo(
        type="signature_invalid",
        category="tampering",
        title="Digital signature integrity issue",
        what_it_means=(
            "A digital signature in the document failed cryptographic digest validation or has an invalid byte range. "
            "The document content may have been altered after signing."
        ),
        what_to_check="Verify the signer certificate and compare the signed byte range against the full file.",
    ),
    "post_signature_modification": FindingTypeInfo(
        type="post_signature_modification",
        category="tampering",
        title="Document modified after signature",
        what_it_means=(
            "Content was added or modified after a digital signature was applied, "
            "violating signature modification policy."
        ),
        what_to_check="Check which fields or objects were altered in the post-signature revision.",
    ),
    "incremental_update": FindingTypeInfo(
        type="incremental_update",
        category="tampering",
        title="Post-creation revision or alteration",
        what_it_means=(
            "The PDF contains incremental update revisions where page content or form fields were modified "
            "after initial file creation."
        ),
        what_to_check="Review the differences between revisions to ensure only authorized edits were made.",
    ),
    "metadata_anomaly": FindingTypeInfo(
        type="metadata_anomaly",
        category="tampering",
        title="Conflicting or suspicious document metadata",
        what_it_means=(
            "Timestamps or software producer tags indicate contradictory creation/modification dates "
            "or use of online editing utilities."
        ),
        what_to_check="Review document creation history and verify the source authoring tool.",
    ),
    "active_content": FindingTypeInfo(
        type="active_content",
        category="tampering",
        title="Active content or executable script found",
        what_it_means=(
            "The document contains embedded JavaScript, launch actions, or external stream triggers "
            "that could alter presentation or pose security risks."
        ),
        what_to_check="Examine embedded scripts and actions to ensure no dynamic content alters contractual terms.",
    ),
    "annotation_overlay": FindingTypeInfo(
        type="annotation_overlay",
        category="tampering",
        title="Suspicious visual overlay or annotation",
        what_it_means=(
            "An annotation or opaque redaction layer obscures underlying document content."
        ),
        what_to_check="Confirm whether the overlay was intended and verify what text lies beneath.",
    ),
    "detector_error": FindingTypeInfo(
        type="detector_error",
        category="tampering",
        title="Forensics detector execution failure",
        what_it_means=(
            "An internal detector encountered an error while analyzing document structure."
        ),
        what_to_check="Check the worker logs and inspect the PDF structure for parsing anomalies.",
    ),
    # -----------------------------------------------------------------------
    # Consistency (Inconsistency)
    # -----------------------------------------------------------------------
    "figure_words_mismatch": FindingTypeInfo(
        type="figure_words_mismatch",
        category="inconsistency",
        title="Amount in words doesn't match the figure",
        what_it_means=(
            "The numerical monetary amount does not equal the corresponding spelled-out amount words "
            "within the same clause."
        ),
        what_to_check="Confirm the intended payment or liability amount with the drafting parties.",
    ),
    "date_order_conflict": FindingTypeInfo(
        type="date_order_conflict",
        category="inconsistency",
        title="Conflicting date sequence",
        what_it_means=(
            "A subsequent contractual date (such as termination date) is chronologically earlier than "
            "a preceding date (such as effective date)."
        ),
        what_to_check="Review the timeline of performance and verify start and end dates.",
    ),
    "effective_date_conflict": FindingTypeInfo(
        type="effective_date_conflict",
        category="inconsistency",
        title="Multiple or conflicting effective dates",
        what_it_means=(
            "The agreement specifies contradictory effective dates in different provisions or recitals."
        ),
        what_to_check="Determine which effective date governs the agreement.",
    ),
    "term_length_conflict": FindingTypeInfo(
        type="term_length_conflict",
        category="inconsistency",
        title="Stated term contradicts date span",
        what_it_means=(
            "The explicitly stated contract duration contradicts the calculated time between start and expiration dates."
        ),
        what_to_check="Clarify whether the fixed duration or the calendar expiration date prevails.",
    ),
    "party_name_variant": FindingTypeInfo(
        type="party_name_variant",
        category="inconsistency",
        title="Inconsistent party name or spelling",
        what_it_means=(
            "A contracting party entity name is written with variant spellings or corporate suffixes "
            "across different clauses."
        ),
        what_to_check="Verify the legal entity name against corporate registry documents.",
    ),
    "unknown_party_entity": FindingTypeInfo(
        type="unknown_party_entity",
        category="inconsistency",
        title="Unidentified contracting entity",
        what_it_means=(
            "An entity name appears in an operative clause but was not introduced in the preamble or party recitals."
        ),
        what_to_check="Check if the entity is an affiliate, guarantor, or an accidental drafting carryover.",
    ),
    "dangling_reference": FindingTypeInfo(
        type="dangling_reference",
        category="inconsistency",
        title="Cross-reference to non-existent clause",
        what_it_means=(
            "A clause cites a specific section or clause number that does not exist in the contract."
        ),
        what_to_check="Locate the intended target section and correct the cross-reference number.",
    ),
    "duplicate_clause_number": FindingTypeInfo(
        type="duplicate_clause_number",
        category="inconsistency",
        title="Duplicate clause numbering",
        what_it_means=(
            "Multiple sections share the same clause number, creating ambiguity in cross-references."
        ),
        what_to_check="Renumber conflicting clauses and update any dependent citations.",
    ),
    "numbering_gap": FindingTypeInfo(
        type="numbering_gap",
        category="inconsistency",
        title="Missing or skipped clause number",
        what_it_means=(
            "The clause numbering skips one or more numbers in sequence, which may indicate a deleted section."
        ),
        what_to_check="Verify whether a provision was intentionally omitted or mistakenly removed.",
    ),
}


def get_finding_type_info(finding_type: str, module: str | None = None) -> FindingTypeInfo:
    """Retrieve catalog definition for a finding type with graceful fallback."""
    if finding_type in CATALOG:
        return CATALOG[finding_type]

    # Graceful fallback for unknown finding types
    is_tampering = (module and "forensic" in module.lower()) or "tamper" in finding_type.lower()
    cat: FindingCategory = "tampering" if is_tampering else "inconsistency"
    human_title = finding_type.replace("_", " ").strip().capitalize()
    return FindingTypeInfo(
        type=finding_type,
        category=cat,
        title=human_title,
        what_it_means="An issue was detected by an automated integrity check that requires human inspection.",
        what_to_check="Inspect the marked clause text and related contract provisions.",
    )


def get_catalog() -> dict[str, FindingTypeInfo]:
    """Return the complete finding catalog."""
    return CATALOG
