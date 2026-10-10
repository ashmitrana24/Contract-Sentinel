"""Module 4: Consistency Checks Evaluation Benchmark.

Evaluates contract self-consistency detectors on:
1. Module 1 synthetic/generated dataset (train/val split and held-out test split)
2. Reports detection rate, type correctness, localization, and FP rate.
"""

from __future__ import annotations

import argparse
import datetime
import json
import math
import sys
import time
from pathlib import Path
from typing import Any

# Ensure backend/src is on sys.path
_BACKEND_SRC = Path(__file__).resolve().parent.parent / "backend" / "src"
if str(_BACKEND_SRC) not in sys.path:
    sys.path.insert(0, str(_BACKEND_SRC))

from clauseguard.consistency.models import ConsistencySettings
from clauseguard.consistency.run import analyze
from clauseguard.parsing.parse_document import parse_document
from clauseguard.schemas.findings import Finding, Severity


def _percentile(values: list[float], pct: float) -> float:
    """Compute percentile from sorted list of numbers."""
    if not values:
        return 0.0
    if len(values) == 1:
        return values[0]
    k = (len(values) - 1) * pct
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return values[int(k)]
    d0 = values[int(f)] * (c - k)
    d1 = values[int(c)] * (k - f)
    return d0 + d1


# Expected finding types for content tamper types
_EXPECTED_FINDING_TYPES = {
    "amount_figure_only": {"figure_words_mismatch"},
    "xref_break": {"dangling_reference"},
    "clause_delete": {"dangling_reference", "numbering_gap"},
    "date_shift": {"date_order_conflict", "effective_date_conflict", "term_length_conflict"},
    "party_swap": {"party_name_variant"},
}

_TARGET_CONTENT_TAMPERS = [
    "amount_figure_only",
    "date_shift",
    "party_swap",
    "clause_delete",
    "xref_break",
]

_EXPECTED_UNDETECTABLE = [
    "amount_both",
    "clause_insert",
    "incremental_edit",
    "hidden_text",
    "metadata_anomaly",
    "active_content",
    "signature_invalid",
    "post_signature_modification",
]


