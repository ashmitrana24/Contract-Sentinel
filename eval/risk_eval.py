"""Risk summary evaluation benchmark (Module 8).

Evaluates the distribution of risk bands across document categories:
- clean synthetic
- clean CUAD-derived
- file-level tampers (incremental_edit, hidden_text, etc.)
- content-level tampers (amount_figure_only, date_shift, xref_break, party_swap, clause_delete)

Targets:
- clean synthetic: "low" >= 98%
- incremental_edit: "high" >= 95%
- hidden_text: "high" >= 95%
- amount_figure_only: "medium" or "high" >= 90%
- date_shift: "medium" or "high" >= 90%
- xref_break: "medium" or "high" >= 90%
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

# Ensure backend/src is on sys.path
_ROOT = Path(__file__).resolve().parent.parent
_BACKEND_SRC = _ROOT / "backend" / "src"
if str(_BACKEND_SRC) not in sys.path:
    sys.path.insert(0, str(_BACKEND_SRC))

from clauseguard.config import get_settings
from clauseguard.consistency import ConsistencySettings
from clauseguard.consistency import analyze as analyze_consistency
from clauseguard.forensics.models import ForensicsSettings
from clauseguard.forensics.run import analyze as analyze_forensics
from clauseguard.parsing.parse_document import parse_document
from clauseguard.risk.aggregate import summarize


def evaluate_dataset(data_dir: Path) -> dict[str, Any]:
    labels_file = data_dir / "labels.jsonl"
    if not labels_file.exists():
        labels_file = data_dir / "labels.json"
    if not labels_file.exists():
        raise FileNotFoundError(f"No labels file found in {data_dir}")

    records: list[dict[str, Any]] = []
    if labels_file.suffix == ".jsonl":
        for line in labels_file.read_text(encoding="utf-8").splitlines():
            if line.strip():
                records.append(json.loads(line))
    else:
        records = json.loads(labels_file.read_text(encoding="utf-8"))

    settings = get_settings()
    f_settings = ForensicsSettings(budget_seconds=20.0)
    c_settings = ConsistencySettings(budget_seconds=10.0)

    # Categories to evaluate
    category_counts: dict[str, dict[str, int]] = {}

    print(f"\nEvaluating dataset: {data_dir} ({len(records)} documents)")
    start_t = time.monotonic()

    for idx, rec in enumerate(records):
        doc_id = rec["doc_id"]
        pdf_path = data_dir / f"{doc_id}.pdf"
        if not pdf_path.exists():
            continue

        pdf_bytes = pdf_path.read_bytes()
        try:
            parsed = parse_document(pdf_bytes)
            f_rep = analyze_forensics(pdf_bytes, f_settings)
            c_rep = analyze_consistency(parsed, c_settings)
        except Exception as exc:
            print(f"Error processing {doc_id}: {exc}")
            continue

        all_findings = list(f_rep.findings) + list(c_rep.findings)
        cov_inputs = {
            "needs_ocr": parsed.needs_ocr,
            "clause_count": len(parsed.clauses),
            "unsegmented": len(parsed.clauses) < 2 or any(c.kind == "unsegmented" for c in parsed.clauses),
            "analysis_runs": [
                {
                    "module": "pdf_forensics",
                    "status": f_rep.status,
                    "detector_status": {"detectors": [d.model_dump() for d in f_rep.detectors]},
                },
                {
                    "module": "consistency",
                    "status": c_rep.status,
                    "detector_status": {"detectors": [d.model_dump() for d in c_rep.detectors]},
                },
            ],
        }

        summary = summarize(all_findings, cov_inputs, settings)
        band = summary.band

        # Assign document to one or more evaluation categories
        is_tampered = rec.get("is_tampered", False)
        source_type = rec.get("source_type", "synthetic")
        tamper_types = rec.get("tamper_types", [])

        cats: list[str] = []
        if not is_tampered:
            if source_type == "synthetic":
                cats.append("clean_synthetic")
            else:
                cats.append("clean_cuad")
        else:
            for tt in tamper_types:
                cats.append(f"tamper_{tt}")
            if rec.get("tamper_class") == "file":
                cats.append("file_level_tampers")

        for cat in cats:
            if cat not in category_counts:
                category_counts[cat] = {"low": 0, "medium": 0, "high": 0, "total": 0}
            category_counts[cat][band] += 1
            category_counts[cat]["total"] += 1

        if (idx + 1) % 50 == 0 or idx + 1 == len(records):
            elapsed = time.monotonic() - start_t
            print(f"  Processed {idx + 1}/{len(records)} docs ({elapsed:.1f}s)...")

    return category_counts


def print_results_table(category_counts: dict[str, dict[str, int]]) -> dict[str, str]:
    # Target definitions: (target_description, eval_function)
    targets = {
        "clean_synthetic": ("Low >= 98%", lambda c: (c["low"] / c["total"]) >= 0.98 if c["total"] else False),
        "tamper_incremental_edit": ("High >= 95%", lambda c: (c["high"] / c["total"]) >= 0.95 if c["total"] else False),
        "tamper_hidden_text": ("High >= 95%", lambda c: (c["high"] / c["total"]) >= 0.95 if c["total"] else False),
        "tamper_amount_figure_only": (
            "Med/High >= 90%",
            lambda c: ((c["medium"] + c["high"]) / c["total"]) >= 0.90 if c["total"] else False,
        ),
        "tamper_date_shift": (
            "Med/High >= 90%",
            lambda c: ((c["medium"] + c["high"]) / c["total"]) >= 0.90 if c["total"] else False,
        ),
        "tamper_xref_break": (
            "Med/High >= 90%",
            lambda c: ((c["medium"] + c["high"]) / c["total"]) >= 0.90 if c["total"] else False,
        ),
    }

    results_status: dict[str, str] = {}

    print("\n" + "=" * 90)
    print(f"{'Category':<30} {'Total':<8} {'Low %':<10} {'Med %':<10} {'High %':<10} {'Target':<15} {'Status'}")
    print("-" * 90)

    # Sort categories with targets first
    priority_order = [
        "clean_synthetic",
        "tamper_incremental_edit",
        "tamper_hidden_text",
        "tamper_amount_figure_only",
        "tamper_date_shift",
        "tamper_xref_break",
        "clean_cuad",
        "file_level_tampers",
        "tamper_party_swap",
        "tamper_clause_delete",
    ]
    all_cats = list(priority_order) + [c for c in sorted(category_counts.keys()) if c not in priority_order]

    for cat in all_cats:
        if cat not in category_counts:
            continue
        c = category_counts[cat]
        tot = c["total"]
        if tot == 0:
            continue
        low_pct = f"{c['low'] / tot * 100:.1f}%"
        med_pct = f"{c['medium'] / tot * 100:.1f}%"
        high_pct = f"{c['high'] / tot * 100:.1f}%"

        target_str = "-"
        status_str = "REPORT ONLY"
        if cat in targets:
            target_desc, fn = targets[cat]
            target_str = target_desc
            is_met = fn(c)
            status_str = "MET" if is_met else "MISSED"
            results_status[cat] = status_str

        print(f"{cat:<30} {tot:<8} {low_pct:<10} {med_pct:<10} {high_pct:<10} {target_str:<15} {status_str}")

    print("=" * 90)
    return results_status


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate ClauseGuard Risk Bands")
    parser.add_argument(
        "--data-dir",
        type=str,
        default="data/generated",
        help="Path to generated data directory",
    )
    args = parser.parse_args()

    data_path = Path(args.data_dir).resolve()
    counts = evaluate_dataset(data_path)
    print_results_table(counts)


if __name__ == "__main__":
    main()
