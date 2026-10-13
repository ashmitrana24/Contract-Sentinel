"""Clause taxonomy for ClauseGuard Module 5.

Defines the 45-class taxonomy:
- 36 core contractual clause categories derived from CUAD v1.
- 9 additional unbenchmarked rule-only labels for high-value legal risk patterns.
5 document-level metadata categories from CUAD are explicitly excluded from clause classification.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

METADATA_CATEGORIES: frozenset[str] = frozenset({
    "Document Name",
    "Parties",
    "Agreement Date",
    "Effective Date",
    "Expiration Date",
})


@dataclass(frozen=True)
class LabelDefinition:
    """Definition of a clause label in the taxonomy."""

    id: str
    name: str
    description: str
    source: str  # 'cuad' or 'rule_only'
    cuad_category: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# Mapping from exact CUAD category names (36 contractual) to internal snake_case IDs.
CUAD_CATEGORY_TO_ID: dict[str, str] = {
    "Governing Law": "governing_law",
    "Renewal Term": "renewal_term",
    "Notice Period To Terminate Renewal": "notice_period_to_terminate_renewal",
    "Most Favored Nation": "most_favored_nation",
    "Non-Compete": "non_compete",
    "Exclusivity": "exclusivity",
    "No-Solicit Of Customers": "no_solicit_of_customers",
    "Competitive Restriction Exception": "competitive_restriction_exception",
    "No-Solicit Of Employees": "no_solicit_of_employees",
    "Non-Disparagement": "non_disparagement",
    "Termination For Convenience": "termination_for_convenience",
    "Rofr/Rofo/Rofn": "rofr_rofo_rofn",
    "Change Of Control": "change_of_control",
    "Anti-Assignment": "anti_assignment",
    "Revenue/Profit Sharing": "revenue_profit_sharing",
    "Price Restrictions": "price_restrictions",
    "Minimum Commitment": "minimum_commitment",
    "Volume Restriction": "volume_restriction",
    "Ip Ownership Assignment": "ip_ownership_assignment",
    "Joint Ip Ownership": "joint_ip_ownership",
    "License Grant": "license_grant",
    "Non-Transferable License": "non_transferable_license",
    "Affiliate License-Licensor": "affiliate_license_licensor",
    "Affiliate License-Licensee": "affiliate_license_licensee",
    "Unlimited/All-You-Can-Eat-License": "unlimited_all_you_can_eat_license",
    "Irrevocable Or Perpetual License": "irrevocable_or_perpetual_license",
    "Source Code Escrow": "source_code_escrow",
    "Post-Termination Services": "post_termination_services",
    "Audit Rights": "audit_rights",
    "Uncapped Liability": "uncapped_liability",
    "Cap On Liability": "cap_on_liability",
    "Liquidated Damages": "liquidated_damages",
    "Warranty Duration": "warranty_duration",
    "Insurance": "insurance",
    "Covenant Not To Sue": "covenant_not_to_sue",
    "Third Party Beneficiary": "third_party_beneficiary",
}

# 36 Core CUAD Contractual Labels
_CORE_DEFINITIONS: list[LabelDefinition] = [
    LabelDefinition(
        id="governing_law",
        name="Governing Law",
        description="Specifies jurisdiction, governing law, and legal forum applicable to the contract.",
        source="cuad",
        cuad_category="Governing Law",
    ),
    LabelDefinition(
        id="renewal_term",
        name="Renewal Term",
        description="Terms specifying automatic or elective extension and duration of renewal periods.",
        source="cuad",
        cuad_category="Renewal Term",
    ),
    LabelDefinition(
        id="notice_period_to_terminate_renewal",
        name="Notice Period To Terminate Renewal",
        description="Required notice timeframe to prevent automatic renewal or extension.",
        source="cuad",
        cuad_category="Notice Period To Terminate Renewal",
    ),
    LabelDefinition(
        id="most_favored_nation",
        name="Most Favored Nation",
        description="Guarantees pricing, terms, or conditions no less favorable than offered to others.",
        source="cuad",
        cuad_category="Most Favored Nation",
    ),
    LabelDefinition(
        id="non_compete",
        name="Non-Compete",
        description="Restricts a party from engaging in competitive business activities or markets.",
        source="cuad",
        cuad_category="Non-Compete",
    ),
    LabelDefinition(
        id="exclusivity",
        name="Exclusivity",
        description="Grants exclusive dealing, distribution, purchasing, or operational rights.",
        source="cuad",
        cuad_category="Exclusivity",
    ),
    LabelDefinition(
        id="no_solicit_of_customers",
        name="No-Solicit Of Customers",
        description="Restricts solicitation, enticement, or diversion of customers or clients.",
        source="cuad",
        cuad_category="No-Solicit Of Customers",
    ),
    LabelDefinition(
        id="competitive_restriction_exception",
        name="Competitive Restriction Exception",
        description="Carve-outs and exceptions to restrictive covenants or competition limitations.",
        source="cuad",
        cuad_category="Competitive Restriction Exception",
    ),
    LabelDefinition(
        id="no_solicit_of_employees",
        name="No-Solicit Of Employees",
        description="Restricts hiring, recruitment, or inducement of personnel and contractors.",
        source="cuad",
        cuad_category="No-Solicit Of Employees",
    ),
    LabelDefinition(
        id="non_disparagement",
        name="Non-Disparagement",
        description="Prohibits making negative, defamatory, or derogatory statements about a party.",
        source="cuad",
        cuad_category="Non-Disparagement",
    ),
    LabelDefinition(
        id="termination_for_convenience",
        name="Termination For Convenience",
        description="Right to terminate the contract at will without cause or breach upon notice.",
        source="cuad",
        cuad_category="Termination For Convenience",
    ),
    LabelDefinition(
        id="rofr_rofo_rofn",
        name="Right of First Refusal / Offer / Negotiation",
        description="Priority rights to purchase, license, or negotiate prior to third parties.",
        source="cuad",
        cuad_category="Rofr/Rofo/Rofn",
    ),
    LabelDefinition(
        id="change_of_control",
        name="Change Of Control",
        description="Provisions triggered by mergers, acquisitions, or shifts in controlling ownership.",
        source="cuad",
        cuad_category="Change Of Control",
    ),
    LabelDefinition(
        id="anti_assignment",
        name="Anti-Assignment",
        description="Restrictions or consent requirements for assignment or delegation of the contract.",
        source="cuad",
        cuad_category="Anti-Assignment",
    ),
    LabelDefinition(
        id="revenue_profit_sharing",
        name="Revenue / Profit Sharing",
        description="Clauses outlining allocation of profits, revenues, or royalties between parties.",
        source="cuad",
        cuad_category="Revenue/Profit Sharing",
    ),
    LabelDefinition(
        id="price_restrictions",
        name="Price Restrictions",
        description="Limitations on price increases, price parity, or mandated price calculation models.",
        source="cuad",
        cuad_category="Price Restrictions",
    ),
    LabelDefinition(
        id="minimum_commitment",
        name="Minimum Commitment",
        description="Minimum purchase, spend, or order volume commitments required of a party.",
        source="cuad",
        cuad_category="Minimum Commitment",
    ),
    LabelDefinition(
        id="volume_restriction",
        name="Volume Restriction",
        description="Quotas, maximum usage thresholds, or capacity caps on products or services.",
        source="cuad",
        cuad_category="Volume Restriction",
    ),
    LabelDefinition(
        id="ip_ownership_assignment",
        name="IP Ownership Assignment",
        description="Assignment or vesting of intellectual property rights and inventions.",
        source="cuad",
        cuad_category="Ip Ownership Assignment",
    ),
    LabelDefinition(
        id="joint_ip_ownership",
        name="Joint IP Ownership",
        description="Co-ownership arrangements for newly developed or shared intellectual property.",
        source="cuad",
        cuad_category="Joint Ip Ownership",
    ),
    LabelDefinition(
        id="license_grant",
        name="License Grant",
        description="Terms granting rights to use software, technology, trademarks, or IP.",
        source="cuad",
        cuad_category="License Grant",
    ),
    LabelDefinition(
        id="non_transferable_license",
        name="Non-Transferable License",
        description="Explicit limitation prohibiting transfer or sublicensing of granted rights.",
        source="cuad",
        cuad_category="Non-Transferable License",
    ),
    LabelDefinition(
        id="affiliate_license_licensor",
        name="Affiliate License (Licensor)",
        description="Extends licensor obligations or rights across corporate affiliates.",
        source="cuad",
        cuad_category="Affiliate License-Licensor",
    ),
    LabelDefinition(
        id="affiliate_license_licensee",
        name="Affiliate License (Licensee)",
        description="Permits corporate affiliates of the licensee to exercise granted license rights.",
        source="cuad",
        cuad_category="Affiliate License-Licensee",
    ),
    LabelDefinition(
        id="unlimited_all_you_can_eat_license",
        name="Unlimited / Enterprise License",
        description="Unrestricted enterprise-wide license without seat or deployment limitations.",
        source="cuad",
        cuad_category="Unlimited/All-You-Can-Eat-License",
    ),
    LabelDefinition(
        id="irrevocable_or_perpetual_license",
        name="Irrevocable Or Perpetual License",
        description="License grants that cannot be revoked or that continue indefinitely.",
        source="cuad",
        cuad_category="Irrevocable Or Perpetual License",
    ),
    LabelDefinition(
        id="source_code_escrow",
        name="Source Code Escrow",
        description="Deposit of source code with an independent escrow agent upon release triggers.",
        source="cuad",
        cuad_category="Source Code Escrow",
    ),
    LabelDefinition(
        id="post_termination_services",
        name="Post-Termination Services",
        description="Obligations to provide transition assistance or disengagement services post-expiry.",
        source="cuad",
        cuad_category="Post-Termination Services",
    ),
    LabelDefinition(
        id="audit_rights",
        name="Audit Rights",
        description="Rights to inspect, audit, or review books, records, facilities, or security.",
        source="cuad",
        cuad_category="Audit Rights",
    ),
    LabelDefinition(
        id="uncapped_liability",
        name="Uncapped Liability",
        description="Explicit exclusions from liability limits (e.g. gross negligence, willful misconduct).",
        source="cuad",
        cuad_category="Uncapped Liability",
    ),
    LabelDefinition(
        id="cap_on_liability",
        name="Cap On Liability",
        description="Monetary limits, aggregate caps, or fee-multiple caps on contractual liability.",
        source="cuad",
        cuad_category="Cap On Liability",
    ),
    LabelDefinition(
        id="liquidated_damages",
        name="Liquidated Damages",
        description="Pre-agreed financial penalties or damages payable upon specified breaches.",
        source="cuad",
        cuad_category="Liquidated Damages",
    ),
    LabelDefinition(
        id="warranty_duration",
        name="Warranty Duration",
        description="Length and scope of product, service, or representation warranty coverage.",
        source="cuad",
        cuad_category="Warranty Duration",
    ),
    LabelDefinition(
        id="insurance",
        name="Insurance",
        description="Mandated types, coverage levels, and maintenance of insurance policies.",
        source="cuad",
        cuad_category="Insurance",
    ),
    LabelDefinition(
        id="covenant_not_to_sue",
        name="Covenant Not To Sue",
        description="Agreement refraining from instituting legal proceedings or patent claims.",
        source="cuad",
        cuad_category="Covenant Not To Sue",
    ),
    LabelDefinition(
        id="third_party_beneficiary",
        name="Third Party Beneficiary",
        description="Provisions conferring or disclaiming enforceable rights to third parties.",
        source="cuad",
        cuad_category="Third Party Beneficiary",
    ),
]

# 9 Additional Unbenchmarked Rule-Only Labels
_EXTRA_DEFINITIONS: list[LabelDefinition] = [
    LabelDefinition(
        id="indemnification",
        name="Indemnification",
        description="Obligation to defend, hold harmless, and indemnify against third-party claims.",
        source="rule_only",
    ),
    LabelDefinition(
        id="confidentiality",
        name="Confidentiality",
        description="Protection, non-disclosure, and authorized handling of proprietary information.",
        source="rule_only",
    ),
    LabelDefinition(
        id="payment_terms",
        name="Payment Terms",
        description="Invoicing frequency, payment due windows (e.g. Net 30), and interest on late fees.",
        source="rule_only",
    ),
    LabelDefinition(
        id="unilateral_amendment",
        name="Unilateral Amendment",
        description="Right of one party to unilaterally modify or update terms without mutual agreement.",
        source="rule_only",
    ),
    LabelDefinition(
        id="force_majeure",
        name="Force Majeure",
        description="Suspension of contractual obligations during unforeseeable catastrophic events.",
        source="rule_only",
    ),
    LabelDefinition(
        id="arbitration_or_dispute_resolution",
        name="Dispute Resolution & Arbitration",
        description="Mandatory arbitration, mediation, or structured escalation procedures.",
        source="rule_only",
    ),
    LabelDefinition(
        id="waiver_of_rights",
        name="Waiver Of Rights",
        description="Waiver of jury trial, class actions, or rights arising from failure to enforce terms.",
        source="rule_only",
    ),
    LabelDefinition(
        id="termination_for_cause",
        name="Termination For Cause",
        description="Rights to terminate immediately upon material breach, insolvency, or default.",
        source="rule_only",
    ),
    LabelDefinition(
        id="auto_renewal",
        name="Auto-Renewal / Evergreen",
        description="Evergreen clauses specifying automatic successive renewals unless timely terminated.",
        source="rule_only",
    ),
]

CORE_CUAD_LABELS: tuple[str, ...] = tuple(d.id for d in _CORE_DEFINITIONS)
EXTRA_RULE_LABELS: tuple[str, ...] = tuple(d.id for d in _EXTRA_DEFINITIONS)

ALL_DEFINITIONS: tuple[LabelDefinition, ...] = tuple(_CORE_DEFINITIONS + _EXTRA_DEFINITIONS)
ALL_LABELS: tuple[str, ...] = tuple(d.id for d in ALL_DEFINITIONS)

LABEL_MAP: dict[str, LabelDefinition] = {d.id: d for d in ALL_DEFINITIONS}


def get_label_definition(label_id: str) -> LabelDefinition | None:
    """Retrieve full label definition by id."""
    return LABEL_MAP.get(label_id)


def is_cuad_label(label_id: str) -> bool:
    """Check if label id belongs to core CUAD benchmarked classes."""
    defn = LABEL_MAP.get(label_id)
    return defn is not None and defn.source == "cuad"


def normalize_category_to_label(category_name: str) -> str | None:
    """Convert CUAD category name to snake_case label id, or None if metadata or unknown."""
    if category_name in METADATA_CATEGORIES:
        return None
    return CUAD_CATEGORY_TO_ID.get(category_name)
