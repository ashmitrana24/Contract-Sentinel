"""Answer generation and grounding verification pipeline for ClauseGuard Ask."""

from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass, field
from typing import Any, Sequence

from sqlalchemy.orm import Session

from clauseguard.ask.chunking import RetrievalChunk
from clauseguard.ask.privacy import (
    AEQI_SYSTEM_PROMPT,
    redact_sensitive_pii,
    restore_sensitive_pii,
    sanitize_contract_context,
)
from clauseguard.ask.retrieval import RetrievalResult, retrieve_evidence
from clauseguard.config import Settings
from clauseguard.llm import LLMProvider, get_provider
from clauseguard.schemas.api import Citation

import unicodedata

logger = logging.getLogger(__name__)

CLAUSE_CITE_RE = re.compile(r"\[(?:Clause|c)?\s*([a-zA-Z0-9_.-]+)\]", re.IGNORECASE)
QUOTE_RE = re.compile(r'"([^"\n]{6,})"')
MONEY_RE = re.compile(r"\$[0-9,]+(?:\.[0-9]{2})?")

ABSTENTION_PHRASES = (
    "the contract does not say",
    "the contract does not contain",
    "the contract does not mention",
    "the contract does not specify",
    "the agreement does not specify",
    "the agreement does not contain",
    "the provided contract excerpts do not contain",
    "the provided contract excerpts do not",
    "the provided excerpts do not",
    "no information is provided regarding",
    "there is no mention of",
)


def normalize_for_verification(text: str) -> str:
    """Canonical Unicode normalisation for quote and numeric grounding verification.

    Applies:
    1. NFKC normalisation
    2. Maps hyphen and minus variants (U+2010 to U+2015, U+2212) to "-"
    3. Maps non-breaking & thin spaces to standard ASCII space " "
    4. Maps curly quotes to straight quotes
    5. Collapses whitespace
    """
    if not text:
        return ""
    # 1. NFKC
    t = unicodedata.normalize("NFKC", text)
    # 2. Map all hyphen and minus variants to "-"
    t = re.sub(r"[\u2010\u2011\u2012\u2013\u2014\u2015\u2212]", "-", t)
    # 3. Non-breaking, thin, and mathematical spaces to standard space
    t = re.sub(r"[\u00A0\u2000-\u200B\u202F\u3000]", " ", t)
    # 4. Curly quotes to straight
    t = re.sub(r"[\u2018\u2019\u201A\u201B]", "'", t)
    t = re.sub(r"[\u201C\u201D\u201E\u201F\u00AB\u00BB]", '"', t)
    # 5. Collapse whitespace
    return " ".join(t.split())


def strip_markdown(text: str) -> str:
    """Strip markdown formatting (**, *, `, __, _) from text."""
    if not text:
        return ""
    t = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)
    t = re.sub(r"\*([^*]+)\*", r"\1", text)
    t = re.sub(r"__([^_]+)__", r"\1", text)
    t = re.sub(r"_([^_]+)_", r"\1", t)
    t = re.sub(r"`([^`]+)`", r"\1", t)
    t = t.replace("**", "").replace("*", "").replace("`", "")
    return t


def is_abstention_answer(text: str) -> bool:
    """Check if an answer explicitly states that the contract does not contain the requested information."""
    if not text:
        return False
    norm = normalize_for_verification(text).lower()
    if norm.startswith("the contract does not say"):
        return True
    return any(p in norm for p in ABSTENTION_PHRASES)


@dataclass(frozen=True)
class GroundingVerificationResult:
    """Outcome of grounding checks on generated answer."""

    is_grounded: bool
    unverified_clause_ids: list[str]
    unverified_quotes: list[str]
    unverified_monetary_amounts: list[str]
    warnings: list[str]
    kind: str = "answered"  # "answered" | "abstention"
    unrecognized_citations: list[str] = field(default_factory=list)