def evaluate_split(
    split_name: str,
    items: list[dict[str, Any]],
    data_dir: Path,
    settings: ConsistencySettings | None = None,
) -> dict[str, Any]:
    """Evaluate detector performance on a labeled split (train/val or test)."""
    if settings is None:
        settings = ConsistencySettings()

    latencies_ms: list[float] = []
    results: list[dict[str, Any]] = []

    for item in items:
        doc_id = item["doc_id"]
        pdf_path = data_dir / f"{doc_id}.pdf"
        if not pdf_path.exists():
            pdf_path = data_dir / "pdfs" / f"{doc_id}.pdf"
        if not pdf_path.exists():
            continue

        pdf_bytes = pdf_path.read_bytes()
        t0 = time.monotonic()
        try:
            parsed_doc = parse_document(pdf_bytes)
            report = analyze(parsed_doc, settings)
        except Exception as exc:
            # Report detector crash as error
            dur_ms = (time.monotonic() - t0) * 1000
            latencies_ms.append(dur_ms)
            results.append({
                "doc_id": doc_id,
                "error": str(exc),
                "is_flagged": False,
                "findings": [],
                "tamper_types": item.get("tamper_types", []),
                "is_tampered": item.get("is_tampered", False),
                "source_type": item.get("source_type", "synthetic"),
                "duration_ms": dur_ms,
            })
            continue

        dur_ms = (time.monotonic() - t0) * 1000
        latencies_ms.append(dur_ms)

        med_plus_findings: list[Finding] = [
            f for f in report.findings
            if f.severity in (Severity.MEDIUM, Severity.HIGH, Severity.CRITICAL)
        ]
        is_flagged = len(med_plus_findings) > 0

        true_tamper_types = item.get("tamper_types", [])
        tamper_details = item.get("tamper_details", [])

        # Check localization and type correctness per tamper
        type_correct_map: dict[str, bool] = {}
        localized_map: dict[str, bool] = {}

        for detail in tamper_details:
            t_type = detail.get("tamper_type")
            if not t_type:
                continue

            expected_types = _EXPECTED_FINDING_TYPES.get(t_type, set())
            matching_findings = [f for f in med_plus_findings if f.type in expected_types]

            type_correct = len(matching_findings) > 0
            type_correct_map[t_type] = type_correct

            gt_clause = str(detail.get("clause_id") or "").strip()
            gt_dangling = [str(x).strip() for x in detail.get("dangling_xrefs", [])]

            localized = False
            for f in matching_findings:
                f_clause = str(f.clause_ref or "").strip()
                if gt_clause and f_clause == gt_clause:
                    localized = True
                    break
                # For clause_delete / xref_break, also match if dangling target matches
                if gt_dangling and f_clause in gt_dangling:
                    localized = True
                    break
                if gt_clause and f.details and str(f.details.get("missing_target") or "").strip() == gt_clause:
                    localized = True
                    break

            # If no clause label was provided in ground truth, don't penalize localization
            if not gt_clause and not gt_dangling:
                localized = type_correct

            localized_map[t_type] = localized

        results.append({
            "doc_id": doc_id,
            "source_type": item.get("source_type", "synthetic"),
            "is_tampered": item.get("is_tampered", False),
            "tamper_types": true_tamper_types,
            "tamper_details": tamper_details,
            "is_flagged": is_flagged,
            "findings": med_plus_findings,
            "finding_summaries": [
                {
                    "type": f.type,
                    "severity": f.severity.value,
                    "clause_ref": f.clause_ref,
                    "page": f.page,
                    "evidence": f.evidence[:200],
                    "explanation": f.explanation[:200],
                }
                for f in med_plus_findings
            ],
            "type_correct_map": type_correct_map,
            "localized_map": localized_map,
            "duration_ms": dur_ms,
        })

    # 1. Performance per target content tamper type
    recall_per_type: dict[str, dict[str, Any]] = {}
    for t_type in _TARGET_CONTENT_TAMPERS:
        relevant_docs = [r for r in results if t_type in r["tamper_types"]]
        total = len(relevant_docs)
        flagged = sum(1 for r in relevant_docs if r["is_flagged"])
        type_correct = sum(1 for r in relevant_docs if r["type_correct_map"].get(t_type, False))
        localized = sum(1 for r in relevant_docs if r["localized_map"].get(t_type, False))

        recall_per_type[t_type] = {
            "total": total,
            "flagged": flagged,
            "recall": round(flagged / total, 4) if total > 0 else 1.0,
            "type_correct": type_correct,
            "type_correctness_rate": round(type_correct / total, 4) if total > 0 else 1.0,
            "localized": localized,
            "localization_rate": round(localized / total, 4) if total > 0 else 1.0,
        }

    # 2. False positive rate on clean documents (separate synthetic vs CUAD)
    clean_synth_docs = [r for r in results if not r["is_tampered"] and r["source_type"] == "synthetic"]
    clean_cuad_docs = [r for r in results if not r["is_tampered"] and r["source_type"] != "synthetic"]

    clean_synth_total = len(clean_synth_docs)
    clean_synth_fp = sum(1 for r in clean_synth_docs if r["is_flagged"])
    clean_synth_fpr = round(clean_synth_fp / clean_synth_total, 4) if clean_synth_total > 0 else 0.0

    clean_cuad_total = len(clean_cuad_docs)
    clean_cuad_fp = sum(1 for r in clean_cuad_docs if r["is_flagged"])
    clean_cuad_fpr = round(clean_cuad_fp / clean_cuad_total, 4) if clean_cuad_total > 0 else 0.0

    # 3. Expected undetectable tamper flag rates
    expected_undetectable_stats: dict[str, dict[str, Any]] = {}
    for ut in _EXPECTED_UNDETECTABLE:
        u_docs = [
            r for r in results
            if ut in r["tamper_types"] and not any(t in r["tamper_types"] for t in _TARGET_CONTENT_TAMPERS)
        ]
        u_total = len(u_docs)
        u_flagged = sum(1 for r in u_docs if r["is_flagged"])
        expected_undetectable_stats[ut] = {
            "total": u_total,
            "flagged": u_flagged,
            "flag_rate": round(u_flagged / u_total, 4) if u_total > 0 else 0.0,
        }

    # 4. Latency percentiles
    sorted_lats = sorted(latencies_ms)
    p50 = round(_percentile(sorted_lats, 0.50), 2)
    p95 = round(_percentile(sorted_lats, 0.95), 2)
    p99 = round(_percentile(sorted_lats, 0.99), 2)
    mean_lat = round(sum(sorted_lats) / len(sorted_lats), 2) if sorted_lats else 0.0

    # 5. Misses and false positives for reporting
    misses_by_type: dict[str, list[dict[str, Any]]] = {}
    for t_type in _TARGET_CONTENT_TAMPERS:
        misses = [
            {
                "doc_id": r["doc_id"],
                "tamper_types": r["tamper_types"],
                "tamper_details": r["tamper_details"],
            }
            for r in results
            if t_type in r["tamper_types"] and not r["is_flagged"]
        ]
        misses_by_type[t_type] = misses[:5]

    cuad_clean_fp_docs = [
        {
            "doc_id": r["doc_id"],
            "findings": r["finding_summaries"],
        }
        for r in clean_cuad_docs
        if r["is_flagged"]
    ]

    return {
        "split_name": split_name,
        "total_documents": len(results),
        "recall_per_type": recall_per_type,
        "clean_synthetic": {
            "total": clean_synth_total,
            "false_positives": clean_synth_fp,
            "fpr": clean_synth_fpr,
        },
        "clean_cuad": {
            "total": clean_cuad_total,
            "false_positives": clean_cuad_fp,
            "fpr": clean_cuad_fpr,
        },
        "expected_undetectable": expected_undetectable_stats,
        "latency_stats": {
            "mean_ms": mean_lat,
            "p50_ms": p50,
            "p95_ms": p95,
            "p99_ms": p99,
        },
        "misses_by_type": misses_by_type,
        "cuad_clean_fp_docs": cuad_clean_fp_docs,
    }


