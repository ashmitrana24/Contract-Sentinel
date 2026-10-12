"""ContractNLI evaluation: run consistency analysis ONCE on the 123 held-out test NDAs from ContractNLI.

Corpus: ContractNLI (Koreeda & Manning, EMNLP 2021)
Hugging Face dataset: kiddothe2b/contract-nli (contract_nli_long.zip)
License: CC BY-NC-SA 4.0
Subset: test (123 non-disclosure agreements)
Evaluation: Zero tuning, single pass.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
import zipfile

import sys

# Ensure backend/src is on sys.path
_BACKEND_SRC = Path(__file__).resolve().parent.parent / "backend" / "src"
if str(_BACKEND_SRC) not in sys.path:
    sys.path.insert(0, str(_BACKEND_SRC))

from clauseguard.consistency.models import ConsistencySettings
from clauseguard.consistency.run import analyze
from clauseguard.parsing.clauses import segment_clauses
from clauseguard.schemas.findings import Severity
from clauseguard.schemas.parsed import PageModel, ParsedDocument


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
    # 1. Download / locate contract_nli_long.zip
    from huggingface_hub import hf_hub_download
    zip_path = hf_hub_download(
        repo_id="kiddothe2b/contract-nli",
        filename="contract_nli_long.zip",
        repo_type="dataset",
    )
    print(f"Loading ContractNLI from: {zip_path}")

    # 2. Extract test split NDAs
    z = zipfile.ZipFile(zip_path)
    with z.open("contract_nli_long.jsonl") as f:
        all_entries = [json.loads(line) for line in f]

    test_entries = [e for e in all_entries if e.get("subset") == "test"]
    print(f"Total entries in ContractNLI: {len(all_entries)}")
    print(f"Test split NDAs to evaluate: {len(test_entries)}")

    settings = ConsistencySettings()
    flagged_docs = []
    finding_type_counts: dict[str, int] = {}

    for idx, entry in enumerate(test_entries):
        text = entry["premise"]
        # Extract title from first non-empty lines
        non_empty = [ln.strip() for ln in text.splitlines() if ln.strip()]
        doc_title = non_empty[0][:80] if non_empty else f"ContractNLI_Test_NDA_{idx + 1}"
        doc_id = f"ContractNLI_Test_{idx + 1:03d} ({doc_title})"

        pdoc = parse_raw_text(text)
        if pdoc is None:
            continue

        report = analyze(pdoc, settings)
        med_findings = [
            f for f in report.findings
            if f.severity in (Severity.MEDIUM, Severity.HIGH, Severity.CRITICAL)
        ]

        if med_findings:
            doc_record: dict[str, Any] = {
                "doc_id": doc_id,
                "index": idx + 1,
                "first_line": doc_title,
                "text_length": len(text),
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

        if (idx + 1) % 25 == 0 or idx + 1 == len(test_entries):
            print(f"Processed {idx + 1}/{len(test_entries)}... Flagged so far: {len(flagged_docs)}")

    total_analyzed = len(test_entries)
    flagged_count = len(flagged_docs)
    flag_rate = (flagged_count / total_analyzed) * 100 if total_analyzed else 0.0

    print("\n" + "=" * 60)
    print("=== CONTRACT-NLI TEST NDA EVALUATION SUMMARY ===")
    print("=" * 60)
    print(f"Total Analyzed: {total_analyzed}")
    print(f"Flagged (MEDIUM+): {flagged_count} ({flag_rate:.2f}%)")
    print("Breakdown by finding type:")
    for ftype, cnt in sorted(finding_type_counts.items(), key=lambda x: -x[1]):
        print(f"  {ftype:<30} {cnt} occurrences")

    out_file = Path(__file__).resolve().parent / "results" / "contract_nli_scan.json"
    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_text(
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
    print(f"\nWrote full JSON results to: {out_file}")


if __name__ == "__main__":
    main()