def verify_grounding(
    answer_text: str,
    retrieved_chunks: Sequence[RetrievalChunk],
    overview_block: str | None = None,
) -> GroundingVerificationResult:
    """Verify that cited clauses, verbatim quotes, and numeric amounts exist in context.

    Abstentions require no citations and are marked verified with kind='abstention'.
    Quote and number comparisons apply canonical Unicode normalisation, markdown stripping,
    ellipsis segment splitting, negation-omission checks, and parenthetical citation mapping.
    """
    if is_abstention_answer(answer_text):
        return GroundingVerificationResult(
            is_grounded=True,
            unverified_clause_ids=[],
            unverified_quotes=[],
            unverified_monetary_amounts=[],
            warnings=[],
            kind="abstention",
            unrecognized_citations=[],
        )

    valid_clause_ids = {normalize_for_verification(c.clause_id).lower() for c in retrieved_chunks}
    valid_chunk_ids = {normalize_for_verification(c.chunk_id).lower() for c in retrieved_chunks}
    valid_headings = {}
    for c in retrieved_chunks:
        if c.heading:
            valid_headings[normalize_for_verification(c.heading).lower()] = c.clause_id

    combined_context = "\n".join(f"{c.heading or ''} {c.text}" for c in retrieved_chunks)
    if overview_block:
        combined_context += "\n" + overview_block
    norm_context = normalize_for_verification(combined_context)
    norm_context_clean = strip_markdown(norm_context)
    norm_context_lower = norm_context_clean.lower()

    warnings: list[str] = []
    unrecognized_cites: list[str] = []

    # 1. Check cited clause IDs (bracketed [c1] or mapped parenthetical (Section 2))
    cited_ids = CLAUSE_CITE_RE.findall(answer_text)
    unverified_ids: list[str] = []
    for cid in cited_ids:
        clean_cid = normalize_for_verification(cid.strip()).lower()
        if clean_cid not in valid_clause_ids and clean_cid not in valid_chunk_ids:
            unverified_ids.append(cid)
            warnings.append(f"Cited clause '[{cid}]' is not in retrieved evidence.")

    # Parentheses citations like (Section 2) or (Clause 5)
    paren_cites = re.findall(
        r"\((?:Section|Clause|c)?\s*([a-zA-Z0-9_.-]+(?:\s+[a-zA-Z0-9_.-]+)?)\)",
        answer_text,
        re.IGNORECASE,
    )
    for pcite in paren_cites:
        p_clean = normalize_for_verification(pcite.strip()).lower()
        # Skip pure numeric/enumerator parentheticals like (12), (30), (a), (b), (i), (ii)
        if re.match(r"^(?:\d+|[a-zA-Z]|[ivxIVX]+)$", p_clean) and p_clean not in valid_clause_ids and p_clean not in valid_chunk_ids:
            continue
        if p_clean in valid_clause_ids or p_clean in valid_chunk_ids or p_clean in valid_headings:
            # Mapped successfully to excerpt ID or heading
            pass
        elif any(p_clean in h for h in valid_headings):
            pass
        else:
            unrecognized_cites.append(f"({pcite})")
            warnings.append(f"Unrecognized citation: '({pcite})'")

    # 2. Check verbatim quotes (>= 6 chars) with markdown stripping and ellipsis splitting
    norm_answer = normalize_for_verification(answer_text)
    quotes = QUOTE_RE.findall(norm_answer)
    unverified_quotes: list[str] = []
    negation_words = {"not", "no", "never", "without", "neither"}

    for raw_q in quotes:
        q_clean = strip_markdown(normalize_for_verification(raw_q)).strip()
        norm_q_lower = q_clean.lower()
        if len(norm_q_lower) < 6:
            continue

        # Case 1: Exact verbatim substring match
        if norm_q_lower in norm_context_lower:
            continue

        # Case 2: Ellipsis-shortened quote
        ellipsis_split = re.split(r"(?:\.\.\.|\u2026|\.\s+\.\s+\.)", q_clean)
        segments = [s.strip() for s in ellipsis_split if s.strip()]

        if len(segments) > 1:
            all_segs_found = True
            positions: list[tuple[int, int]] = []
            search_start = 0

            for seg in segments:
                seg_lower = seg.lower()
                pos = norm_context_lower.find(seg_lower, search_start)
                if pos == -1:
                    all_segs_found = False
                    break
                positions.append((pos, len(seg_lower)))
                search_start = pos + len(seg_lower)

            if not all_segs_found:
                unverified_quotes.append(raw_q)
                warnings.append(f"Quote segments in \"{raw_q}\" do not appear sequentially in retrieved text.")
                continue

            # Check omitted gaps in the source text for dropped negation words
            meaning_altered = False
            for i in range(len(positions) - 1):
                gap_start = positions[i][0] + positions[i][1]
                gap_end = positions[i + 1][0]
                gap_text = norm_context_lower[gap_start:gap_end]
                gap_tokens = set(re.findall(r"\b[a-z]+\b", gap_text))
                dropped_negations = gap_tokens.intersection(negation_words)
                if dropped_negations:
                    meaning_altered = True
                    warnings.append(
                        f"Shortened quote omitted negation word(s) {dropped_negations}, altering meaning: \"{raw_q}\"."
                    )
                    break

            if meaning_altered:
                unverified_quotes.append(raw_q)
                continue

            # Ellipsis quote matched sequentially without altering negations
            continue

        # Verbatim quote not found
        unverified_quotes.append(raw_q)
        warnings.append(f"Quote \"{raw_q}\" does not match retrieved text verbatim.")

    # 3. Check monetary figures with Unicode normalisation
    money_amounts = MONEY_RE.findall(norm_answer)
    unverified_money: list[str] = []
    for m in money_amounts:
        norm_m_lower = normalize_for_verification(m).lower()
        if norm_m_lower not in norm_context_lower:
            unverified_money.append(m)
            warnings.append(f"Monetary amount '{m}' not found in contract text.")

    is_grounded = len(unverified_ids) == 0 and len(unverified_quotes) == 0 and len(unverified_money) == 0

    return GroundingVerificationResult(
        is_grounded=is_grounded,
        unverified_clause_ids=unverified_ids,
        unverified_quotes=unverified_quotes,
        unverified_monetary_amounts=unverified_money,
        warnings=warnings,
        kind="answered",
        unrecognized_citations=unrecognized_cites,
    )



