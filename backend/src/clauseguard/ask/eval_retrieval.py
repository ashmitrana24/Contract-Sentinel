"""Retrieval evaluation script for ClauseGuard Ask against the CUAD benchmark.

Evaluates BM25 retrieval with optional label boosting on CUAD VAL and TEST splits.
Measures:
- Hit@1, Hit@3, Hit@5
- Mean Reciprocal Rank (MRR)
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from typing import Any

from clauseguard.ask.chunking import build_retrieval_chunks
from clauseguard.ask.retrieval import BM25Index, tokenize
from clauseguard.clauses.model import classify_clause
from clauseguard.clauses.taxonomy import normalize_category_to_label
from clauseguard.clauses.training.cuad_data import _chunk_raw_into_pages, load_cuad_raw
from clauseguard.clauses.training.split import partition_contracts
from clauseguard.parsing.clauses import segment_clauses

logger = logging.getLogger("clauseguard.ask.eval_retrieval")


def evaluate_split(
    split_name: str = "val",
    max_contracts: int | None = None,
    label_boost: float = 1.25,
    top_k: int = 5,
) -> dict[str, float]:
    """Evaluate retrieval engine over the specified CUAD split."""
    raw_data = load_cuad_raw()
    all_titles = [c.get("title", "") for c in raw_data if c.get("title")]
    partition = partition_contracts(all_titles, seed=42)

    target_titles = set(partition.val_contracts if split_name == "val" else partition.test_contracts)
    contracts = [c for c in raw_data if c.get("title") in target_titles]

    if max_contracts:
        contracts = contracts[:max_contracts]

    logger.info("Evaluating retrieval on %d %s contracts...", len(contracts), split_name.upper())

    total_queries = 0
    hit1_count = 0
    hit3_count = 0
    hit5_count = 0
    reciprocal_ranks: list[float] = []

    t0 = time.perf_counter()

    for c_idx, contract in enumerate(contracts, start=1):
        paragraphs = contract.get("paragraphs", [])
        if not paragraphs:
            continue

        context = paragraphs[0].get("context", "")
        qas = paragraphs[0].get("qas", [])

        # Filter only QAs with at least one answer
        positive_qas = [q for q in qas if q.get("answers") and len(q["answers"]) > 0]
        if not positive_qas:
            continue

        pages = _chunk_raw_into_pages(context)
        raw_clauses = segment_clauses(pages)
        chunks = build_retrieval_chunks(raw_clauses, pages=pages)
        if not chunks:
            continue

        index = BM25Index(chunks)

        # Pre-classify clauses to populate clause_id -> labels mapping for boosting
        clause_labels_map: dict[str, set[str]] = {}
        if label_boost > 1.0:
            for clause in raw_clauses:
                c_id = str(clause.clause_id)
                preds = classify_clause(clause.text, heading=clause.heading)
                clause_labels_map[c_id] = {p["label"] for p in preds if p.get("score", 0.0) >= 0.3}

        for qa in positive_qas:
            question_text = qa.get("question", "")
            answers = qa.get("answers", [])
            gold_answer_texts = [a["text"].strip() for a in answers if a.get("text")]
            if not gold_answer_texts:
                continue

            # Query classification for label boosting
            label_boosts: dict[str, float] = {}
            if label_boost > 1.0:
                q_preds = classify_clause(question_text)
                q_labels = {p["label"] for p in q_preds if p.get("score", 0.0) >= 0.3}
                if q_labels:
                    for c_id, c_lbls in clause_labels_map.items():
                        if q_labels.intersection(c_lbls):
                            label_boosts[c_id] = label_boost

            results = index.search(question_text, top_k=top_k, label_boosts=label_boosts)
            retrieved_chunks = [c for c, _score in results]

            total_queries += 1
            rank = None

            for r_idx, chunk in enumerate(retrieved_chunks, start=1):
                # Match criterion: chunk contains gold answer or has significant token overlap
                chunk_lower = chunk.text.lower()
                chunk_tokens = set(tokenize(chunk.text))
                is_hit = False

                for gold_ans in gold_answer_texts:
                    gold_lower = gold_ans.lower()
                    if gold_lower in chunk_lower or (len(gold_lower) > 30 and gold_lower[:30] in chunk_lower):
                        is_hit = True
                        break
                    # Word overlap >= 40%
                    gold_toks = set(tokenize(gold_ans))
                    if gold_toks and len(chunk_tokens.intersection(gold_toks)) / len(gold_toks) >= 0.4:
                        is_hit = True
                        break

                if is_hit:
                    rank = r_idx
                    break

            if rank is not None:
                reciprocal_ranks.append(1.0 / rank)
                if rank <= 1:
                    hit1_count += 1
                if rank <= 3:
                    hit3_count += 1
                if rank <= 5:
                    hit5_count += 1
            else:
                reciprocal_ranks.append(0.0)

    elapsed = time.perf_counter() - t0
    mrr = (sum(reciprocal_ranks) / max(1, total_queries)) if total_queries > 0 else 0.0
    hit1 = (hit1_count / max(1, total_queries)) if total_queries > 0 else 0.0
    hit3 = (hit3_count / max(1, total_queries)) if total_queries > 0 else 0.0
    hit5 = (hit5_count / max(1, total_queries)) if total_queries > 0 else 0.0

    metrics = {
        "split": split_name,
        "contracts_evaluated": len(contracts),
        "total_queries": total_queries,
        "hit@1": hit1,
        "hit@3": hit3,
        "hit@5": hit5,
        "mrr": mrr,
        "elapsed_seconds": elapsed,
    }

    print("\n" + "=" * 60)
    print(f"RETRIEVAL EVALUATION REPORT [{split_name.upper()} SPLIT]")
    print("=" * 60)
    print(f"Contracts:          {len(contracts)}")
    print(f"Total QA Queries:   {total_queries}")
    print(f"Label Boost Multiplier: {label_boost}")
    print(f"Hit@1:              {hit1:.4f} ({hit1 * 100:.1f}%)")
    print(f"Hit@3:              {hit3:.4f} ({hit3 * 100:.1f}%)")
    print(f"Hit@5:              {hit5:.4f} ({hit5 * 100:.1f}%)")
    print(f"MRR:                {mrr:.4f}")
    print(f"Evaluation Time:    {elapsed:.2f}s")
    print("=" * 60 + "\n")

    return metrics


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    parser = argparse.ArgumentParser(description="Evaluate BM25 retrieval on CUAD.")
    parser.add_argument("--split", choices=["val", "test"], default="val", help="Dataset split to evaluate")
    parser.add_argument("--contracts", type=int, default=None, help="Max number of contracts to evaluate")
    parser.add_argument("--boost", type=float, default=1.25, help="Label boost factor")
    parser.add_argument("--top-k", type=int, default=5, help="Max retrieved chunks")

    args = parser.parse_args()
    evaluate_split(
        split_name=args.split,
        max_contracts=args.contracts,
        label_boost=args.boost,
        top_k=args.top_k,
    )


if __name__ == "__main__":
    main()
