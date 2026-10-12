"""CUAD unseen scan: run consistency analysis ONCE on the 310 unseen CUAD v1 contracts.

Obtains the remaining 310 CUAD v1 contracts (not among the 200 diagnostic contracts),
runs the final detector on them once with no tuning, and outputs:
- eval/results/consistency_unseen_review.md
- eval/results/cuad_unseen_scan.json
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

# Ensure backend/src is on sys.path
_BACKEND_SRC = Path(__file__).resolve().parent.parent / "backend" / "src"
if str(_BACKEND_SRC) not in sys.path:
    sys.path.insert(0, str(_BACKEND_SRC))

from clauseguard.consistency.models import ConsistencySettings
from clauseguard.consistency.run import analyze
from clauseguard.parsing.clauses import segment_clauses
from clauseguard.schemas.findings import Severity
from clauseguard.schemas.parsed import PageModel, ParsedDocument

_DIAGNOSTIC_DIR = Path(__file__).resolve().parent.parent / "data" / "raw" / "cuad"


def parse_raw_text(raw: str) -> ParsedDocument | None:
    """Convert raw contract text into ParsedDocument using page chunking."""
    if not raw.strip():
        return None

    pages = []
    current_lines = []
    current_chars = 0
    for line in raw.splitlines(keepends=True):
        current_lines.append(line)
        current_chars += len(line)
        if current_chars >= 3000:
            chunk = "".join(current_lines)
            pages.append(
                PageModel(
                    page_no=len(pages) + 1,
                    width=612.0,
                    height=792.0,
                    text=chunk,
                    char_count=len(chunk),
                )
            )
            current_lines = []
            current_chars = 0
    if current_lines:
        chunk = "".join(current_lines)
        pages.append(
            PageModel(
                page_no=len(pages) + 1,
                width=612.0,
                height=792.0,
                text=chunk,
                char_count=len(chunk),
            )
        )

    clauses = segment_clauses(pages)
    return ParsedDocument(
        page_count=len(pages),
        pages=pages,
        clauses=clauses,
    )


def main() -> None:
    # 1. Locate CUAD_v1.json
    cache_path = Path.home() / ".cache" / "huggingface" / "hub" / "datasets--TheAtticusProject--cuad"
    json_candidates = list(cache_path.glob("**/CUAD_v1.json"))
    if not json_candidates:
        from huggingface_hub import hf_hub_download
        downloaded = hf_hub_download(repo_id="TheAtticusProject/cuad", filename="CUAD_v1/CUAD_v1.json", repo_type="dataset")
        cuad_json_path = Path(downloaded)
    else:
        cuad_json_path = json_candidates[0]

    print(f"Loading CUAD v1 from: {cuad_json_path}")
    raw_data = json.loads(cuad_json_path.read_text(encoding="utf-8"))["data"]

    # 2. Filter out the 200 diagnostic contracts
    diagnostic_stems = {f.stem.lower() for f in _DIAGNOSTIC_DIR.glob("*.txt")}
    unseen_contracts = [
        entry for entry in raw_data
        if entry["title"].lower() not in diagnostic_stems
    ]
    print(f"Total CUAD contracts: {len(raw_data)}")
    print(f"Diagnostic (seen) contracts: {len(diagnostic_stems)}")
    print(f"Unseen contracts to evaluate: {len(unseen_contracts)}")

    settings = ConsistencySettings()
    flagged_docs = []
    finding_type_counts: dict[str, int] = {}

    for idx, entry in enumerate(unseen_contracts):
        title = entry["title"]
        context = entry["paragraphs"][0]["context"]
        pdoc = parse_raw_text(context)
        if pdoc is None:
            continue

        report = analyze(pdoc, settings)
        med_findings = [
            f for f in report.findings
            if f.severity in (Severity.MEDIUM, Severity.HIGH, Severity.CRITICAL)
        ]

        if med_findings:
            doc_record: dict[str, Any] = {
                "title": title,
                "findings": [],
            }
            for f in med_findings:
                finding_type_counts[f.type] = finding_type_counts.get(f.type, 0) + 1
                doc_record["findings"].append({
                    "type": f.type,
                    "severity": f.severity.value,
                    "clause_ref": f.clause_ref,
                    "evidence": f.evidence,
                    "explanation": f.explanation,
                })
            flagged_docs.append(doc_record)

        if (idx + 1) % 50 == 0 or idx + 1 == len(unseen_contracts):
            print(f"Processed {idx + 1}/{len(unseen_contracts)}... Flagged so far: {len(flagged_docs)}")

    total_analyzed = len(unseen_contracts)
    flagged_count = len(flagged_docs)
    flag_rate = (flagged_count / total_analyzed) * 100 if total_analyzed else 0.0

    print("\n" + "=" * 60)
    print("=== UNSEEN CUAD EVALUATION SUMMARY ===")
    print("=" * 60)
    print(f"Total Analyzed: {total_analyzed}")
    print(f"Flagged (MEDIUM+): {flagged_count} ({flag_rate:.2f}%)")
    print("Breakdown by finding type:")
    for ft, cnt in sorted(finding_type_counts.items(), key=lambda x: -x[1]):
        print(f"  {ft:30s} {cnt} occurrences")

    results_dir = Path(__file__).resolve().parent / "results"
    results_dir.mkdir(parents=True, exist_ok=True)

    json_out = results_dir / "cuad_unseen_scan.json"
    json_out.write_text(
        json.dumps(
            {
                "total_analyzed": total_analyzed,
                "flagged_count": flagged_count,
                "flag_rate": round(flag_rate, 2),
                "finding_type_counts": finding_type_counts,
                "flagged_docs": flagged_docs,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"\nWrote full JSON results to: {json_out}")


if __name__ == "__main__":
    main()
