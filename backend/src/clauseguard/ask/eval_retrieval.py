"""Retrieval evaluation script for ClauseGuard Ask against the CUAD benchmark.

Evaluates BM25 retrieval with ablations on CUAD VAL and TEST splits.
Measures:
- Recall@1, Recall@3, Recall@6
- Mean Reciprocal Rank (MRR)
- Per-label and overall breakdown
- Failure analysis for worst labels
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

from clauseguard.ask.chunking import build_retrieval_chunks
from clauseguard.ask.retrieval import BM25Index, expand_intent_query, tokenize
from clauseguard.clauses.model import classify_clause
from clauseguard.clauses.taxonomy import normalize_category_to_label
from clauseguard.clauses.training.cuad_data import _chunk_raw_into_pages, load_cuad_raw
from clauseguard.clauses.training.split import partition_contracts
from clauseguard.parsing.clauses import segment_clauses

logger = logging.getLogger("clauseguard.ask.eval_retrieval")


@dataclass
class EvalMetrics:
    total_queries: int = 0
    hit1: int = 0
    hit3: int = 0
    hit6: int = 0
    mrr_sum: float = 0.0

    @property
    def recall1(self) -> float:
        return (self.hit1 / max(1, self.total_queries)) if self.total_queries > 0 else 0.0

    @property
    def recall3(self) -> float:
        return (self.hit3 / max(1, self.total_queries)) if self.total_queries > 0 else 0.0

    @property
    def recall6(self) -> float:
        return (self.hit6 / max(1, self.total_queries)) if self.total_queries > 0 else 0.0

    @property
    def mrr(self) -> float:
        return (self.mrr_sum / max(1, self.total_queries)) if self.total_queries > 0 else 0.0


@dataclass
class MissExample:
    contract_title: str
    label: str
    question: str
    gold_answers: list[str]
    retrieved_headings: list[str | None]
    retrieved_snippets: list[str]
    reason: str


def check_hit(
    chunk_text: str,
    gold_answer_texts: list[str],
    chunk_tokens: set[str],
) -> bool:
    """Check if retrieved chunk matches any gold answer span."""
    chunk_lower = chunk_text.lower()
    for gold_ans in gold_answer_texts:
        gold_lower = gold_ans.lower()
        if gold_lower in chunk_lower or (len(gold_lower) > 30 and gold_lower[:30] in chunk_lower):
            return True
        if len(chunk_lower) > 30 and chunk_lower[:30] in gold_lower:
            return True
        gold_toks = set(tokenize(gold_ans))
        if gold_toks and len(chunk_tokens.intersection(gold_toks)) / len(gold_toks) >= 0.4:
            return True
        if chunk_tokens and len(chunk_tokens.intersection(gold_toks)) / len(chunk_tokens) >= 0.6:
            return True
    return False


def run_evaluation(
    split_name: str = "val",
    max_contracts: int | None = None,
    mode: str = "all",  # "all", "plain", "intent", "full"
    top_k: int = 6,
    label_boost: float = 1.75,
    heading_boost: float = 1.35,
) -> dict[str, Any]:
    """Run retrieval evaluation with ablations on CUAD."""
    raw_data = load_cuad_raw()
    all_titles = [c.get("title", "") for c in raw_data if c.get("title")]
    partition = partition_contracts(all_titles, seed=42)

    target_titles = set(partition.val_contracts if split_name == "val" else partition.test_contracts)
    contracts = [c for c in raw_data if c.get("title") in target_titles]

    if max_contracts:
        contracts = contracts[:max_contracts]

    logger.info("Evaluating retrieval on %d %s contracts (mode=%s)...", len(contracts), split_name.upper(), mode)

    # 1. Pre-parse and pre-classify all contracts to avoid redundant inference
    t_start = time.perf_counter()
    parsed_contracts: list[dict[str, Any]] = []

    for c in contracts:
        paragraphs = c.get("paragraphs", [])
        if not paragraphs:
            continue
        context = paragraphs[0].get("context", "")
        qas = paragraphs[0].get("qas", [])
        positive_qas = [q for q in qas if q.get("answers") and len(q["answers"]) > 0]
        if not positive_qas:
            continue

        pages = _chunk_raw_into_pages(context)
        raw_clauses = segment_clauses(pages)
        chunks = build_retrieval_chunks(raw_clauses, pages=pages)
        if not chunks:
            continue

        # Cache clause labels predicted by Module 5
        clause_labels_map: dict[str, set[str]] = {}
        for clause in raw_clauses:
            c_id = str(clause.clause_id)
            preds = classify_clause(clause.text, heading=clause.heading)
            clause_labels_map[c_id] = {p["label"] for p in preds if p.get("score", 0.0) >= 0.3}

        parsed_contracts.append({
            "title": c.get("title", ""),
            "context": context,
            "qas": positive_qas,
            "raw_clauses": raw_clauses,
            "chunks": chunks,
            "clause_labels_map": clause_labels_map,
        })

    logger.info("Indexed and classified %d contracts in %.2fs", len(parsed_contracts), time.perf_counter() - t_start)

    modes_to_run = ["plain", "intent", "full"] if mode == "all" else [mode]
    ablation_results: dict[str, dict[str, Any]] = {}
    label_metrics_full: dict[str, EvalMetrics] = defaultdict(EvalMetrics)
    miss_examples: dict[str, list[MissExample]] = defaultdict(list)

    for run_mode in modes_to_run:
        overall = EvalMetrics()
        label_metrics: dict[str, EvalMetrics] = defaultdict(EvalMetrics)

        for p_contract in parsed_contracts:
            chunks = p_contract["chunks"]
            clause_labels_map = p_contract["clause_labels_map"]
            index = BM25Index(chunks)

            for qa in p_contract["qas"]:
                qa_id = qa.get("id", "")
                cat_name = qa_id.split("__")[-1] if "__" in qa_id else ""
                label_id = normalize_category_to_label(cat_name) or "other"

                question_text = qa.get("question", "")
                answers = qa.get("answers", [])
                gold_answer_texts = [a["text"].strip() for a in answers if a.get("text")]
                if not gold_answer_texts:
                    continue

                # Configure ablation parameters
                if run_mode == "plain":
                    search_q = question_text
                    h_boost = 1.0
                    l_boosts: dict[str, float] | None = None
                elif run_mode == "intent":
                    expanded_q, _ = expand_intent_query(question_text)
                    search_q = expanded_q
                    h_boost = heading_boost
                    l_boosts = None
                else:  # full
                    expanded_q, detected_intents = expand_intent_query(question_text)
                    # Also include normalized category label if present
                    if label_id != "other":
                        detected_intents.add(label_id)

                    search_q = expanded_q
                    h_boost = heading_boost
                    l_boosts = {}
                    if detected_intents:
                        for c_id, c_lbls in clause_labels_map.items():
                            if detected_intents.intersection(c_lbls):
                                l_boosts[c_id] = label_boost

                results = index.search(
                    search_q,
                    top_k=top_k,
                    label_boosts=l_boosts,
                    heading_boost_factor=h_boost,
                )
                retrieved_chunks = [c for c, _score in results]

                overall.total_queries += 1
                label_metrics[label_id].total_queries += 1
                if run_mode == "full":
                    label_metrics_full[label_id].total_queries += 1

                rank = None
                for r_idx, chunk in enumerate(retrieved_chunks, start=1):
                    full_chunk_text = f"{chunk.heading or ''} {chunk.text}"
                    chunk_tokens = set(tokenize(full_chunk_text))
                    if check_hit(full_chunk_text, gold_answer_texts, chunk_tokens):
                        rank = r_idx
                        break

                if rank is not None:
                    rr = 1.0 / rank
                    overall.mrr_sum += rr
                    label_metrics[label_id].mrr_sum += rr
                    if run_mode == "full":
                        label_metrics_full[label_id].mrr_sum += rr

                    if rank <= 1:
                        overall.hit1 += 1
                        label_metrics[label_id].hit1 += 1
                        if run_mode == "full":
                            label_metrics_full[label_id].hit1 += 1
                    if rank <= 3:
                        overall.hit3 += 1
                        label_metrics[label_id].hit3 += 1
                        if run_mode == "full":
                            label_metrics_full[label_id].hit3 += 1
                    if rank <= 6:
                        overall.hit6 += 1
                        label_metrics[label_id].hit6 += 1
                        if run_mode == "full":
                            label_metrics_full[label_id].hit6 += 1
                else:
                    if run_mode == "full" and len(miss_examples[label_id]) < 3:
                        # Characterize why it missed
                        reason = "No lexical or intent match with gold clause; gold span dispersed or unboosted"
                        if not l_boosts:
                            reason = "Intent not detected in query, no label boost applied"
                        elif retrieved_chunks and not any(r.heading for r in retrieved_chunks):
                            reason = "Heading mismatch or missing clause headings in document"

                        miss_examples[label_id].append(
                            MissExample(
                                contract_title=p_contract["title"],
                                label=label_id,
                                question=question_text[:120],
                                gold_answers=[g[:100] for g in gold_answer_texts[:2]],
                                retrieved_headings=[r.heading for r in retrieved_chunks[:3]],
                                retrieved_snippets=[r.text[:100] for r in retrieved_chunks[:3]],
                                reason=reason,
                            )
                        )

        ablation_results[run_mode] = {
            "queries": overall.total_queries,
            "recall@1": overall.recall1,
            "recall@3": overall.recall3,
            "recall@6": overall.recall6,
            "mrr": overall.mrr,
            "by_label": {
                lbl: {
                    "queries": m.total_queries,
                    "recall@1": m.recall1,
                    "recall@3": m.recall3,
                    "recall@6": m.recall6,
                    "mrr": m.mrr,
                }
                for lbl, m in label_metrics.items()
            },
        }

    return {
        "split": split_name,
        "contracts": len(parsed_contracts),
        "ablations": ablation_results,
        "label_metrics_full": label_metrics_full,
        "miss_examples": miss_examples,
        "elapsed_seconds": time.perf_counter() - t_start,
    }


def print_report(res: dict[str, Any]) -> None:
    split_name = res["split"].upper()
    ablations = res["ablations"]
    print("\n" + "=" * 80)
    print(f"RETRIEVAL EVALUATION REPORT [{split_name} SPLIT] ({res['contracts']} contracts)")
    print("=" * 80)

    print("\n1. ABLATION SUMMARY (OVERALL)")
    print("-" * 80)
    print(f"{'Ablation':<35} | {'Recall@1':<10} | {'Recall@3':<10} | {'Recall@6':<10} | {'MRR':<8}")
    print("-" * 80)
    for mode, data in ablations.items():
        name = {
            "plain": "1. Plain BM25",
            "intent": "2. BM25 + Query-Intent & Heading",
            "full": "3. BM25 + Intent + Module 5 Labels",
        }.get(mode, mode)
        print(
            f"{name:<35} | {data['recall@1']*100:>8.1f}% | {data['recall@3']*100:>8.1f}% | "
            f"{data['recall@6']*100:>8.1f}% | {data['mrr']:>8.4f}"
        )
    print("-" * 80)

    # 2. Per-label table for full model
    if "full" in ablations:
        full_by_label = ablations["full"]["by_label"]
        print("\n2. PER-LABEL PERFORMANCE (FULL PIPELINE)")
        print("-" * 80)
        print(f"{'Label':<35} | {'Count':<6} | {'Recall@1':<9} | {'Recall@3':<9} | {'Recall@6':<9} | {'MRR':<8}")
        print("-" * 80)
        sorted_labels = sorted(full_by_label.items(), key=lambda x: x[1]["recall@6"], reverse=True)
        for lbl, stats in sorted_labels:
            print(
                f"{lbl:<35} | {stats['queries']:<6} | {stats['recall@1']*100:>7.1f}% | "
                f"{stats['recall@3']*100:>7.1f}% | {stats['recall@6']*100:>7.1f}% | {stats['mrr']:>8.4f}"
            )
        print("-" * 80)

        # 3. 5 Worst Labels
        worst_labels = sorted(
            [item for item in full_by_label.items() if item[1]["queries"] >= 5],
            key=lambda x: (x[1]["recall@6"], x[1]["mrr"]),
        )[:5]

        print("\n3. WORST 5 PERFORMING LABELS ON VAL (>= 5 queries)")
        print("-" * 80)
        for idx, (lbl, stats) in enumerate(worst_labels, start=1):
            print(f"[{idx}] {lbl} (Queries: {stats['queries']}, Recall@6: {stats['recall@6']*100:.1f}%, MRR: {stats['mrr']:.4f})")
            misses = res["miss_examples"].get(lbl, [])
            for m_idx, m in enumerate(misses[:3], start=1):
                print(f"    Example Miss {m_idx}:")
                print(f"      Contract: {m.contract_title}")
                print(f"      Question: {m.question}")
                print(f"      Gold Answer: {m.gold_answers[0] if m.gold_answers else 'N/A'}")
                print(f"      Retrieved Headings: {m.retrieved_headings}")
                print(f"      Root Cause: {m.reason}")
        print("-" * 80)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    parser = argparse.ArgumentParser(description="Evaluate BM25 retrieval ablations on CUAD.")
    parser.add_argument("--split", choices=["val", "test"], default="val", help="Dataset split to evaluate")
    parser.add_argument("--contracts", type=int, default=None, help="Max number of contracts to evaluate")
    parser.add_argument("--mode", choices=["all", "plain", "intent", "full"], default="all", help="Evaluation mode")
    parser.add_argument("--boost", type=float, default=1.75, help="Label boost factor")
    parser.add_argument("--heading-boost", type=float, default=1.35, help="Heading boost factor")
    parser.add_argument("--top-k", type=int, default=6, help="Max retrieved chunks")

    args = parser.parse_args()
    results = run_evaluation(
        split_name=args.split,
        max_contracts=args.contracts,
        mode=args.mode,
        top_k=args.top_k,
        label_boost=args.boost,
        heading_boost=args.heading_boost,
    )
    print_report(results)


if __name__ == "__main__":
    main()
