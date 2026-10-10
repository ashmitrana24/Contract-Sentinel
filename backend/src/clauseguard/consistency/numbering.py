"""Clause numbering gap and duplicate clause number detector.

Detects:
1. numbering_gap (LOW on its own, upgraded to HIGH if a dangling reference points to it):
   Missing number in the middle of a sequence of at least 5 top-level numeric clauses (1, 2, 3...).
   Ignored if a neighbouring heading mentions "reserved", "intentionally omitted",
   "deleted", or "not used".
2. duplicate_clause_number (MEDIUM):
   Two or more clauses share the exact same top-level clause number.

Skips if document is unsegmented or has fewer than 5 parsed clauses.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

from clauseguard.consistency.models import (
    CONSISTENCY_MODULE,
    MAX_EVIDENCE_CHARS,
    ConsistencySettings,
)
from clauseguard.schemas.findings import Finding, Severity

if TYPE_CHECKING:
    from clauseguard.consistency.text_index import TextIndex
    from clauseguard.schemas.parsed import ParsedDocument


_RESERVED_HEADING_PAT = re.compile(
    r"\b(?:reserved|intentionally\s+omitted|omitted|deleted|not\s+used)\b",
    re.IGNORECASE,
)


def detect_clause_numbering(
    doc: ParsedDocument,
    index: TextIndex,
    settings: ConsistencySettings,
    dangling_targets: list[str] | set[str] | None = None,
) -> tuple[list[Finding], dict[str, Any]]:
    """Check for clause numbering gaps and duplicate clause numbers."""
    findings: list[Finding] = []
    stats: dict[str, Any] = {
        "top_level_clauses_found": 0,
        "duplicates_detected": 0,
        "gaps_detected": 0,
        "gaps_correlated_with_xref": 0,
        "skipped_reason": None,
    }

    # Skip if unsegmented or fewer than min_clauses
    if index.is_unsegmented or len(doc.clauses) < settings.min_clauses_for_structural_checks:
        stats["skipped_reason"] = "unsegmented_or_too_few_clauses"
        return findings, stats

    # Collect top-level numeric clause numbers and their clauses
    # We look for clauses with clause_id being an integer string (e.g. "1", "2")
    # or starting with an integer (e.g. "1.0")
    top_level_clauses: dict[int, list[Any]] = {}

    for clause in doc.clauses:
        cid_str = str(clause.clause_id).strip()
        if cid_str.isdigit():
            num = int(cid_str)
        else:
            continue

        # Ignore continuation segments, mid-sentence wrapped lines, and punctuation-prefixed text
        if clause.heading:
            h_strip = clause.heading.strip()
            if not h_strip or not h_strip[0].isalnum() or h_strip[0].islower():
                continue

        # Ignore extreme outlier numbers (e.g. statutory sections 202, 719, etc.)
        if num > 60 and num > len(doc.clauses) * 2:
            continue

        if num not in top_level_clauses:
            top_level_clauses[num] = []
        top_level_clauses[num].append(clause)

    stats["top_level_clauses_found"] = len(top_level_clauses)
    if len(top_level_clauses) < settings.min_clauses_for_structural_checks:
        stats["skipped_reason"] = "fewer_than_5_top_level_clauses"
        return findings, stats

    dangling_set = {str(t).strip() for t in (dangling_targets or [])}

    # -----------------------------------------------------------------------
    # 1. Duplicate top-level clause numbers (MEDIUM)
    # -----------------------------------------------------------------------
    duplicate_nums = [n for n, cls in sorted(top_level_clauses.items()) if len(cls) >= 2]
    # If 2 or more distinct clause numbers repeat, this is a multi-part or multi-schedule
    # document (where each schedule, annex, or exhibit restarts numbering from 1), not accidental duplicates.
    if len(duplicate_nums) < 2:
        for num in duplicate_nums:
            clauses = top_level_clauses[num]
            stats["duplicates_detected"] += 1
            headings_info = [
                f"'{c.heading or 'Untitled'}' (page {c.page_start})" for c in clauses
            ]
            evidence_str = f"Clause {num} appears {len(clauses)} times: {', '.join(headings_info)}"
            if len(evidence_str) > MAX_EVIDENCE_CHARS:
                evidence_str = evidence_str[:MAX_EVIDENCE_CHARS]

            findings.append(
                Finding(
                    module=CONSISTENCY_MODULE,
                    type="duplicate_clause_number",
                    severity=Severity.MEDIUM,
                    page=clauses[1].page_start,
                    clause_ref=str(num),
                    evidence=evidence_str,
                    explanation=(
                        f"Duplicate clause number: clause {num} is used multiple times "
                        f"in the document ({len(clauses)} occurrences)."
                    ),
                    details={
                        "rule_id": "NUM001",
                        "clause_number": num,
                        "occurrence_count": len(clauses),
                        "headings": [c.heading for c in clauses],
                    },
                )
            )
    else:
        stats["skipped_reason"] = "multi_schedule_or_multipart_numbering"

    # -----------------------------------------------------------------------
    # 2. Numbering gaps (LOW, or HIGH if correlated with dangling xref)
    # -----------------------------------------------------------------------
    sorted_nums = sorted(top_level_clauses.keys())
    min_num, max_num = sorted_nums[0], sorted_nums[-1]

    # If the numbering is sparse (< 50% density across span), it's not sequential numbering
    if len(top_level_clauses) < (max_num - min_num + 1) * 0.5 and (max_num - min_num) > 20:
        return findings, stats

    # Check for reserved or intentionally omitted markers across headings or texts
    # Map each existing clause number to its heading and text
    clause_contents: dict[int, str] = {}
    for num, clauses in top_level_clauses.items():
        clause_contents[num] = " ".join(
            f"{c.heading or ''} {c.text or ''}" for c in clauses
        )

    for expected_num in range(min_num, max_num + 1):
        if expected_num not in top_level_clauses:
            # Check neighbouring clauses for "reserved", "omitted", etc.
            neighbour_content = ""
            if expected_num - 1 in clause_contents:
                neighbour_content += f" {clause_contents[expected_num - 1]}"
            if expected_num + 1 in clause_contents:
                neighbour_content += f" {clause_contents[expected_num + 1]}"

            if _RESERVED_HEADING_PAT.search(neighbour_content):
                # Neighbour explicitly states reserved/omitted
                continue

            # Also check page text around the gap in case the segmenter missed it
            prev_clause = top_level_clauses.get(expected_num - 1)
            ref_page = prev_clause[0].page_end if prev_clause else 1

            stats["gaps_detected"] += 1
            has_dangling_xref = str(expected_num) in dangling_set

            if has_dangling_xref:
                stats["gaps_correlated_with_xref"] += 1
                severity = Severity.HIGH
                explanation = (
                    f"Clause numbering gap: clause {expected_num} is missing between clause "
                    f"{expected_num - 1} and clause {expected_num + 1}, and a cross-reference "
                    f"specifically points to missing clause {expected_num}."
                )
            else:
                severity = Severity.LOW
                explanation = (
                    f"Clause numbering gap: clause {expected_num} is missing in the sequence "
                    f"from {min_num} to {max_num}."
                )

            evidence_str = (
                f"Missing clause {expected_num} between clause {expected_num - 1} and clause {expected_num + 1}"
            )
            if has_dangling_xref:
                evidence_str += f" (cross-referenced by dangling reference to '{expected_num}')"
            if len(evidence_str) > MAX_EVIDENCE_CHARS:
                evidence_str = evidence_str[:MAX_EVIDENCE_CHARS]

            findings.append(
                Finding(
                    module=CONSISTENCY_MODULE,
                    type="numbering_gap",
                    severity=severity,
                    page=ref_page,
                    clause_ref=str(expected_num),
                    evidence=evidence_str,
                    explanation=explanation,
                    details={
                        "rule_id": "NUM002",
                        "missing_clause": expected_num,
                        "previous_clause": expected_num - 1,
                        "next_clause": expected_num + 1,
                        "dangling_xref_correlated": has_dangling_xref,
                    },
                )
            )

    return findings, stats
