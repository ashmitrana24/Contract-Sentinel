"""Module 3: PDF Forensics Evaluation Benchmark.

Evaluates PDF structure forensics detectors on:
1. Module 1 synthetic/generated dataset (train/val split and held-out test split)
2. Synthetic unit benchmark suite (--synthetic)
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import time
from pathlib import Path
from typing import Any

from clauseguard.forensics.models import ForensicsSettings
from clauseguard.forensics.run import analyze
from clauseguard.schemas.findings import Severity


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


def _generate_synthetic_eval_dataset() -> list[tuple[str, bytes, bool, list[str]]]:
    """Generate synthetic dataset of clean and tampered PDFs for benchmarking."""
    try:
        from .synthetic import (
            make_active_content_pdf,
            make_hidden_text_pdf,
            make_incremental_pdf,
            make_metadata_pdf,
            make_pdf_with_form_fields,
            make_pdf_with_headers_footers,
            make_pdf_with_highlights,
            make_pdf_with_links,
            make_plain_pdf,
            make_signed_pdf,
            make_word_like_pdf,
        )
    except ImportError:
        from eval.synthetic import (
            make_active_content_pdf,
            make_hidden_text_pdf,
            make_incremental_pdf,
            make_metadata_pdf,
            make_pdf_with_form_fields,
            make_pdf_with_headers_footers,
            make_pdf_with_highlights,
            make_pdf_with_links,
            make_plain_pdf,
            make_signed_pdf,
            make_word_like_pdf,
        )

    dataset: list[tuple[str, bytes, bool, list[str]]] = []

    # Clean documents
    dataset.append(("clean_plain", make_plain_pdf(), False, []))
    dataset.append(("clean_headers", make_pdf_with_headers_footers(), False, []))
    dataset.append(("clean_links", make_pdf_with_links(), False, []))
    dataset.append(("clean_highlights", make_pdf_with_highlights(), False, []))
    dataset.append(("clean_forms", make_pdf_with_form_fields(), False, []))
    dataset.append(("clean_word", make_word_like_pdf(), False, []))
    dataset.append(("clean_signed", make_signed_pdf(), False, []))

    # Tampered documents
    dataset.append(("tampered_incremental_text", make_incremental_pdf(edit_text=True), True, ["incremental_edit"]))
    dataset.append(("tampered_incremental_amount", make_incremental_pdf(edit_amount=True), True, ["incremental_edit"]))
    dataset.append(("tampered_hidden_white", make_hidden_text_pdf("white_on_white"), True, ["hidden_text"]))
    dataset.append(("tampered_hidden_tiny", make_hidden_text_pdf("tiny_text"), True, ["hidden_text"]))
    dataset.append(("tampered_hidden_offpage", make_hidden_text_pdf("offpage"), True, ["hidden_text"]))
    dataset.append(("tampered_hidden_render_mode", make_hidden_text_pdf("invisible_render_mode"), True, ["hidden_text"]))
    dataset.append(("tampered_hidden_occluded", make_hidden_text_pdf("occluded"), True, ["hidden_text"]))
    dataset.append(("tampered_signed_modified", make_signed_pdf(modify_after=True), True, ["post_signature_modification"]))
    dataset.append(("tampered_signed_corrupt", make_signed_pdf(corrupt_bytes=True), True, ["signature_invalid"]))
    dataset.append(("tampered_metadata_reversed", make_metadata_pdf("reversed_dates"), True, ["metadata_anomaly"]))
    dataset.append(("tampered_active_js", make_active_content_pdf("javascript"), True, ["active_content"]))
    dataset.append(("tampered_active_launch", make_active_content_pdf("launch_action"), True, ["active_content"]))

    return dataset


def evaluate_split(
    split_name: str,
    items: list[dict[str, Any]],
    data_dir: Path,
    settings: ForensicsSettings | None = None,
) -> dict[str, Any]:
    """Evaluate detector performance on a labeled split (train/val or test)."""
    if settings is None:
        settings = ForensicsSettings()

    latencies_ms: list[float] = []
    results: list[dict[str, Any]] = []

    page_matches = 0
    evidence_matches = 0
    incr_total = 0

    for item in items:
        doc_id = item["doc_id"]
        pdf_path = data_dir / f"{doc_id}.pdf"
        if not pdf_path.exists():
            pdf_path = data_dir / "pdfs" / f"{doc_id}.pdf"
        if not pdf_path.exists():
            continue

        pdf_bytes = pdf_path.read_bytes()
        t0 = time.monotonic()
        report = analyze(pdf_bytes, settings)
        dur_ms = (time.monotonic() - t0) * 1000
        latencies_ms.append(dur_ms)

        med_plus_findings = [
            f for f in report.findings
            if f.severity in (Severity.MEDIUM, Severity.HIGH, Severity.CRITICAL)
        ]
        is_flagged = len(med_plus_findings) > 0

        # Ground truth positives are file-level tampers
        true_tamper_types = item.get("tamper_types", [])
        file_tampers = [t for t in true_tamper_types if t in ("incremental_edit", "hidden_text")]
        is_gt_positive = len(file_tampers) > 0

        # Incremental localization matching
        if "incremental_edit" in file_tampers:
            incr_total += 1
            incr_findings = [
                f for f in rep_findings_all(report)
                if f.type == "incremental_update"
                and f.severity in (Severity.MEDIUM, Severity.HIGH, Severity.CRITICAL)
            ]
            detail = next(
                (d for d in item.get("tamper_details", []) if d.get("tamper_type") == "incremental_edit"),
                None,
            )
            if detail:
                gt_p = detail.get("page")
                gt_p1 = gt_p + 1 if gt_p is not None else None
                gt_val = detail.get("tampered_value")
                p_match = False
                ev_match = False
                for f in incr_findings:
                    ch_pages = f.details.get("changed_pages", [])
                    if gt_p1 is not None and (f.page == gt_p1 or gt_p1 in ch_pages):
                        p_match = True
                    if gt_val and (gt_val in f.evidence or any(gt_val in str(v) for v in f.details.values())):
                        ev_match = True
                if p_match:
                    page_matches += 1
                if ev_match:
                    evidence_matches += 1

        results.append({
            "doc_id": doc_id,
            "gt_positive": is_gt_positive,
            "is_flagged": is_flagged,
            "file_tampers": file_tampers,
            "tamper_class": item.get("tamper_class"),
            "tamper_types": true_tamper_types,
            "tamper_details": item.get("tamper_details", []),
            "finding_count": len(report.findings),
            "med_plus_count": len(med_plus_findings),
            "findings": [(f.type, f.severity.value, f.explanation) for f in med_plus_findings],
            "duration_ms": dur_ms,
        })

    tp = sum(1 for r in results if r["gt_positive"] and r["is_flagged"])
    fp = sum(1 for r in results if not r["gt_positive"] and r["is_flagged"])
    fn = sum(1 for r in results if r["gt_positive"] and not r["is_flagged"])
    tn = sum(1 for r in results if not r["gt_positive"] and not r["is_flagged"])

    clean_docs = [r for r in results if r["tamper_class"] is None]
    clean_fp = sum(1 for r in clean_docs if r["is_flagged"])
    content_docs = [r for r in results if r["tamper_class"] == "content" and not r["gt_positive"]]
    content_fp = sum(1 for r in content_docs if r["is_flagged"])

    prec = tp / (tp + fp) if (tp + fp) > 0 else (1.0 if fn == 0 else 0.0)
    rec = tp / (tp + fn) if (tp + fn) > 0 else (1.0 if fp == 0 else 0.0)
    f1 = (2 * prec * rec) / (prec + rec) if (prec + rec) > 0 else 0.0

    # Recall per tamper type
    recall_per_type = {}
    for tt in ("incremental_edit", "hidden_text"):
        docs_tt = [r for r in results if tt in r["file_tampers"]]
        tp_tt = sum(1 for r in docs_tt if r["is_flagged"])
        rec_tt = tp_tt / len(docs_tt) if docs_tt else 1.0
        recall_per_type[tt] = {
            "tp": tp_tt,
            "total": len(docs_tt),
            "recall": round(rec_tt, 4),
        }

    lats = sorted(latencies_ms)
    p50 = _percentile(lats, 0.50)
    p95 = _percentile(lats, 0.95)
    p99 = _percentile(lats, 0.99)
    mean_lat = sum(lats) / len(lats) if lats else 0.0

    misses = [r for r in results if r["gt_positive"] and not r["is_flagged"]]
    false_positives = [r for r in results if not r["gt_positive"] and r["is_flagged"]]

    return {
        "split_name": split_name,
        "total_documents": len(results),
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "tn": tn,
        "precision": round(prec, 4),
        "recall": round(rec, 4),
        "f1": round(f1, 4),
        "recall_per_type": recall_per_type,
        "clean_documents": len(clean_docs),
        "clean_false_positive_rate": round(clean_fp / len(clean_docs), 4) if clean_docs else 0.0,
        "clean_false_positives": clean_fp,
        "content_documents": len(content_docs),
        "content_false_positive_rate": round(content_fp / len(content_docs), 4) if content_docs else 0.0,
        "content_false_positives": content_fp,
        "incremental_total": incr_total,
        "incremental_page_match_rate": round(page_matches / incr_total, 4) if incr_total else 1.0,
        "incremental_page_matches": page_matches,
        "incremental_evidence_tampered_value_rate": round(evidence_matches / incr_total, 4) if incr_total else 1.0,
        "incremental_evidence_matches": evidence_matches,
        "latency_stats": {
            "mean_ms": round(mean_lat, 2),
            "p50_ms": round(p50, 2),
            "p95_ms": round(p95, 2),
            "p99_ms": round(p99, 2),
        },
        "misses": misses[:5],
        "false_positives": false_positives[:5],
    }


def rep_findings_all(report) -> list:
    return report.findings


def format_split_markdown(res: dict[str, Any]) -> str:
    """Format evaluation results into GitHub markdown."""
    name = res["split_name"]
    lat = res["latency_stats"]
    lines = [
        f"## {name} Split Results",
        "",
        f"- **Total Documents**: {res['total_documents']}",
        f"- **Confusion Matrix**: TP={res['tp']}, FP={res['fp']}, FN={res['fn']}, TN={res['tn']}",
        f"- **Precision**: {res['precision'] * 100:.2f}%",
        f"- **Recall**: {res['recall'] * 100:.2f}%",
        f"- **F1 Score**: {res['f1'] * 100:.2f}%",
        "",
        "### Recall per Tamper Type",
    ]

    for tt, stat in res["recall_per_type"].items():
        lines.append(f"- **`{tt}`**: {stat['tp']}/{stat['total']} ({stat['recall'] * 100:.1f}%)")

    lines.extend([
        "",
        "### False Positive Rates",
        (
            f"- **Clean Documents (Ground Truth Clean)**: "
            f"{res['clean_false_positives']}/{res['clean_documents']} "
            f"({res['clean_false_positive_rate'] * 100:.2f}%)"
        ),
        (
            f"- **Content-Tampered Documents (Not File-Level)**: "
            f"{res['content_false_positives']}/{res['content_documents']} "
            f"({res['content_false_positive_rate'] * 100:.2f}%)"
        ),
    ])

    if res["incremental_total"] > 0:
        lines.extend([
            "",
            "### Incremental Edit Localization",
            (
                f"- **Page Match Rate**: "
                f"{res['incremental_page_matches']}/{res['incremental_total']} "
                f"({res['incremental_page_match_rate'] * 100:.1f}%)"
            ),
            (
                f"- **Evidence Contains Tampered Value**: "
                f"{res['incremental_evidence_matches']}/{res['incremental_total']} "
                f"({res['incremental_evidence_tampered_value_rate'] * 100:.1f}%)"
            ),
        ])

    lines.extend([
        "",
        "### Latency Percentiles",
        f"- **Mean**: {lat['mean_ms']} ms",
        f"- **p50**: {lat['p50_ms']} ms",
        f"- **p95**: {lat['p95_ms']} ms",
        f"- **p99**: {lat['p99_ms']} ms",
    ])

    if res["misses"]:
        lines.extend(["", "### Misses (False Negatives)", ""])
        for m in res["misses"]:
            lines.append(f"- `{m['doc_id']}`: {m['file_tampers']} (Details: {m['tamper_details']})")
    else:
        lines.extend(["", "### Misses: None (0 false negatives)"])

    if res["false_positives"]:
        lines.extend(["", "### False Positives (Clean or Content-Tampered Flagged Medium+)", ""])
        for fp in res["false_positives"]:
            lines.append(f"- `{fp['doc_id']}` ({fp['tamper_class']}): {fp['findings']}")
    else:
        lines.extend(["", "### False Positives: None (0 false alarms on clean & content-tampered)"])

    lines.append("")
    return "\n".join(lines)


def run_evaluation(
    dataset: list[tuple[str, bytes, bool, list[str]]],
    settings: ForensicsSettings | None = None,
) -> dict[str, Any]:
    """Run evaluation on generic dataset tuples for synthetic testing."""
    if settings is None:
        settings = ForensicsSettings()

    latencies_ms: list[float] = []
    category_map = {
        "incremental_update": "incremental_edit",
        "hidden_text": "hidden_text",
        "active_content": "active_content",
        "annotation_overlay": "active_content",
        "metadata_anomaly": "metadata_anomaly",
        "signature_invalid": "signature_invalid",
        "post_signature_modification": "post_signature_modification",
    }
    all_categories = {
        "incremental_edit",
        "hidden_text",
        "active_content",
        "metadata_anomaly",
        "signature_invalid",
        "post_signature_modification",
    }
    stats = {cat: {"tp": 0, "fp": 0, "fn": 0, "tn": 0} for cat in all_categories}
    total_clean = 0
    clean_false_positives = 0
    results: list[dict[str, Any]] = []

    for doc_id, pdf_bytes, is_tampered, true_tamper_types in dataset:
        t0 = time.monotonic()
        report = analyze(pdf_bytes, settings)
        dur_ms = (time.monotonic() - t0) * 1000
        latencies_ms.append(dur_ms)

        detected_categories = set()
        for f in report.findings:
            cat = category_map.get(f.type, f.type)
            detected_categories.add(cat)

        expected_categories = set(true_tamper_types)

        if not is_tampered:
            total_clean += 1
            high_crit = [f for f in report.findings if f.severity in (Severity.MEDIUM, Severity.HIGH, Severity.CRITICAL)]
            if len(high_crit) > 0:
                clean_false_positives += 1

        for cat in all_categories:
            exp = cat in expected_categories
            det = cat in detected_categories
            if exp and det:
                stats[cat]["tp"] += 1
            elif not exp and det:
                stats[cat]["fp"] += 1
            elif exp and not det:
                stats[cat]["fn"] += 1
            else:
                stats[cat]["tn"] += 1

        results.append({
            "doc_id": doc_id,
            "is_tampered": is_tampered,
            "expected": list(expected_categories),
            "detected": list(detected_categories),
            "finding_count": len(report.findings),
            "duration_ms": dur_ms,
        })

    category_metrics = {}
    total_tp = 0
    total_fp = 0
    total_fn = 0
    for cat, s in stats.items():
        tp, fp, fn = s["tp"], s["fp"], s["fn"]
        total_tp += tp
        total_fp += fp
        total_fn += fn
        prec = tp / (tp + fp) if (tp + fp) > 0 else (1.0 if fn == 0 else 0.0)
        rec = tp / (tp + fn) if (tp + fn) > 0 else (1.0 if fp == 0 else 0.0)
        f1 = (2 * prec * rec) / (prec + rec) if (prec + rec) > 0 else 0.0
        category_metrics[cat] = {
            "tp": tp,
            "fp": fp,
            "fn": fn,
            "precision": round(prec, 4),
            "recall": round(rec, 4),
            "f1": round(f1, 4),
        }

    overall_prec = total_tp / (total_tp + total_fp) if (total_tp + total_fp) > 0 else 1.0
    overall_rec = total_tp / (total_tp + total_fn) if (total_tp + total_fn) > 0 else 1.0
    overall_f1 = (2 * overall_prec * overall_rec) / (overall_prec + overall_rec) if (overall_prec + overall_rec) > 0 else 0.0
    fpr_clean = clean_false_positives / total_clean if total_clean > 0 else 0.0

    latencies_sorted = sorted(latencies_ms)
    latency_stats = {
        "count": len(latencies_ms),
        "mean_ms": round(sum(latencies_ms) / len(latencies_ms), 2) if latencies_ms else 0.0,
        "p50_ms": round(_percentile(latencies_sorted, 0.50), 2),
        "p95_ms": round(_percentile(latencies_sorted, 0.95), 2),
        "p99_ms": round(_percentile(latencies_sorted, 0.99), 2),
    }

    return {
        "summary": {
            "total_documents": len(dataset),
            "clean_documents": total_clean,
            "clean_false_positive_rate": round(fpr_clean, 4),
            "overall_precision": round(overall_prec, 4),
            "overall_recall": round(overall_rec, 4),
            "overall_f1": round(overall_f1, 4),
        },
        "per_category": category_metrics,
        "latency_stats": latency_stats,
        "document_results": results,
    }


def main():
    parser = argparse.ArgumentParser(description="Evaluate PDF Forensics detectors.")
    parser.add_argument("--data", "--dataset-dir", dest="data_dir", type=str, default="", help="Path to generated dataset directory")
    parser.add_argument("--synthetic", action="store_true", default=False, help="Run on synthetic benchmark suite")
    parser.add_argument("--out", type=str, default="eval/results/eval_report.json", help="Path to write JSON report")
    args = parser.parse_args()

    # Locate dataset directory if specified
    data_dir: Path | None = None
    if args.data_dir:
        cand = Path(args.data_dir)
        if cand.exists():
            data_dir = cand
        elif (Path("..") / args.data_dir).exists():
            data_dir = Path("..") / args.data_dir

    if data_dir and not args.synthetic:
        # Load Module 1 dataset
        labels_file = data_dir / "labels.jsonl"
        if not labels_file.exists():
            labels_file = data_dir / "labels.json"

        if not labels_file.exists():
            print(f"Error: labels file not found in {data_dir}", file=sys.stderr)  # noqa: T201
            sys.exit(1)

        if labels_file.suffix == ".jsonl":
            labels = [json.loads(line) for line in labels_file.read_text(encoding="utf-8").splitlines() if line.strip()]
        else:
            labels = json.loads(labels_file.read_text(encoding="utf-8"))

        train_val_items = [item for item in labels if item.get("split") in ("train", "val")]
        test_items = [item for item in labels if item.get("split") == "test"]

        print("# ClauseGuard Module 3: PDF Forensics Evaluation\n")  # noqa: T201

        # Train/Val evaluation
        train_val_res = evaluate_split("Train/Val", train_val_items, data_dir)
        print(format_split_markdown(train_val_res))  # noqa: T201

        # Held-out Test evaluation
        test_res = evaluate_split("Held-out Test", test_items, data_dir)
        print(format_split_markdown(test_res))  # noqa: T201

        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps({"train_val": train_val_res, "test": test_res}, indent=2), encoding="utf-8")
        return

    # Fallback to synthetic suite
    dataset = _generate_synthetic_eval_dataset()
    result = run_evaluation(dataset)
    print(json.dumps(result, indent=2))  # noqa: T201


if __name__ == "__main__":
    main()
