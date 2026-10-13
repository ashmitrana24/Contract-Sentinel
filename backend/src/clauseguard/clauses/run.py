"""Standalone CLI runner for Module 5: Clause Classification & Key-Term Extraction.

Usage:
  python -m clauseguard.clauses.run --input contract.txt
  python -m clauseguard.clauses.run --input contract.pdf --output report.json
  python -m clauseguard.clauses.run --text "1. Governing Law. This agreement is governed by the laws of Delaware."
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from clauseguard.clauses.attributes import extract_all_document_attributes
from clauseguard.clauses.model import classify_clause
from clauseguard.clauses.taxonomy import get_label_definition
from clauseguard.parsing.clauses import segment_clauses
from clauseguard.parsing.parse_document import parse_document
from clauseguard.schemas.parsed import PageModel


def analyze_document_text(
    text: str,
) -> dict[str, Any]:
    """Segment plain text into clauses, classify, and extract key terms."""
    # Chunk into dummy pages for heuristic segmenter
    pages = []
    lines = []
    chars = 0
    for line in text.splitlines(keepends=True):
        lines.append(line)
        chars += len(line)
        if chars >= 3000:
            chunk = "".join(lines)
            pages.append(
                PageModel(
                    page_no=len(pages) + 1,
                    width=612.0,
                    height=792.0,
                    text=chunk,
                    char_count=len(chunk),
                )
            )
            lines = []
            chars = 0
    if lines:
        chunk = "".join(lines)
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
    return analyze_clauses(clauses)


def analyze_pdf_bytes(pdf_bytes: bytes) -> dict[str, Any]:
    """Parse PDF bytes and analyze clauses."""
    parsed = parse_document(pdf_bytes)
    return analyze_clauses(parsed.clauses)


def analyze_clauses(clauses: list[Any]) -> dict[str, Any]:
    """Classify clauses and extract key terms."""
    clause_results = []
    type_counts: dict[str, dict[str, Any]] = {}
    clause_texts = []

    for c in clauses:
        clause_texts.append(c.text)
        preds = classify_clause(c.text, heading=c.heading)
        clause_results.append({
            "order_idx": c.order_idx,
            "clause_id": c.clause_id,
            "heading": c.heading,
            "kind": c.kind,
            "labels": preds,
        })

        for p in preds:
            lbl = p["label"]
            if lbl not in type_counts:
                defn = get_label_definition(lbl)
                type_counts[lbl] = {
                    "label": lbl,
                    "name": defn.name if defn else lbl,
                    "count": 0,
                    "max_score": 0.0,
                    "clause_ids": [],
                }
            type_counts[lbl]["count"] += 1
            type_counts[lbl]["max_score"] = max(type_counts[lbl]["max_score"], p["score"])
            type_counts[lbl]["clause_ids"].append(c.clause_id)

    attributes = extract_all_document_attributes(clause_texts)

    summary_types = sorted(type_counts.values(), key=lambda x: (-x["count"], x["label"]))

    return {
        "status": "ok",
        "total_clauses": len(clauses),
        "total_clause_types_found": len(summary_types),
        "clause_types": summary_types,
        "attributes": attributes.to_dict(),
        "clauses": clause_results,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="ClauseGuard Clause Classification CLI")
    parser.add_argument("--input", "-i", type=Path, help="Path to input PDF or text file")
    parser.add_argument("--text", "-t", type=str, help="Direct input contract text")
    parser.add_argument("--output", "-o", type=Path, help="Path to write JSON output")
    args = parser.parse_args()

    if args.text:
        report = analyze_document_text(args.text)
    elif args.input:
        if not args.input.exists():
            sys.stderr.write(f"Error: input file {args.input} does not exist\n")
            sys.exit(1)
        suffix = args.input.suffix.lower()
        if suffix == ".pdf":
            report = analyze_pdf_bytes(args.input.read_bytes())
        else:
            report = analyze_document_text(args.input.read_text(encoding="utf-8"))
    else:
        parser.print_help()
        sys.exit(1)

    json_str = json.dumps(report, indent=2)
    if args.output:
        args.output.write_text(json_str, encoding="utf-8")
        sys.stdout.write(f"Report written to {args.output}\n")
    else:
        sys.stdout.write(f"{json_str}\n")


if __name__ == "__main__":
    main()
