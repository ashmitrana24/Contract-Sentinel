"""BM25 retrieval engine with clause-label boosting, follow-up expansion, and overview mode."""

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


def tokenize(text: str) -> list[str]:
    """Tokenize and normalize text for BM25 retrieval."""
    tokens = re.findall(r"\b[a-zA-Z0-9_]+\b", text.lower())
    return [t for t in tokens if len(t) > 1 and t not in STOPWORDS]


class BM25Index:
    """Fast, deterministic BM25Okapi inverted index over contract retrieval chunks."""

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

        # Index over combined heading and text
        self.doc_tokens: list[list[str]] = []
        for c in self.chunks:
            combined = f"{c.heading or ''} {c.text}"
            self.doc_tokens.append(tokenize(combined))

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
    ) -> list[tuple[RetrievalChunk, float]]:
        """Score and rank chunks for the query, applying optional chunk-level boosts."""
        if not self.chunks or self.N == 0:
            return []

        q_terms = tokenize(query)
        if not q_terms:
            return []

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

        # Apply label boosts if provided
        if label_boosts:
            for idx, c in enumerate(self.chunks):
                boost = label_boosts.get(c.clause_id, 1.0)
                if boost != 1.0:
                    scores[idx] *= boost

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
        # Extract non-stopword tokens from prior question
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
    label_boost_multiplier: float = 1.25,
    last_user_query: str | None = None,
    last_assistant_heading: str | None = None,
) -> RetrievalResult:
    """Execute end-to-end grounded retrieval for a user question."""
    expanded_query = expand_short_followup(
        query,
        last_user_query=last_user_query,
        last_assistant_heading=last_assistant_heading,
    )

    # 1. Check overview mode
    overview = is_overview_query(query)
    overview_block: str | None = None

    if overview:
        # Load risk summary, findings, and attributes
        risk_row = session.get(RiskSummaryRow, document_id)
        findings = session.execute(
            select(FindingRow)
            .where(FindingRow.document_id == document_id)
            .order_by(
                # Order critical first, then high, medium
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

    # 2. Build retrieval chunks from DB clauses and pages
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

    # 3. Compute question classification for label boosting
    question_labels: set[str] = set()
    try:
        preds = classify_clause(expanded_query)
        question_labels = {p["label"] for p in preds if p.get("score", 0.0) >= 0.3}
    except Exception as exc:
        logger.debug("Question classification failed: %s", exc)

    # Fetch clause labels for this document to build clause_id -> boost mapping
    label_boosts: dict[str, float] = {}
    if question_labels:
        db_labels = session.execute(
            select(ClauseLabelRow.clause_id, ClauseLabelRow.label)
            .where(ClauseLabelRow.document_id == document_id)
        ).all()
        for c_id, lbl in db_labels:
            if lbl in question_labels:
                label_boosts[c_id] = label_boost_multiplier

    # 4. Search BM25
    index = BM25Index(chunks)
    search_results = index.search(expanded_query, top_k=top_k, label_boosts=label_boosts)

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
