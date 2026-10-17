"""Compute honest TRAIN, VAL, and TEST metrics with the EXACT SAME production function: classify_clause."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from clauseguard.clauses.model import ClauseClassifier, classify_clause
from clauseguard.clauses.training.cuad_data import LabeledClause, load_cuad_raw, load_dataset_by_split
from clauseguard.clauses.training.evaluate import evaluate_predictions
from clauseguard.clauses.training.split import partition_contracts

KEY_LABELS = [
    "governing_law",
    "anti_assignment",
    "cap_on_liability",
    "license_grant",
    "termination_for_convenience",
    "uncapped_liability",
    "non_compete",
]


def evaluate_split_production(clauses: list[LabeledClause], split_name: str) -> dict[str, Any]:
    print(f"\nEvaluating {split_name.upper()} ({len(clauses)} clauses) with production classify_clause...", flush=True)
    y_true: list[set[str]] = []
    y_pred: list[set[str]] = []

    for idx, c in enumerate(clauses):
        y_true.append(c.labels)
        preds = classify_clause(c.text, heading=c.heading)
        y_pred.append({p["label"] for p in preds})
        if (idx + 1) % 1000 == 0 or (idx + 1) == len(clauses):
            print(f"  Processed {idx + 1}/{len(clauses)}...", flush=True)

    report = evaluate_predictions(y_true, y_pred, split_name=split_name)
    return report.to_dict()


def main() -> None:
    print("=== Module 5: Comprehensive Honest Evaluation Across TRAIN, VAL, TEST ===", flush=True)
    raw_contracts = load_cuad_raw()
    titles = [c["title"] for c in raw_contracts]
    split = partition_contracts(titles, seed=42)

    # 1. Disjointness check
    train_set = set(split.train_contracts)
    val_set = set(split.val_contracts)
    test_set = set(split.test_contracts)
    assert len(train_set & val_set) == 0, "Train & Val overlap!"
    assert len(train_set & test_set) == 0, "Train & Test overlap!"
    assert len(val_set & test_set) == 0, "Val & Test overlap!"
    assert len(train_set) + len(val_set) + len(test_set) == len(titles), "Contract count mismatch!"
    print(f"Contract counts: Train={len(train_set)}, Val={len(val_set)}, Test={len(test_set)}, Total={len(titles)}", flush=True)
    print("Disjointness: PASSED (0 overlap across all splits).", flush=True)

    # 2. Threshold integrity
    model_dir = Path("backend/models/clauses/v1")
    with open(model_dir / "metrics.json", encoding="utf-8") as f:
        metrics_data = json.load(f)
    with open(model_dir / "thresholds.json", encoding="utf-8") as f:
        thresholds_data = json.load(f)
    classifier = ClauseClassifier(model_dir)

    assert metrics_data["thresholds"] == thresholds_data["thresholds"] == classifier.thresholds
    assert metrics_data["shipped_methods"] == thresholds_data["shipped_methods"] == classifier.shipped_methods
    print("Thresholds integrity: VERIFIED (metrics.json == thresholds.json == ClauseClassifier).", flush=True)

    # 3. Load clauses
    train_clauses, val_clauses, test_clauses = load_dataset_by_split(split)
    print(f"Clauses counts: Train={len(train_clauses)}, Val={len(val_clauses)}, Test={len(test_clauses)}", flush=True)

    # 4. Evaluate TEST, VAL, and TRAIN using the EXACT SAME production function
    test_report = evaluate_split_production(test_clauses, "test")
    val_report = evaluate_split_production(val_clauses, "val")
    train_report = evaluate_split_production(train_clauses, "train")

    output_data = {
        "disjointness": {
            "train_contracts": len(train_set),
            "val_contracts": len(val_set),
            "test_contracts": len(test_set),
            "train_clauses": len(train_clauses),
            "val_clauses": len(val_clauses),
            "test_clauses": len(test_clauses),
            "zero_leakage": True,
        },
        "val": val_report,
        "test": test_report,
        "train": train_report,
    }

    out_path = Path("eval/results/final_honest_evaluation.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(output_data, f, indent=2)

    print(f"\nWrote full evaluation JSON to {out_path}", flush=True)

    # Print summary tables
    print("\n" + "=" * 90, flush=True)
    print(f"{'Label':<32} {'TRAIN F1':<14} {'VAL F1':<14} {'TEST F1':<14} {'VAL P':<10} {'VAL R':<10}", flush=True)
    print("=" * 90, flush=True)
    for k in KEY_LABELS:
        tr_f1 = train_report["labels"][k]["f1"]
        v_f1 = val_report["labels"][k]["f1"]
        te_f1 = test_report["labels"][k]["f1"]
        v_p = val_report["labels"][k]["precision"]
        v_r = val_report["labels"][k]["recall"]
        print(f"{k:<32} {tr_f1:<14.4f} {v_f1:<14.4f} {te_f1:<14.4f} {v_p:<10.4f} {v_r:<10.4f}", flush=True)
    print("-" * 90, flush=True)
    print(
        f"{'OVERALL MICRO':<32} {train_report['micro_f1']:<14.4f} {val_report['micro_f1']:<14.4f} {test_report['micro_f1']:<14.4f} {val_report['micro_precision']:<10.4f} {val_report['micro_recall']:<10.4f}",
        flush=True,
    )
    print(
        f"{'OVERALL MACRO':<32} {train_report['macro_f1']:<14.4f} {val_report['macro_f1']:<14.4f} {test_report['macro_f1']:<14.4f} {val_report['macro_precision']:<10.4f} {val_report['macro_recall']:<10.4f}",
        flush=True,
    )
    print("=" * 90, flush=True)


if __name__ == "__main__":
    main()
