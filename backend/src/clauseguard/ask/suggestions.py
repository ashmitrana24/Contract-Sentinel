"""Dynamic document-specific question suggestions for ClauseGuard Ask."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from clauseguard.db.models import (
    ClauseLabelRow,
    Document,
    DocumentAttributeRow,
    FindingRow,
    RiskSummaryRow,
)
from clauseguard.schemas.api import AskSuggestion, AskSuggestionsResponse


def generate_document_suggestions(
    document_id: uuid.UUID,
    session: Session,
) -> AskSuggestionsResponse:
    """Generate 4-6 dynamic, document-tailored questions balanced across categories."""
    doc = session.get(Document, document_id)
    if not doc:
        return AskSuggestionsResponse(document_id=document_id, suggestions=[])

    key_terms: list[tuple[str, str, str | None]] = []
    obligations: list[tuple[str, str, str | None]] = []
    risks: list[tuple[str, str, str | None]] = []

    # 1. Attributes-based candidates
    attrs = session.get(DocumentAttributeRow, document_id)
    if attrs:
        if attrs.governing_law_jurisdiction:
            key_terms.append((
                f"What are the governing law and dispute resolution rules under {attrs.governing_law_jurisdiction} law?",
                "key_terms",
                None,
            ))
        if attrs.limitation_of_liability:
            key_terms.append((
                "How does the limitation of liability clause allocate damages and liability caps?",
                "key_terms",
                None,
            ))
        if attrs.payment_terms_days:
            key_terms.append((
                f"What are the invoice payment terms ({attrs.payment_terms_days} days) and consequences of late payment?",
                "key_terms",
                None,
            ))
        if attrs.termination_notice_days:
            obligations.append((
                f"What are the requirements and conditions for termination upon {attrs.termination_notice_days} days notice?",
                "obligations",
                None,
            ))
        if attrs.auto_renews:
            obligations.append((
                "What are the renewal terms and non-renewal notice deadlines for this contract?",
                "obligations",
                None,
            ))
        if attrs.non_compete_duration_months:
            obligations.append((
                f"What restrictions apply during the {attrs.non_compete_duration_months}-month non-compete period?",
                "obligations",
                None,
            ))

    # 2. Forensics & Consistency Findings
    findings = session.execute(
        select(FindingRow).where(FindingRow.document_id == document_id)
    ).scalars().all()

    hidden_found = any(
        f.module == "pdf_forensics" and f.type in {"white_on_white", "sub_1pt_font", "render_mode_3", "offpage_text", "occluded_text"}
        for f in findings
    )
    if hidden_found:
        risks.append((
            "Where was hidden or suspicious text detected in this contract and what does it say?",
            "risks",
            None,
        ))

    tamper_found = any(f.type in {"incremental_edit_amount", "post_signature_edit"} for f in findings)
    if tamper_found:
        risks.append((
            "What alterations or modifications were detected after the initial document creation?",
            "risks",
            None,
        ))

    ref_found = any("ref" in f.type or "citation" in f.type for f in findings)
    if ref_found:
        risks.append((
            "Which referenced clauses or schedule attachments were flagged as missing or unresolved?",
            "risks",
            None,
        ))

    # 3. Risk Summary Overview
    risk = session.get(RiskSummaryRow, document_id)
    if risk and risk.band in ("critical", "high", "medium"):
        risks.append((
            "Summarize the primary risk findings identified in the contract integrity analysis.",
            "risks",
            None,
        ))

    # Select balanced set: up to 2 from each group
    selected: list[tuple[str, str, str | None]] = []
    seen_q: set[str] = set()

    for pool in [risks, key_terms, obligations]:
        count = 0
        for item in pool:
            if count >= 2:
                break
            if item[0] not in seen_q:
                seen_q.add(item[0])
                selected.append(item)
                count += 1

    # If still under 4, pull remaining from pools
    if len(selected) < 4:
        for pool in [risks, key_terms, obligations]:
            for item in pool:
                if len(selected) >= 5:
                    break
                if item[0] not in seen_q:
                    seen_q.add(item[0])
                    selected.append(item)

    # 4. Standard fallback questions if still fewer than 4
    fallbacks = [
        ("Summarize the key commercial terms and obligations in this contract.", "general", None),
        ("What are the confidentiality and non-disclosure obligations?", "obligations", None),
        ("What representations, warranties, or indemnities are provided?", "obligations", None),
        ("What events constitute a default or breach of this agreement?", "risks", None),
    ]

    for item in fallbacks:
        if len(selected) >= 4:
            break
        if item[0] not in seen_q:
            seen_q.add(item[0])
            selected.append(item)

    # Limit to at most 6
    selected = selected[:6]

    suggestions = [
        AskSuggestion(
            id=f"sug_{idx + 1}",
            question=q,
            category=cat,
            target_clause_id=target,
        )
        for idx, (q, cat, target) in enumerate(selected)
    ]

    return AskSuggestionsResponse(document_id=document_id, suggestions=suggestions)
