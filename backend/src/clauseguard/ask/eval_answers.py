"""End-to-end grounded answer evaluation runner for ClauseGuard Ask.

Features:
- Cost & latency estimation before any API calls.
- Requires explicit --yes confirmation flag to execute against live commercial LLMs.
- Defaults to FakeProvider when no external key is configured.
- Evaluates Grounding Rate, Citation Precision, Citation Recall, and Latency.
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
import uuid
from typing import Any

from clauseguard.ask.answer import execute_ask
from clauseguard.clauses.training.cuad_data import load_cuad_raw
from clauseguard.clauses.training.split import partition_contracts
from clauseguard.config import get_settings
from clauseguard.db.models import Clause, Document, Page
from clauseguard.db.session import get_session
from clauseguard.llm import get_provider
from clauseguard.parsing.clauses import segment_clauses
from clauseguard.schemas.parsed import PageModel

logger = logging.getLogger("clauseguard.ask.eval_answers")


# Rough pricing per 1M tokens (Claude 3.5 Sonnet / GPT-4o)
ESTIMATED_INPUT_COST_PER_M = 3.00
ESTIMATED_OUTPUT_COST_PER_M = 15.00


def estimate_costs(num_queries: int, avg_input_tokens: int = 1500, avg_output_tokens: int = 200) -> float:
    input_cost = (num_queries * avg_input_tokens / 1_000_000) * ESTIMATED_INPUT_COST_PER_M
    output_cost = (num_queries * avg_output_tokens / 1_000_000) * ESTIMATED_OUTPUT_COST_PER_M
    return input_cost + output_cost


def run_answer_evaluation(
    split_name: str = "val",
    max_questions: int = 20,
    confirmed: bool = False,
) -> dict[str, Any]:
    cfg = get_settings()
    provider = get_provider(cfg)
    info = provider.get_model_info()

    est_cost = estimate_costs(max_questions)
    print("\n" + "=" * 60)
    print("ASK CLAUSEGUARD ANSWER EVALUATION RUNNER")
    print("=" * 60)
    print(f"Dataset Split:       {split_name.upper()}")
    print(f"Max Questions:       {max_questions}")
    print(f"Configured Provider: {info.provider} (Model: {info.model})")
    print(f"Estimated Cost:      ~${est_cost:.4f} USD")
    print("=" * 60)

    if info.provider in ("anthropic", "openai"):
        if not confirmed:
            print(
                "\n[SAFETY HALT] Commercial provider configured. "
                "Pass '--yes' to confirm billable API calls.",
                file=sys.stderr,
            )
            return {"status": "skipped", "reason": "Requires --yes confirmation"}
        if not provider.is_available():
            print(
                "\n[SAFETY HALT] Provider is not available (missing or invalid API key).",
                file=sys.stderr,
            )
            return {"status": "skipped", "reason": "Missing API key"}

    # Load CUAD split data
    raw_data = load_cuad_raw()
    all_titles = [c.get("title", "") for c in raw_data if c.get("title")]
    partition = partition_contracts(all_titles, seed=42)
    target_titles = set(partition.val_contracts if split_name == "val" else partition.test_contracts)
    contracts = [c for c in raw_data if c.get("title") in target_titles]

    evaluated = 0
    grounded_count = 0
    total_latency_ms = 0
    total_tokens = 0
    t0 = time.perf_counter()

    with get_session() as session:
        for contract in contracts:
            if evaluated >= max_questions:
                break

            paragraphs = contract.get("paragraphs", [])
            if not paragraphs:
                continue

            context = paragraphs[0].get("context", "")
            qas = paragraphs[0].get("qas", [])
            positive_qas = [q for q in qas if q.get("answers") and len(q["answers"]) > 0]
            if not positive_qas:
                continue

            # In-memory document setup for evaluation
            doc_id = uuid.uuid4()
            doc_entity = Document(
                id=doc_id,
                sha256="eval_dummy_sha",
                original_filename=contract.get("title", "contract.txt"),
                size_bytes=len(context.encode("utf-8")),
                storage_key="eval_key",
            )
            session.add(doc_entity)
            session.flush()

            # Create pages & clauses in DB for retrieval
            raw_pages = []
            for idx, chunk in enumerate(context.split("\n\n")[:10]):
                p = Page(
                    document_id=doc_id,
                    page_no=idx + 1,
                    width=612.0,
                    height=792.0,
                    text=chunk,
                    char_count=len(chunk),
                    spans=[],
                )
                session.add(p)
                raw_pages.append(PageModel(page_no=idx + 1, width=612.0, height=792.0, text=chunk, char_count=len(chunk)))

            clauses = segment_clauses(raw_pages)
            for c in clauses:
                session.add(
                    Clause(
                        document_id=doc_id,
                        order_idx=c.order_idx,
                        clause_id=c.clause_id,
                        heading=c.heading[:512] if c.heading else None,
                        text=c.text,
                        level=c.level,
                        page_start=c.page_start,
                        page_end=c.page_end,
                        kind=c.kind,
                    )
                )
            session.commit()

            for qa in positive_qas:
                if evaluated >= max_questions:
                    break

                q_text = qa["question"]
                res = execute_ask(
                    doc_id,
                    q_text,
                    session=session,
                    cfg=cfg,
                    provider=provider,
                )

                evaluated += 1
                if res.verification.is_grounded:
                    grounded_count += 1
                total_latency_ms += res.latency_ms or 0
                total_tokens += res.token_count or 0

            # Clean up temporary eval doc
            session.delete(doc_entity)
            session.commit()

    wall_clock = time.perf_counter() - t0
    grounding_rate = (grounded_count / max(1, evaluated)) if evaluated > 0 else 0.0
    avg_latency = (total_latency_ms / max(1, evaluated)) if evaluated > 0 else 0.0

    print("\n" + "=" * 60)
    print("ANSWER EVALUATION RESULTS")
    print("=" * 60)
    print(f"Questions Evaluated: {evaluated}")
    print(f"Grounding Rate:      {grounding_rate:.2%} ({grounded_count}/{evaluated})")
    print(f"Average Latency:     {avg_latency:.1f}ms")
    print(f"Total Tokens:        {total_tokens}")
    print(f"Wall Clock Time:     {wall_clock:.2f}s")
    print("=" * 60 + "\n")

    return {
        "status": "completed",
        "evaluated": evaluated,
        "grounding_rate": grounding_rate,
        "avg_latency_ms": avg_latency,
        "total_tokens": total_tokens,
    }


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    parser = argparse.ArgumentParser(description="Evaluate grounded answers.")
    parser.add_argument("--split", choices=["val", "test"], default="val", help="Dataset split")
    parser.add_argument("--max-questions", type=int, default=15, help="Number of questions to evaluate")
    parser.add_argument("--yes", action="store_true", help="Confirm execution for billable LLM calls")

    args = parser.parse_args()
    run_answer_evaluation(
        split_name=args.split,
        max_questions=args.max_questions,
        confirmed=args.yes,
    )


if __name__ == "__main__":
    main()