def build_citations(chunks: Sequence[RetrievalChunk]) -> list[Citation]:
    """Convert retrieved chunks into API Citation models."""
    citations: list[Citation] = []
    for c in chunks:
        snip = c.text.strip().split("\n")[0]
        if len(snip) > 200:
            snip = snip[:197] + "..."
        citations.append(
            Citation(
                chunk_id=c.chunk_id,
                clause_id=c.clause_id,
                heading=c.heading,
                page=c.page_start,
                text_snippet=snip,
            )
        )
    return citations


def construct_prompt(
    question: str,
    retrieval: RetrievalResult,
    hidden_findings: Sequence[Any] | None = None,
) -> tuple[str, bool]:
    """Build the complete, delimited user prompt for the LLM and return (prompt, hidden_text_excluded)."""
    chunk_texts = [f"[{c.chunk_id}] {c.heading + ': ' if c.heading else ''}{c.text}" for c in retrieval.chunks]
    context_block, hidden_excluded = sanitize_contract_context(chunk_texts, hidden_findings=hidden_findings)

    parts: list[str] = []
    if retrieval.is_overview and retrieval.overview_block:
        parts.append(f"<contract_overview>\n{retrieval.overview_block}\n</contract_overview>\n")

    parts.append(context_block)
    parts.append(
        f"\nUSER QUESTION: {question}\n\n"
        "Provide a concise, grounded answer based strictly on the excerpts above. "
        "Cite the relevant clause bracket e.g. [1.1] or [c1.w0]. "
        "Quote verbatim terms of >= 6 characters in double quotes. "
        "If the excerpts do not contain the answer, begin your reply with: "
        "'The contract does not say' followed by a short clause naming what was looked for."
    )
    return "\n".join(parts), hidden_excluded