def _print_evaluation_table(eval_result: dict[str, Any]) -> None:
    """Print human-readable evaluation summary table."""
    split = eval_result["split_name"]
    print(f"\n{'='*75}")
    print(f"MODULE 4 CONSISTENCY CHECKS EVALUATION REPORT: {split}")
    print(f"{'='*75}")
    print(f"Total documents evaluated: {eval_result['total_documents']}")
    print(f"Latency: p50={eval_result['latency_stats']['p50_ms']}ms, "
          f"p95={eval_result['latency_stats']['p95_ms']}ms, "
          f"mean={eval_result['latency_stats']['mean_ms']}ms")
    print("\n--- CONTENT TAMPER DETECTION ---")
    print(f"{'Tamper Type':<22} {'Total':<6} {'Flagged':<8} {'Recall':<10} {'Type Corr.':<12} {'Localized':<10}")
    print("-" * 75)
    for t_type, stats in eval_result["recall_per_type"].items():
        rec_str = f"{stats['recall']*100:.1f}%"
        type_str = f"{stats['type_correctness_rate']*100:.1f}%"
        loc_str = f"{stats['localization_rate']*100:.1f}%"
        print(f"{t_type:<22} {stats['total']:<6} {stats['flagged']:<8} {rec_str:<10} {type_str:<12} {loc_str:<10}")

    print("\n--- CLEAN DOCUMENT FALSE POSITIVES ---")
    cs = eval_result["clean_synthetic"]
    cc = eval_result["clean_cuad"]
    print(f"Clean Synthetic: {cs['false_positives']}/{cs['total']} ({cs['fpr']*100:.2f}%) [target <= 2.0%]")
    print(f"Clean CUAD:      {cc['false_positives']}/{cc['total']} ({cc['fpr']*100:.2f}%) [target <= 5.0%]")

    print("\n--- EXPECTED UNDETECTABLE TAMPERS ---")
    for ut, u_stats in eval_result["expected_undetectable"].items():
        if u_stats["total"] > 0:
            rate_str = f"{u_stats['flag_rate']*100:.1f}%"
            print(f"{ut:<28} Flagged {u_stats['flagged']}/{u_stats['total']} ({rate_str})")
    print(f"{'='*75}\n")


