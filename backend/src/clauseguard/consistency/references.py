"""Cross-reference extraction and dangling reference detector.

Detects:
1. dangling_reference (MEDIUM):
   A cross-reference (e.g., "Clause 4.2", "Section 5", "Article III", "paragraph 3",
   "Clauses 4.1 and 4.2", ranges like "Sections 4.1 to 4.3", sub-item "Clause 4.2(a)")
   where the referenced target does not exist in the contract clauses and does not
   appear at the start of any line in the document text.

Ignores:
- External references: followed by "of the ... Act/Code/Regulations/Statute/Agreement dated"
  or preceded by "under". Example: "Section 138 of the Negotiable Instruments Act".
- Self-references ("this Clause", "this Section").
- Skips if document is unsegmented or has fewer than 5 parsed clauses.
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


# ---------------------------------------------------------------------------
# Cross-reference regexes
# ---------------------------------------------------------------------------

_XREF_PAT = re.compile(
    r"\b(?P<prefix>Clauses?|Sections?|Articles?|paragraphs?|paras?)\s+"
    r"(?P<target>(?:\d+(?:\.\d+)*|[IVXLCDM]+|[A-Z])(?:\([A-Za-z0-9]+\))*)\b"
    r"(?:\s+(?P<conj>and|to|through|-)\s+(?:(?:Clauses?|Sections?|Articles?|paragraphs?|paras?)\s+)?(?P<target2>(?:\d+(?:\.\d+)*|[IVXLCDM]+|[A-Z])(?:\([A-Za-z0-9]+\))*)\b)?",
    re.IGNORECASE,
)

# Common words that must never be treated as dangling targets
_DISALLOWED_TARGETS = {
    "shall", "may", "will", "is", "are", "be", "to", "and", "or", "in", "of", "for",
    "with", "as", "by", "on", "at", "from", "into", "through", "during", "above",
    "below", "hereof", "herein", "hereunder", "set", "forth", "stated", "contained",
    "specified", "referred", "described", "provided", "clause", "section", "article",
    "paragraph", "s",
}

# External statute/act/agreement indicator following the reference
_EXTERNAL_FOLLOWING_PAT = re.compile(
    r"^\s*(?:-\d+[A-Za-z0-9]*\s*)*(?:\([A-Za-z0-9]+\)\s*)*(?:(?:of|under)\s+(?:the\s+|this\s+|that\s+|any\s+)?[A-Za-z0-9\s,.&'\(\)\-]{1,80}?(?:Act|Code|Law|Regulations?|Rules?|Statute|Ordinance|Bankruptcy|Order|U\.?S\.?C\.?|C\.?F\.?R\.?|Agreement\s+dated|Contract\s+dated)|\(\s*(?:or\s+similar\s+)?[A-Za-z0-9\s,.&'\-]{1,60}?(?:Law|Act|Code|Statute)\b)",
    re.IGNORECASE,
)

# External agreement indicator: "of the <Name> Agreement" (where <Name> is not just "this" or empty)
_EXTERNAL_AGREEMENT_PAT = re.compile(
    r"^\s*(?:\([A-Za-z0-9]+\)\s*)*of\s+(?:the|any|such)\s+([A-Za-z0-9\s,]{2,50}?)\s+(?:Agreement|Contract|Plan|Policy)\b",
    re.IGNORECASE,
)

# External indicator preceding the reference (e.g. "under Section 138", "Pub. L. No. 111-5, Section 1553", "47 U.S.C. §222 (as amended, 'Section 222')")
_EXTERNAL_PRECEDING_PAT = re.compile(
    r"(?:\b(?:under|pursuant\s+to|in\s+terms\s+of|as\s+per|Pub\.?\s*L\.?(?:\s*No\.?)?[\s\d\-]+,|Regulation,)\s*$|\b(?:U\.?S\.?C\.?|C\.?F\.?R\.?)\b[\s\S]{0,55}[\"“']?$)",
    re.IGNORECASE,
)

# Self-reference patterns
_SELF_REF_PAT = re.compile(
    r"\b(?:this|such|that)\s*$",
    re.IGNORECASE,
)


def _clean_subitem_target(target: str) -> str:
    """Strip trailing parenthetical sub-item designations (e.g., '4.2(a)' -> '4.2')."""
    return re.sub(r"\([A-Za-z0-9]+\)$", "", target.strip())


def _expand_range(start_target: str, end_target: str) -> list[str]:
    """Expand a range of clause numbers if numeric/dotted."""
    # Integer range: 4 to 6 -> [4, 5, 6]
    if start_target.isdigit() and end_target.isdigit():
        s, e = int(start_target), int(end_target)
        if 0 < s <= e and (e - s) <= 20:
            return [str(i) for i in range(s, e + 1)]
    # Decimal range: 4.1 to 4.3 -> [4.1, 4.2, 4.3]
    if "." in start_target and "." in end_target:
        p1 = start_target.split(".")
        p2 = end_target.split(".")
        if len(p1) == 2 and len(p2) == 2 and p1[0] == p2[0]:
            if p1[1].isdigit() and p2[1].isdigit():
                s, e = int(p1[1]), int(p2[1])
                if 0 < s <= e and (e - s) <= 20:
                    return [f"{p1[0]}.{i}" for i in range(s, e + 1)]
    return [start_target, end_target]


def detect_cross_references(
    doc: ParsedDocument,
    index: TextIndex,
    settings: ConsistencySettings,
) -> tuple[list[Finding], dict[str, Any]]:
    """Detect cross-references to non-existent clauses in the contract."""
    findings: list[Finding] = []
    stats: dict[str, Any] = {
        "references_found": 0,
        "external_ignored": 0,
        "dangling_detected": 0,
        "dangling_targets": [],
        "skipped_reason": None,
    }

    # Skip if unsegmented or fewer than min_clauses
    if index.is_unsegmented or len(doc.clauses) < settings.min_clauses_for_structural_checks:
        stats["skipped_reason"] = "unsegmented_or_too_few_clauses"
        return findings, stats

    # Collect existing clause identifiers
    existing_clause_ids: set[str] = set()
    for clause in doc.clauses:
        cid = str(clause.clause_id).strip()
        existing_clause_ids.add(cid)
        # Also add without leading zeros or stripped
        existing_clause_ids.add(cid.lower())
        # Add heading if heading starts with number
        if clause.heading:
            m_head = re.match(r"^(\d+(?:\.\d+)*)", clause.heading.strip())
            if m_head:
                existing_clause_ids.add(m_head.group(1))

    # Pre-extract full document text for page-text safeguard
    full_text = "\n".join(p.text for p in doc.pages) if doc.pages else ""

    # Group dangling references by target: target -> list of (segment, match_snippet)
    dangling_by_target: dict[str, list[tuple[Any, str]]] = {}

    for segment in index.segments:
        seg_text = segment.text
        if not seg_text.strip():
            continue

        for m in _XREF_PAT.finditer(seg_text):
            stats["references_found"] += 1
            start_idx = m.start()
            end_idx = m.end()

            preceding_context = seg_text[max(0, start_idx - 50) : start_idx]

            # 0. Check if self-reference ("this Clause", "such Section")
            if _SELF_REF_PAT.search(preceding_context):
                continue

            # 1. Check if preceded by external indicator ("under Section ...")
            if _EXTERNAL_PRECEDING_PAT.search(preceding_context):
                stats["external_ignored"] += 1
                continue

            # 2. Check if followed by external indicator ("... of the Companies Act")
            following_context = seg_text[end_idx : min(len(seg_text), end_idx + 80)]
            if _EXTERNAL_FOLLOWING_PAT.search(following_context):
                stats["external_ignored"] += 1
                continue

            m_ext_agr = _EXTERNAL_AGREEMENT_PAT.search(following_context)
            if m_ext_agr:
                inner_name = m_ext_agr.group(1).strip().lower()
                if inner_name not in {"this", "the", "said"}:
                    stats["external_ignored"] += 1
                    continue

            raw_target1 = m.group("target")
            raw_target2 = m.group("target2")
            conj = m.group("conj")

            targets_to_check: list[str] = []
            if raw_target2 and conj:
                conj_lower = conj.lower()
                if conj_lower in {"to", "through", "-"}:
                    targets_to_check.extend(_expand_range(raw_target1, raw_target2))
                else:
                    targets_to_check.extend([raw_target1, raw_target2])
            else:
                targets_to_check.append(raw_target1)

            snippet = seg_text[max(0, start_idx - 30) : min(len(seg_text), end_idx + 30)]

            for raw_t in targets_to_check:
                clean_t = _clean_subitem_target(raw_t)

                if clean_t.lower() in _DISALLOWED_TARGETS:
                    continue


                # Skip self-reference (referring to the same clause)
                if segment.clause_ref and clean_t == segment.clause_ref:
                    continue

                # Check if target exists directly in parsed clauses
                if raw_t in existing_clause_ids or clean_t in existing_clause_ids:
                    continue

                # Check safeguard: is target found in page text as a heading or paragraph marker?
                # e.g., "\n4.2 ", ". 4.2 ", "and 4.5.", "\nClause 4.2", or "4.2 Term"
                escaped_t = re.escape(clean_t)
                heading_pat = (
                    rf"(?:^|\n|[\.\;\)\]\"\'\u201d]\s+)\s*(?:and\s+|or\s+)?(?:Clause\s+|Section\s+|Article\s+|Paragraph\s+)?{escaped_t}\.?\b(?!\s*(?:and|or|to|through|of\s+the|\-))"
                )
                if re.search(heading_pat, full_text, re.IGNORECASE):
                    continue

                # Also check capitalized section heading pattern for dotted numbers: e.g. "8.1. Equipment", "9.1 Confidentiality"
                if "." in clean_t:
                    m_head = re.search(rf"\b{escaped_t}\.?\s+[A-Z][a-z]+", full_text)
                    if m_head:
                        pos = m_head.start()
                        prec = full_text[max(0, pos - 15) : pos]
                        if not re.search(r"(?:Section|Clause|Article|Paragraph)\s*$", prec, re.I):
                            continue

                # Check line-start section heading in page text: e.g. "\n10. Confidentiality", "\nARTICLE 10 Confidentiality"
                if re.search(
                    rf"(?:^|\n)\s*(?:(?:Article|Section|Clause)\s+)?{escaped_t}\.?\s+[A-Z]",
                    full_text,
                ):
                    continue
                # Also check all-caps Article headings: e.g. "ARTICLE 10 CONFIDENTIALITY", "ARTICLE VIII INDEMNIFICATION"
                if re.search(rf"\b(?:ARTICLE|SECTION|CLAUSE)\s+{escaped_t}\s+[A-Z]{{3,}}\b", full_text):
                    continue
                if re.match(r"^[IVXLCDM]+$", clean_t):
                    if len(re.findall(rf"\b(?:Article|Section|Clause)\s+{escaped_t}\b", full_text, re.I)) >= 2:
                        continue

                # Target is dangling!
                if clean_t not in dangling_by_target:
                    dangling_by_target[clean_t] = []
                dangling_by_target[clean_t].append((segment, snippet))

    # Construct findings: one finding per missing target
    dangling_target_list = sorted(dangling_by_target.keys())
    stats["dangling_targets"] = dangling_target_list
    stats["dangling_detected"] = len(dangling_target_list)

    for target, occurrences in dangling_by_target.items():
        ref_count = len(occurrences)
        first_segment, first_snippet = occurrences[0]
        referencing_clauses = sorted(
            {seg.clause_ref for seg, _ in occurrences if seg.clause_ref}
        )

        evidence_str = f"Target '{target}' referenced in: {first_snippet}"
        if ref_count > 1:
            evidence_str += f" (and {ref_count - 1} other occurrence(s))"
        if len(evidence_str) > MAX_EVIDENCE_CHARS:
            evidence_str = evidence_str[:MAX_EVIDENCE_CHARS]

        clause_info = f"clause(s) {', '.join(referencing_clauses)}" if referencing_clauses else "the document"
        explanation = (
            f"Cross-reference to '{target}' in {clause_info} cannot be resolved: "
            f"no clause with identifier '{target}' exists in the contract"
        )
        if ref_count >= 2:
            explanation += f" (referenced {ref_count} times)."
        else:
            explanation += "."

        findings.append(
            Finding(
                module=CONSISTENCY_MODULE,
                type="dangling_reference",
                severity=Severity.MEDIUM,
                page=first_segment.page,
                clause_ref=first_segment.clause_ref,
                evidence=evidence_str,
                explanation=explanation,
                details={
                    "rule_id": "XRF001",
                    "missing_target": target,
                    "reference_count": ref_count,
                    "referencing_clauses": referencing_clauses,
                },
            )
        )

    return findings, stats