@dataclass(frozen=True)
class AnswerExecutionResult:
    """Full result of answering pipeline."""

    question: str
    answer: str
    citations: list[Citation]
    status: str  # answered | insufficient_evidence | retrieve_only
    verification: GroundingVerificationResult
    token_count: int | None
    latency_ms: int | None
    hidden_text_excluded: bool = False


def execute_ask(
    document_id: Any,
    question: str,
    *,
    session: Session,
    cfg: Settings,
    provider: LLMProvider | None = None,
    last_user_query: str | None = None,
    last_assistant_heading: str | None = None,
    hidden_findings: Sequence[Any] | None = None,
) -> AnswerExecutionResult:
    """Execute synchronous grounded question answering with PII protection and hidden text exclusion."""
    t0 = time.perf_counter()

    # 1. Retrieve evidence
    retrieval = retrieve_evidence(
        document_id,
        question,
        session=session,
        top_k=5,
        last_user_query=last_user_query,
        last_assistant_heading=last_assistant_heading,
    )

    citations = build_citations(retrieval.chunks)

    # 2. Check sufficient evidence
    if not retrieval.has_sufficient_evidence or (not retrieval.chunks and not retrieval.overview_block):
        elapsed_ms = int((time.perf_counter() - t0) * 1000)
        topic = question.rstrip("?").strip()
        topic = re.sub(r"^(what\s+is|what\s+are|how\s+many|is\s+there|are\s+there|can\s+a\s+party|does\s+the)\s+", "", topic, flags=re.IGNORECASE)
        return AnswerExecutionResult(
            question=question,
            answer=f"The contract does not say what is specified regarding {topic}.",
            citations=[],
            status="insufficient_evidence",
            verification=GroundingVerificationResult(
                is_grounded=True,
                unverified_clause_ids=[],
                unverified_quotes=[],
                unverified_monetary_amounts=[],
                warnings=[],
                kind="abstention",
            ),
            token_count=0,
            latency_ms=elapsed_ms,
            hidden_text_excluded=False,
        )

    # 3. LLM generation with prompt sanitization and PII masking
    llm = provider or get_provider(cfg)
    prompt, hidden_excluded = construct_prompt(question, retrieval, hidden_findings=hidden_findings)
    redacted_prompt, pii_mapping = redact_sensitive_pii(prompt)

    if cfg.debug_log_prompts:
        logger.debug("Prompt to LLM:\n%s", redacted_prompt)

    try:
        resp = llm.generate(redacted_prompt, system=AEQI_SYSTEM_PROMPT)
        raw_answer = resp.content
        token_count = resp.token_count
    except Exception as exc:
        logger.error("LLM generation error: %s", exc)
        elapsed_ms = int((time.perf_counter() - t0) * 1000)
        return AnswerExecutionResult(
            question=question,
            answer="",
            citations=citations,
            status="retrieve_only",
            verification=GroundingVerificationResult(
                is_grounded=False,
                unverified_clause_ids=[],
                unverified_quotes=[],
                unverified_monetary_amounts=[],
                warnings=[f"LLM generation failed: {exc}"],
            ),
            token_count=0,
            latency_ms=elapsed_ms,
            hidden_text_excluded=hidden_excluded,
        )

    # 4. Verify grounding and restore PII in user-visible answer
    verification = verify_grounding(
        raw_answer,
        retrieval.chunks,
        overview_block=retrieval.overview_block,
    )
    final_answer = restore_sensitive_pii(raw_answer, pii_mapping)

    elapsed_ms = int((time.perf_counter() - t0) * 1000)

    return AnswerExecutionResult(
        question=question,
        answer=final_answer,
        citations=citations,
        status="answered",
        verification=verification,
        token_count=token_count,
        latency_ms=elapsed_ms,
        hidden_text_excluded=hidden_excluded,
    )