def generate_cuad_review(
    eval_results_train_val: dict[str, Any],
    eval_results_test: dict[str, Any],
    out_path: Path,
) -> None:
    """Write eval/results/consistency_cuad_review.md."""
    lines: list[str] = [
        "# CUAD Clean Document Consistency Review",
        "",
        "This document reviews every CUAD-derived clean contract that triggered a consistency finding",
        "of severity MEDIUM or higher, along with misses and false positives per tamper type.",
        "",
        "## Summary",
        "",
        f"- **Train/Val Clean CUAD FPs**: {eval_results_train_val['clean_cuad']['false_positives']} / {eval_results_train_val['clean_cuad']['total']} ({eval_results_train_val['clean_cuad']['fpr']*100:.1f}%)",
        f"- **Held-out Test Clean CUAD FPs**: {eval_results_test['clean_cuad']['false_positives']} / {eval_results_test['clean_cuad']['total']} ({eval_results_test['clean_cuad']['fpr']*100:.1f}%)",
        "",
    ]

    all_cuad_fps = (
        eval_results_train_val.get("cuad_clean_fp_docs", []) +
        eval_results_test.get("cuad_clean_fp_docs", [])
    )

    lines.append("## Detailed CUAD Clean Findings (Medium+ Severity)")
    lines.append("")
    if not all_cuad_fps:
        lines.append("No CUAD clean documents triggered findings of severity MEDIUM or higher (0 false positives).")
        lines.append("")
    else:
        for item in all_cuad_fps:
            doc_id = item["doc_id"]
            lines.append(f"### Document: `{doc_id}`")
            for f in item["findings"]:
                lines.append(f"- **Finding Type**: `{f['type']}`")
                lines.append(f"  - **Severity**: `{f['severity']}`")
                lines.append(f"  - **Page**: {f['page']}")
                lines.append(f"  - **Clause Ref**: {f['clause_ref']}")
                lines.append(f"  - **Evidence**: `{f['evidence']}`")
                lines.append(f"  - **Explanation**: {f['explanation']}")
            lines.append("")

    lines.append("## Misses by Tamper Type (up to 5 per type)")
    lines.append("")
    for split_res in (eval_results_train_val, eval_results_test):
        sname = split_res["split_name"]
        lines.append(f"### Split: {sname}")
        for t_type, misses in split_res["misses_by_type"].items():
            lines.append(f"#### `{t_type}` (Miss count: {len(misses)})")
            if not misses:
                lines.append("No misses recorded (100% recall).")
            else:
                for m in misses:
                    lines.append(f"- Document `{m['doc_id']}`: details: {m['tamper_details']}")
            lines.append("")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run ClauseGuard Module 4 Consistency Evaluation")
    parser.add_argument("--data", type=str, default="data/generated", help="Path to data/generated directory")
    parser.add_argument("--out", type=str, default=None, help="Output JSON path")
    args = parser.parse_args()

    data_dir = Path(args.data)
    labels_file = data_dir / "labels.jsonl"
    if not labels_file.exists():
        print(f"Error: labels file not found at {labels_file}", file=sys.stderr)
        sys.exit(1)

    items: list[dict[str, Any]] = []
    with open(labels_file, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                items.append(json.loads(line))

    # Split into train/val and test
    train_val_items = [it for it in items if it.get("split") in ("train", "val")]
    test_items = [it for it in items if it.get("split") == "test"]

    settings = ConsistencySettings()

    print(f"Running Module 4 Consistency Evaluation on {len(items)} documents...")
    print(f"Train/Val: {len(train_val_items)} documents, Test: {len(test_items)} documents")

    train_val_res = evaluate_split("Train/Val", train_val_items, data_dir, settings)
    _print_evaluation_table(train_val_res)

    test_res = evaluate_split("Held-out Test", test_items, data_dir, settings)
    _print_evaluation_table(test_res)

    # Date string for json
    today = datetime.date.today().strftime("%Y%m%d")
    out_dir = Path("eval/results")
    out_dir.mkdir(parents=True, exist_ok=True)

    json_path = Path(args.out) if args.out else out_dir / f"consistency_{today}.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump({"train_val": train_val_res, "test": test_res}, f, indent=2, default=str)
    print(f"Wrote full results to {json_path}")

    cuad_review_path = out_dir / "consistency_cuad_review.md"
    generate_cuad_review(train_val_res, test_res, cuad_review_path)
    print(f"Wrote CUAD review file to {cuad_review_path}")


if __name__ == "__main__":
    main()
