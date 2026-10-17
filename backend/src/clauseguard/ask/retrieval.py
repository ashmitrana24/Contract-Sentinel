"""Pure-Python BM25Okapi retrieval engine for ClauseGuard Ask."""

from __future__ import annotations

import logging
import math
import re
from dataclasses import dataclass
from typing import Any, Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from clauseguard.ask.chunking import RetrievalChunk, build_retrieval_chunks
from clauseguard.clauses.model import classify_clause
from clauseguard.clauses.taxonomy import normalize_category_to_label
from clauseguard.db.models import (
    Clause,
    ClauseLabelRow,
    DocumentAttributeRow,
    FindingRow,
    Page,
    RiskSummaryRow,
)

logger = logging.getLogger(__name__)

STOPWORDS = {
    "a", "an", "the", "and", "or", "of", "to", "in", "is", "for", "on", "with", "as",
    "by", "at", "from", "it", "this", "that", "are", "be", "was", "under", "shall",
    "will", "which", "what", "where", "how", "who", "when", "does", "do", "any",
}

# Legal phrase & synonym expansions for the 18 core legal intents
INTENT_SYNONYMS: dict[str, list[str]] = {
    "termination_for_convenience": [
        "terminate for convenience", "termination without cause", "terminate at will",
        "cancel agreement", "end the agreement", "notice of termination", "right to terminate",
        "without cause", "prior written notice of termination",
    ],
    "governing_law": [
        "governing law", "choice of law", "jurisdiction", "construed in accordance with",
        "laws of the state", "applicable law", "exclusive jurisdiction", "venue",
    ],
    "cap_on_liability": [
        "limitation of liability", "liability cap", "aggregate liability", "damages cap",
        "in no event shall liability exceed", "consequential damages", "indirect damages",
        "maximum liability", "aggregate direct damages",
    ],
    "uncapped_liability": [
        "unlimited liability", "uncapped liability", "no limitation of liability",
        "gross negligence", "willful misconduct", "indemnification obligations shall not be subject to",
        "fraud intentional misrepresentation",
    ],
    "anti_assignment": [
        "assignment", "assign", "neither party may assign", "without prior written consent",
        "transfer of rights", "successor and permitted assigns", "subcontracting",
    ],
    "change_of_control": [
        "change of control", "merger", "acquisition", "sale of substantially all assets",
        "consolidation", "reorganization", "controlling interest",
    ],
    "non_compete": [
        "non-compete", "covenant not to compete", "restrictive covenant",
        "shall not engage in competing business", "non-competition", "restraint of trade",
    ],
    "audit_rights": [
        "audit", "inspection", "books and records", "right to inspect", "audit rights",
        "examine books", "independent certified public accountant",
    ],
    "insurance": [
        "insurance", "commercial general liability", "worker's compensation", "policy limits",
        "errors and omissions", "certificate of insurance", "umbrella liability",
    ],
    "ip_ownership_assignment": [
        "intellectual property", "inventions", "work made for hire", "assignment of patents",
        "proprietary rights", "work product", "patent rights", "copyright assignment",
    ],
    "license_grant": [
        "license grant", "grant of license", "non-exclusive license", "worldwide royalty-free",
        "perpetual license", "revocable license", "right and license", "sublicensable",
    ],
    "confidentiality": [
        "confidential information", "non-disclosure", "proprietary information", "trade secrets",
        "confidentiality obligations", "duty of confidentiality", "standard of care",
    ],
    "exclusivity": [
        "exclusive", "exclusivity", "sole provider", "sole and exclusive",
        "exclusive remedy", "exclusive right", "non-exclusive",
    ],
    "most_favored_nation": [
        "most favored nation", "mfn", "pricing terms no less favorable",
        "most favored customer", "favorable terms", "competitive pricing",
    ],
    "volume_restriction": [
        "minimum commitment", "volume restriction", "purchase obligation",
        "minimum purchase", "quota", "minimum volume",
    ],
    "price_restriction": [
        "price restriction", "price cap", "price adjustment", "price increase",
        "fee schedule", "pricing restrictions", "discount",
    ],
    "price_restrictions": [
        "price restriction", "price cap", "price adjustment", "price increase",
        "fee schedule", "pricing restrictions", "discount",
    ],
    "post_termination_services": [
        "transition services", "post-termination assistance", "wind-down",
        "termination assistance", "return of materials", "post-termination obligations",
    ],
    "indemnification": [
        "indemnify", "indemnification", "hold harmless", "defend and hold harmless",
        "indemnified party", "indemnitor", "defense of claims",
    ],
}


