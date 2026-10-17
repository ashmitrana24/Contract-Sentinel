"""Answer generation and grounding verification pipeline for ClauseGuard Ask."""

from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass
from typing import Iterator, Sequence

from sqlalchemy.orm import Session

from clauseguard.ask.chunking import RetrievalChunk
from clauseguard.ask.privacy import (
    AEQI_SYSTEM_PROMPT,
    sanitize_contract_context,
)
from clauseguard.ask.retrieval import RetrievalResult, retrieve_evidence
from clauseguard.config import Settings
from clauseguard.llm import LLMProvider, get_provider
from clauseguard.schemas.api import Citation

logger = logging.getLogger(__name__)

CLAUSE_CITE_RE = re.compile(r"\[(?:Clause|c)?\s*([a-zA-Z0-9_.-]+)\]", re.IGNORECASE)
QUOTE_RE = re.compile(r'"([^"\n]{6,})"')
MONEY_RE = re.compile(r"\$[0-9,]+(?:\.[0-9]{2})?")


@dataclass(frozen=True)
class GroundingVerificationResult:
    """Outcome of grounding checks on generated answer."""

    is_grounded: bool
    unverified_clause_ids: list[str]
    unverified_quotes: list[str]
    unverified_monetary_amounts: list[str]
    warnings: list[str]


def verify_grounding(
    answer_text: str,
    retrieved_chunks: Sequence[RetrievalChunk],
    overview_block: str | None = None,
) -> GroundingVerificationResult:
    """Verify that cited clauses, verbatim quotes, and numeric amounts exist in context."""
    valid_clause_ids = {c.clause_id for c in retrieved_chunks}
    valid_chunk_ids = {c.chunk_id for c in retrieved_chunks}
    combined_context = "\n".join(c.text for c in retrieved_chunks)
    if overview_block:
        combined_context += "\n" + overview_block
    normalized_context = " ".join(combined_context.lower().split())

    warnings: list[str] = []

    # 1. Check cited clause IDs
    cited_ids = CLAUSE_CITE_RE.findall(answer_text)
    unverified_ids: list[str] = []
    for cid in cited_ids:
        clean_cid = cid.strip()
        if clean_cid not in valid_clause_ids and clean_cid not in valid_chunk_ids:
            unverified_ids.append(clean_cid)
            warnings.append(f"Cited clause '[{clean_cid}]' was not in retrieved context.")

    # 2. Check quotes (>= 6 chars)
    quotes = QUOTE_RE.findall(answer_text)
    unverified_quotes: list[str] = []
    for q in quotes:
        norm_q = " ".join(q.strip().lower().split())
        if norm_q not in normalized_context:
            unverified_quotes.append(q)
            warnings.append(f"Verbatim quote \"{q[:40]}...\" not found in contract context.")

    # 3. Check monetary amounts
    money_matches = MONEY_RE.findall(answer_text)
    unverified_money: list[str] = []
    for m in money_matches:
        if m not in combined_context:
            unverified_money.append(m)
            warnings.append(f"Monetary amount '{m}' not found in contract text.")

    is_grounded = len(unverified_ids) == 0 and len(unverified_quotes) == 0 and len(unverified_money) == 0

    return GroundingVerificationResult(
        is_grounded=is_grounded,
        unverified_clause_ids=unverified_ids,
        unverified_quotes=unverified_quotes,
        unverified_monetary_amounts=unverified_money,
        warnings=warnings,
    )


def build_citations(chunks: Sequence[RetrievalChunk]) -> list[Citation]:
    """Convert retrieved chunks into API Citation models."""
    citations: list[Citation] = []
    for c in chunks:
        # 1-2 sentence snippet
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
) -> str:
    """Build the complete, delimited user prompt for the LLM."""
    chunk_texts = [f"[{c.chunk_id}] {c.heading + ': ' if c.heading else ''}{c.text}" for c in retrieval.chunks]
    context_block = sanitize_contract_context(chunk_texts, hidden_findings=hidden_findings)

    parts: list[str] = []
    if retrieval.is_overview and retrieval.overview_block:
        parts.append(f"<contract_overview>\n{retrieval.overview_block}\n</contract_overview>\n")

    parts.append(context_block)
    parts.append(
        f"\nUSER QUESTION: {question}\n\n"
        "Provide a concise, grounded answer based strictly on the excerpts above. "
        "Cite the relevant clause bracket e.g. [1.1] or [c1.w0]. "
        "Quote verbatim terms of >= 6 characters in double quotes. "
        "If the excerpts do not contain the answer, say: 'The provided contract excerpts do not contain sufficient information to answer this question.'"
    )
    return "\n".join(parts)


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
    """Execute synchronous grounded question answering."""
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
        return AnswerExecutionResult(
            question=question,
            answer="The provided contract excerpts do not contain sufficient information to answer this question.",
            citations=citations,
            status="insufficient_evidence",
            verification=GroundingVerificationResult(
                is_grounded=True,
                unverified_clause_ids=[],
                unverified_quotes=[],
                unverified_monetary_amounts=[],
                warnings=[],
            ),
            token_count=0,
            latency_ms=elapsed_ms,
        )

    # 3. LLM generation
    llm = provider or get_provider(cfg)
    prompt = construct_prompt(question, retrieval, hidden_findings=hidden_findings)

    if cfg.debug_log_prompts:
        logger.debug("Prompt to LLM:\n%s", prompt)

    try:
        resp = llm.generate(prompt, system=AEQI_SYSTEM_PROMPT)
        answer_text = resp.content
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
        )

    # 4. Verify grounding
    verification = verify_grounding(
        answer_text,
        retrieval.chunks,
        overview_block=retrieval.overview_block,
    )

    elapsed_ms = int((time.perf_counter() - t0) * 1000)

    return AnswerExecutionResult(
        question=question,
        answer=answer_text,
        citations=citations,
        status="answered",
        verification=verification,
        token_count=token_count,
        latency_ms=elapsed_ms,
    )
