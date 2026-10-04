"""Forensics evaluation and benchmark suite.

Runs the full detector suite against a directory of labeled PDFs (or a built-in
synthetic benchmark suite) and computes:
- Precision, Recall, F1 per tamper type
- Overall precision, recall, F1
- False positive rate on clean documents
- Latency statistics (mean, p50, p95, p99) per document
- Structured JSON report and Markdown summary table.

Usage:
  python -m eval.forensics_eval --dataset-dir ../datagen/data/generated
  python -m eval.forensics_eval --synthetic --out eval/results/eval_report.json
"""

from __future__ import annotations

import argparse
import json
import logging
import math
import time
from pathlib import Path
from typing import Any

from clauseguard.forensics.models import ForensicsSettings
from clauseguard.forensics.run import analyze

logger = logging.getLogger(__name__)


def _percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
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
    dataset.append(("tampered_hidden_sub1pt", make_hidden_text_pdf("sub_1pt"), True, ["hidden_text"]))
    dataset.append(("tampered_hidden_occluded", make_hidden_text_pdf("occluded"), True, ["hidden_text"]))
    dataset.append(("tampered_hidden_offpage", make_hidden_text_pdf("offpage"), True, ["hidden_text"]))
    dataset.append(("tampered_active_js", make_active_content_pdf("javascript"), True, ["active_content"]))
    dataset.append(("tampered_active_launch", make_active_content_pdf("launch"), True, ["active_content"]))
    dataset.append(("tampered_meta_future", make_metadata_pdf("future_date"), True, ["metadata_anomaly"]))
    dataset.append(("tampered_meta_reversed", make_metadata_pdf("mod_before_create"), True, ["metadata_anomaly"]))
    dataset.append(("tampered_sig_byte_corrupt", make_signed_pdf(corrupt_bytes=True), True, ["signature_invalid"]))
    dataset.append(("tampered_sig_post_edit", make_signed_pdf(modify_after=True), True, ["post_signature_modification"]))

    return dataset


def run_evaluation(
    dataset: list[tuple[str, bytes, bool, list[str]]],
    settings: ForensicsSettings | None = None,
) -> dict[str, Any]:
    if settings is None:
        settings = ForensicsSettings()

    latencies_ms: list[float] = []

    # Map finding types to generic evaluation tamper categories
    category_map = {
        "incremental_update": "incremental_edit",
        "hidden_text": "hidden_text",
        "active_content": "active_content",
        "annotation_overlay": "active_content",
        "metadata_anomaly": "metadata_anomaly",
        "signature_invalid": "signature_invalid",
        "post_signature_modification": "post_signature_modification",
    }

    # Per-category metrics: TP, FP, FN, TN
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

        # Detected categories
        detected_categories = set()
        for f in report.findings:
            cat = category_map.get(f.type, f.type)
            detected_categories.add(cat)

        expected_categories = set(true_tamper_types)

        if not is_tampered:
            total_clean += 1
            # For clean docs, any high/critical finding is a severe false alarm
            high_crit = [f for f in report.findings if f.severity in ("high", "critical")]
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

    # Compute precision, recall, F1
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


def format_markdown_table(eval_result: dict[str, Any]) -> str:
    summary = eval_result["summary"]
    lat = eval_result["latency_stats"]
    cats = eval_result["per_category"]

    lines = [
        "# PDF Structure Forensics — Evaluation Report",
        "",
        "## Overall Summary",
        f"- **Total Documents**: {summary['total_documents']}",
        f"- **Clean Documents**: {summary['clean_documents']} (FPR on High/Critical: {summary['clean_false_positive_rate'] * 100:.1f}%)",
        f"- **Overall Precision**: {summary['overall_precision'] * 100:.1f}%",
        f"- **Overall Recall**: {summary['overall_recall'] * 100:.1f}%",
        f"- **Overall F1 Score**: {summary['overall_f1'] * 100:.1f}%",
        "",
        "## Latency Statistics",
        f"- **Mean**: {lat['mean_ms']:.1f} ms",
        f"- **p50**: {lat['p50_ms']:.1f} ms",
        f"- **p95**: {lat['p95_ms']:.1f} ms",
        f"- **p99**: {lat['p99_ms']:.1f} ms",
        "",
        "## Performance per Tamper Category",
        "| Category | TP | FP | FN | Precision | Recall | F1 Score |",
        "|---|---|---|---|---|---|---|",
    ]

    for cat, m in sorted(cats.items()):
        lines.append(
            f"| `{cat}` | {m['tp']} | {m['fp']} | {m['fn']} | {m['precision'] * 100:.1f}% | {m['recall'] * 100:.1f}% | {m['f1'] * 100:.1f}% |"
        )

    lines.append("")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Evaluate PDF Forensics detectors.")
    parser.add_argument("--dataset-dir", type=str, default="", help="Path to generated dataset directory")
    parser.add_argument("--synthetic", action="store_true", default=True, help="Run on synthetic benchmark suite")
    parser.add_argument("--out", type=str, default="eval/results/eval_report.json", help="Path to write JSON report")
    args = parser.parse_args()

    dataset: list[tuple[str, bytes, bool, list[str]]] = []

    if args.dataset_dir and Path(args.dataset_dir).exists():
        ds_path = Path(args.dataset_dir)
        labels_file = ds_path / "labels.jsonl"
        if labels_file.exists():
            for line in labels_file.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                label_data = json.loads(line)
                doc_id = label_data["doc_id"]
                pdf_path = ds_path / "pdfs" / f"{doc_id}.pdf"
                if pdf_path.exists():
                    dataset.append((
                        doc_id,
                        pdf_path.read_bytes(),
                        label_data.get("is_tampered", False),
                        label_data.get("tamper_types", []),
                    ))

    if not dataset:
        dataset = _generate_synthetic_eval_dataset()

    result = run_evaluation(dataset)
    md_table = format_markdown_table(result)

    print(md_table)  # noqa: T201

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(result, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