def tokenize(text: str) -> list[str]:
    """Tokenize and normalize text for BM25 retrieval."""
    tokens = re.findall(r"\b[a-zA-Z0-9_]+\b", text.lower())
    return [t for t in tokens if len(t) > 1 and t not in STOPWORDS]


def expand_intent_query(query: str) -> tuple[str, set[str]]:
    """Detect legal intent from query and expand with domain synonyms."""
    q_lower = query.lower()
    matched_intents: set[str] = set()

    for intent in INTENT_SYNONYMS:
        intent_clean = intent.replace("_", " ")
        if intent_clean in q_lower:
            matched_intents.add(intent)

    # Specific keyword triggers
    if any(k in q_lower for k in ("terminat", "cancel", "end the agreement", "convenience")):
        matched_intents.add("termination_for_convenience")
    if any(k in q_lower for k in ("governing law", "jurisdiction", "choice of law", "what state", "which state")):
        matched_intents.add("governing_law")
    if any(k in q_lower for k in ("liability", "cap on liability", "damages limit", "maximum liability")):
        matched_intents.add("cap_on_liability")
    if any(k in q_lower for k in ("unlimited liability", "uncapped", "no cap")):
        matched_intents.add("uncapped_liability")
    if any(k in q_lower for k in ("assign", "assignment", "transfer rights")):
        matched_intents.add("anti_assignment")
    if any(k in q_lower for k in ("change of control", "merger", "acquisition")):
        matched_intents.add("change_of_control")
    if any(k in q_lower for k in ("non-compete", "compete", "competition")):
        matched_intents.add("non_compete")
    if any(k in q_lower for k in ("audit", "inspection", "inspect books")):
        matched_intents.add("audit_rights")
    if any(k in q_lower for k in ("insurance", "policy limit")):
        matched_intents.add("insurance")
    if any(k in q_lower for k in ("intellectual property", "ip", "patent", "invention")):
        matched_intents.add("ip_ownership_assignment")
    if any(k in q_lower for k in ("license", "grant of license")):
        matched_intents.add("license_grant")
    if any(k in q_lower for k in ("confidential", "nda", "trade secret")):
        matched_intents.add("confidentiality")
    if any(k in q_lower for k in ("exclusive", "exclusivity")):
        matched_intents.add("exclusivity")
    if any(k in q_lower for k in ("most favored", "mfn")):
        matched_intents.add("most_favored_nation")
    if any(k in q_lower for k in ("indemnif", "hold harmless")):
        matched_intents.add("indemnification")
    if any(k in q_lower for k in ("volume", "quota", "minimum purchase")):
        matched_intents.add("volume_restriction")
    if any(k in q_lower for k in ("price", "pricing", "fee increase")):
        matched_intents.add("price_restrictions")
    if any(k in q_lower for k in ("post-termination", "transition services", "wind-down")):
        matched_intents.add("post_termination_services")

    expansion_terms: list[str] = []
    for intent in matched_intents:
        syns = INTENT_SYNONYMS.get(intent, [])
        if syns:
            expansion_terms.extend(syns[:3])

    if expansion_terms:
        expanded_query = f"{query} {' '.join(expansion_terms)}"
    else:
        expanded_query = query

    return expanded_query, matched_intents


