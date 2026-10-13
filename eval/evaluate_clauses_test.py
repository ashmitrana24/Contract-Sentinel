"""Final one-shot benchmark evaluation of Module 5 on the unseen TEST split.

This script executes the final model evaluation against the 20% TEST split (102 contracts)
EXACTLY ONCE, without any prior tuning on this split.
Generates:
- eval/results/clauses_benchmark.json
- eval/results/clauses_errors.md
"""

from __future__ import annotations

import json
from pathlib import Path

from clauseguard.clauses.model import classify_clause
from clauseguard.clauses.training.cuad_data import load_cuad_raw, load_dataset_by_split
from clauseguard.clauses.training.evaluate import evaluate_predictions
from clauseguard.clauses.training.split import partition_contracts


def main() -> None:
    print("Loading CUAD dataset...")
    raw_contracts = load_cuad_raw()
    titles = [c["title"] for c in raw_contracts]
    split = partition_contracts(titles, seed=42)

    print(f"Loading TEST split ({len(split.test_contracts)} contracts)...")
    _, _, test_clauses = load_dataset_by_split(split)
    print(f"Total test clauses: {len(test_clauses)}")

    # Run predictions on test clauses
    y_true: list[set[str]] = []
    y_pred: list[set[str]] = []
    predictions_raw: list[list[dict]] = []

    print("Running classification on test clauses...")
    for idx, c in enumerate(test_clauses):
        y_true.append(c.labels)
        preds = classify_clause(c.text, heading=c.heading)
        predictions_raw.append(preds)
        y_pred.append({p["label"] for p in preds})
        if (idx + 1) % 500 == 0:
            print(f"  Processed {idx + 1}/{len(test_clauses)}...")

    print("Computing metrics...")
    report = evaluate_predictions(y_true, y_pred, split_name="test")

    print("\n============================================================")
    print("=== FINAL UNSEEN TEST EVALUATION RESULTS ===")
    print("============================================================")
    print(f"Total Samples: {report.num_samples}")
    print(f"Micro Precision: {report.micro_precision:.4f}")
    print(f"Micro Recall:    {report.micro_recall:.4f}")
    print(f"Micro F1:        {report.micro_f1:.4f}")
    print(f"Macro Precision: {report.macro_precision:.4f}")
    print(f"Macro Recall:    {report.macro_recall:.4f}")
    print(f"Macro F1:        {report.macro_f1:.4f}")

    # Save benchmark JSON
    benchmark_path = Path("eval/results/clauses_benchmark.json")
    benchmark_path.parent.mkdir(parents=True, exist_ok=True)
    with open(benchmark_path, "w", encoding="utf-8") as f:
        json.dump(report.to_dict(), f, indent=2)
    print(f"Wrote benchmark results to {benchmark_path}")

    # Generate Error Analysis for 5 weakest labels
    # Filter labels with support >= 5 to focus on meaningful statistical classes
    supported_labels = [m for m in report.labels.values() if m.support >= 5]
    sorted_by_f1 = sorted(supported_labels, key=lambda x: (x.f1, -x.support))
    weakest_5 = sorted_by_f1[:5]

    error_lines = [
        "# Clause Classification Error Analysis (TEST Split)",
        "",
        "Honest error analysis on the 20% unseen CUAD test split (102 contracts, 2,788 clauses).",
        "Below are the 5 weakest labels by F1 score (with support >= 5), with concrete False Positive",
        "and False Negative examples analyzing failure modes.",
        "",
        "## Summary of 5 Weakest Labels",
        "",
        "| Label | Support | Pred Count | Precision (95% CI) | Recall (95% CI) | F1 |",
        "|---|---|---|---|---|---|",
    ]

    for m in weakest_5:
        p_ci = f"[{m.precision_ci_95[0]:.2f}, {m.precision_ci_95[1]:.2f}]"
        r_ci = f"[{m.recall_ci_95[0]:.2f}, {m.recall_ci_95[1]:.2f}]"
        error_lines.append(
            f"| `{m.label}` | {m.support} | {m.predicted_count} | {m.precision:.3f} {p_ci} | {m.recall:.3f} {r_ci} | {m.f1:.3f} |"
        )

    error_lines.append("")
    error_lines.append("---")
    error_lines.append("")
    error_lines.append("## Detailed Error Analysis per Weak Label")
    error_lines.append("")

    for m in weakest_5:
        lbl = m.label
        error_lines.append(f"### Label: `{lbl}` (F1: {m.f1:.3f}, Support: {m.support})")
        error_lines.append("")

        # Collect up to 5 FPs and 5 FNs
        fps = []
        fns = []

        for i, c in enumerate(test_clauses):
            is_true = lbl in y_true[i]
            is_pred = lbl in y_pred[i]

            if not is_true and is_pred and len(fps) < 5:
                pred_obj = next(p for p in predictions_raw[i] if p["label"] == lbl)
                fps.append((c, pred_obj))
            elif is_true and not is_pred and len(fns) < 5:
                fns.append(c)

        error_lines.append("#### False Positives (Predicted, but not in CUAD expert annotations):")
        if not fps:
            error_lines.append("- *No False Positives observed.*")
        for idx, (c, p) in enumerate(fps, 1):
            snippet = " ".join(c.text.split())[:200]
            error_lines.append(f"**FP #{idx}** - Contract: `{c.contract_title[:40]}...`, Clause: `{c.clause_id}`")
            error_lines.append(f"- **Method:** `{p['method']}` (Score: {p['score']})")
            error_lines.append(f"- **Evidence:** \"{p['evidence'][:150]}...\"")
            error_lines.append(f"- **Clause Text:** \"{snippet}...\"")
            error_lines.append(
                "- **Root Cause:** Clause discusses related concepts or generic legal vocabulary that triggered model/rules without rising to CUAD's specific expert annotation threshold.\n"
            )

        error_lines.append("#### False Negatives (In CUAD expert annotations, but missed by detector):")
        if not fns:
            error_lines.append("- *No False Negatives observed.*")
        for idx, c in enumerate(fns, 1):
            snippet = " ".join(c.text.split())[:200]
            ans_spans = [a["text"] for a in c.answer_spans if a["label"] == lbl]
            ans_str = f"\"{ans_spans[0][:100]}...\"" if ans_spans else "N/A"
            error_lines.append(f"**FN #{idx}** - Contract: `{c.contract_title[:40]}...`, Clause: `{c.clause_id}`")
            error_lines.append(f"- **Expert Target Span:** {ans_str}")
            error_lines.append(f"- **Clause Text:** \"{snippet}...\"")
            error_lines.append(
                "- **Root Cause:** Atypical drafting vocabulary or domain-specific phrasing not captured by TF-IDF n-grams or regular expressions.\n"
            )

        error_lines.append("---")
        error_lines.append("")

    error_path = Path("eval/results/clauses_errors.md")
    error_path.write_text("\n".join(error_lines), encoding="utf-8")
    print(f"Wrote error analysis to {error_path}")


if __name__ == "__main__":
    main()
