"""CUAD full scan: run consistency analysis on ALL available CUAD contracts.

Uses the datagen text-segmentation approach (no PDF tampering needed) to
convert raw CUAD .txt files into ParsedDocument objects, then runs all
consistency detectors. Reports:
- Total CUAD contracts analyzed
- How many have MEDIUM+ findings
- Breakdown by finding type
- 10 random flagged examples with evidence
"""

from __future__ import annotations

import json
import random
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
from clauseguard.schemas.parsed import ClauseModel, PageModel, ParsedDocument

_CUAD_DIR = Path(__file__).resolve().parent.parent / "data" / "raw" / "cuad"


def parse_cuad_text(txt_path: Path) -> ParsedDocument | None:
    """Convert a CUAD .txt file into a ParsedDocument using the clause segmenter."""
    try:
        raw = txt_path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return None

    if not raw.strip():
        return None

    # Chunk into pages of ~3000 chars on line boundaries
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
    random.seed(42)
    settings = ConsistencySettings()

    txt_files = sorted(_CUAD_DIR.glob("*.txt"))
    print(f"Found {len(txt_files)} CUAD .txt files")

    total = 0
    flagged_docs: list[dict[str, Any]] = []
    finding_type_counts: dict[str, int] = {}
    errors = 0

    for txt_path in txt_files:
        doc = parse_cuad_text(txt_path)
        if doc is None:
            errors += 1
            continue

        total += 1
        try:
            report = analyze(doc, settings)
        except Exception as exc:
            errors += 1
            print(f"  ERROR on {txt_path.name}: {exc}")
            continue

        med_plus = [
            f for f in report.findings
            if f.severity in (Severity.MEDIUM, Severity.HIGH, Severity.CRITICAL)
        ]
        if med_plus:
            flagged_docs.append({
                "file": txt_path.name,
                "findings": [
                    {
                        "type": f.type,
                        "severity": f.severity.value,
                        "clause_ref": f.clause_ref,
                        "evidence": f.evidence[:200] if f.evidence else "",
                    }
                    for f in med_plus
                ],
            })
            for f in med_plus:
                finding_type_counts[f.type] = finding_type_counts.get(f.type, 0) + 1

    flagged_count = len(flagged_docs)
    flag_rate = flagged_count / total if total > 0 else 0.0

    print(f"\n=== CUAD Full Scan Results ===")
    print(f"Analyzed:  {total} documents  ({errors} errors/skipped)")
    print(f"Flagged (MEDIUM+): {flagged_count} / {total} = {flag_rate*100:.1f}%")
    print(f"Target: <= 5.0%  ->  {'MET' if flag_rate <= 0.05 else 'MISSED'}")
    print(f"\nBreakdown by finding type:")
    for ftype, count in sorted(finding_type_counts.items(), key=lambda x: -x[1]):
        print(f"  {ftype:<30} {count} occurrences")

    print(f"\n--- 10 random flagged examples ---")
    sample = random.sample(flagged_docs, min(10, len(flagged_docs)))
    for item in sample:
        print(f"\nFile: {item['file']}")
        for fnd in item["findings"][:3]:
            print(f"  [{fnd['severity'].upper():6}] {fnd['type']} @ clause {fnd['clause_ref']}")
            print(f"    Evidence: {fnd['evidence'][:120]}")

    # Write JSON output
    out = {
        "total_analyzed": total,
        "flagged_count": flagged_count,
        "flag_rate": round(flag_rate, 4),
        "errors": errors,
        "target_met": flag_rate <= 0.05,
        "finding_type_counts": finding_type_counts,
        "flagged_docs": flagged_docs,
    }
    out_path = Path(__file__).parent / "results" / "cuad_full_scan.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"\nWrote results to {out_path}")


if __name__ == "__main__":
    main()