class BM25Index:
    """Fast, deterministic BM25Okapi inverted index with heading and label boosts."""

    def __init__(
        self,
        chunks: Sequence[RetrievalChunk],
        k1: float = 1.5,
        b: float = 0.75,
    ) -> None:
        self.chunks = list(chunks)
        self.k1 = k1
        self.b = b
        self.N = len(self.chunks)

        self.doc_tokens: list[list[str]] = []
        self.heading_tokens: list[set[str]] = []

        for c in self.chunks:
            combined = f"{c.heading or ''} {c.text}"
            self.doc_tokens.append(tokenize(combined))
            self.heading_tokens.append(set(tokenize(c.heading or "")))

        self.doc_lens = [len(toks) for toks in self.doc_tokens]
        self.avgdl = (sum(self.doc_lens) / max(1, self.N)) if self.N > 0 else 1.0

        # Term frequencies and document frequencies
        self.tf: list[dict[str, int]] = []
        self.df: dict[str, int] = {}
        for toks in self.doc_tokens:
            counts: dict[str, int] = {}
            for t in toks:
                counts[t] = counts.get(t, 0) + 1
            self.tf.append(counts)
            for t in counts:
                self.df[t] = self.df.get(t, 0) + 1

        # IDFs
        self.idf: dict[str, float] = {}
        for term, freq in self.df.items():
            self.idf[term] = math.log((self.N - freq + 0.5) / (freq + 0.5) + 1.0)

    def search(
        self,
        query: str,
        top_k: int = 5,
        label_boosts: dict[str, float] | None = None,
        heading_boost_factor: float = 1.35,
    ) -> list[tuple[RetrievalChunk, float]]:
        """Score and rank chunks for the query, applying heading and label boosts."""
        if not self.chunks or self.N == 0:
            return []

        q_terms = tokenize(query)
        if not q_terms:
            return []

        q_term_set = set(q_terms)
        scores: list[float] = [0.0] * self.N

        for term in q_terms:
            idf_val = self.idf.get(term, 0.0)
            if idf_val <= 0:
                continue

            for idx in range(self.N):
                freq = self.tf[idx].get(term, 0)
                if freq > 0:
                    numerator = freq * (self.k1 + 1.0)
                    denominator = freq + self.k1 * (1.0 - self.b + self.b * (self.doc_lens[idx] / self.avgdl))
                    scores[idx] += idf_val * (numerator / denominator)

        # Apply heading match boost and stored label boost
        for idx, c in enumerate(self.chunks):
            # 1. Heading match boost
            if heading_boost_factor > 1.0 and self.heading_tokens[idx]:
                overlap = len(self.heading_tokens[idx].intersection(q_term_set))
                if overlap > 0:
                    scores[idx] *= 1.0 + (heading_boost_factor - 1.0) * min(3, overlap)

            # 2. Stored Module 5 predicted label boost
            if label_boosts:
                boost = label_boosts.get(c.clause_id, 1.0)
                if boost > 1.0:
                    if scores[idx] > 0.0:
                        scores[idx] *= boost
                    else:
                        # Prior baseline for matching label even if unigrams differed
                        scores[idx] = 0.25 * boost

        ranked = sorted(enumerate(scores), key=lambda x: x[1], reverse=True)
        return [(self.chunks[idx], score) for idx, score in ranked[:top_k] if score > 0.0]


OVERVIEW_QUERY_RE = re.compile(
    r"\b(summariz\w*|overview|main\s+risk\w*|key\s+risk\w*|primary\s+risk\w*|risk\s+summar\w*|findings|red\s+flag\w*)\b",
    re.IGNORECASE,
)


def is_overview_query(query: str) -> bool:
    """Detect if question is requesting a high-level risk overview."""
    q_lower = query.lower().strip()
    if q_lower in {"summarize the risks", "what are the main risks?", "what are the risks", "risk overview"}:
        return True
    return bool(OVERVIEW_QUERY_RE.search(q_lower))


def expand_short_followup(
    query: str,
    last_user_query: str | None = None,
    last_assistant_heading: str | None = None,
) -> str:
    """Expand short follow-up questions (< 6 words) with prior context keywords."""
    words = query.strip().split()
    if len(words) >= 6:
        return query

    context_additions: list[str] = []
    if last_assistant_heading:
        context_additions.append(last_assistant_heading)
    if last_user_query:
        prior_terms = tokenize(last_user_query)
        if prior_terms:
            context_additions.append(" ".join(prior_terms[:3]))

    if context_additions:
        return f"{query} ({' '.join(context_additions)})"
    return query


@dataclass(frozen=True)
class RetrievalResult:
    """Result of retrieval engine execution."""

    chunks: list[RetrievalChunk]
    scores: list[float]
    is_overview: bool = False
    overview_block: str | None = None
    has_sufficient_evidence: bool = True


def retrieve_evidence(
    document_id: Any,
    query: str,
    *,
    session: Session,
    top_k: int = 5,
    min_score_threshold: float = 0.05,
    label_boost_multiplier: float = 1.75,
    heading_boost_factor: float = 1.35,
    last_user_query: str | None = None,
    last_assistant_heading: str | None = None,
) -> RetrievalResult:
    """Execute end-to-end grounded retrieval for a user question."""
    # 1. Expand short follow-ups and intent synonyms
    followup_query = expand_short_followup(
        query,
        last_user_query=last_user_query,
        last_assistant_heading=last_assistant_heading,
    )
    expanded_query, detected_intents = expand_intent_query(followup_query)

    # 2. Check overview mode
    overview = is_overview_query(query)
    overview_block: str | None = None

    if overview:
        risk_row = session.get(RiskSummaryRow, document_id)
        findings = session.execute(
            select(FindingRow)
            .where(FindingRow.document_id == document_id)
            .order_by(
                FindingRow.severity.desc(),
                FindingRow.created_at.asc(),
            )
            .limit(3)
        ).scalars().all()
        attrs = session.get(DocumentAttributeRow, document_id)

        blocks = []
        if risk_row:
            blocks.append(f"OVERALL RISK BAND: {risk_row.band.upper()} (Score: {risk_row.score}/100)")
            summary_dict = risk_row.summary or {}
            headline = summary_dict.get("headline", "")
            if headline:
                blocks.append(f"HEADLINE: {headline}")

        if findings:
            blocks.append("TOP INTEGRITY & FORENSICS FINDINGS:")
            for f in findings:
                blocks.append(f"- [{f.severity.upper()}] {f.type}: {f.explanation} (Evidence: '{f.evidence}')")

        if attrs:
            blocks.append("CONTRACT KEY ATTRIBUTES:")
            if attrs.governing_law_jurisdiction:
                blocks.append(f"- Governing Law: {attrs.governing_law_jurisdiction}")
            if attrs.termination_notice_days:
                blocks.append(f"- Termination Notice: {attrs.termination_notice_days} days")
            if attrs.liability_cap:
                blocks.append(f"- Liability Cap: {attrs.liability_cap}")
            if attrs.limitation_of_liability:
                blocks.append(f"- Limitation of Liability: {attrs.limitation_of_liability.get('type')}")

        overview_block = "\n".join(blocks)

    # 3. Build retrieval chunks from DB clauses and pages
    db_clauses = session.execute(
        select(Clause).where(Clause.document_id == document_id).order_by(Clause.order_idx.asc())
    ).scalars().all()

    db_pages = session.execute(
        select(Page).where(Page.document_id == document_id).order_by(Page.page_no.asc())
    ).scalars().all()

    chunks = build_retrieval_chunks(db_clauses, pages=db_pages)
    if not chunks:
        return RetrievalResult(
            chunks=[],
            scores=[],
            is_overview=overview,
            overview_block=overview_block,
            has_sufficient_evidence=bool(overview_block),
        )

    # 4. Fetch stored predicted clause labels from Module 5
    label_boosts: dict[str, float] = {}
    if detected_intents:
        db_labels = session.execute(
            select(ClauseLabelRow.clause_id, ClauseLabelRow.label)
            .where(ClauseLabelRow.document_id == document_id)
        ).all()
        for c_id, lbl in db_labels:
            if lbl in detected_intents:
                label_boosts[str(c_id)] = label_boost_multiplier

    # 5. Search BM25 with heading and label boosts
    index = BM25Index(chunks)
    search_results = index.search(
        expanded_query,
        top_k=top_k,
        label_boosts=label_boosts,
        heading_boost_factor=heading_boost_factor,
    )

    retrieved_chunks = [c for c, _score in search_results]
    scores = [score for _c, score in search_results]

    has_evidence = False
    if overview and overview_block:
        has_evidence = True
    elif scores and max(scores) >= min_score_threshold:
        has_evidence = True

    return RetrievalResult(
        chunks=retrieved_chunks,
        scores=scores,
        is_overview=overview,
        overview_block=overview_block,
        has_sufficient_evidence=has_evidence,
    )
