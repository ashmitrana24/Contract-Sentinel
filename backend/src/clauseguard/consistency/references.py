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
    r"(?P<target>(?:\d+(?:\.\d+)*[A-Za-z]?|[IVXLCDM]+|[A-Z])(?:\([A-Za-z0-9]+\))*)(?!\w)"
    r"(?:\s+(?P<conj>and|to|through|-)\s+(?:(?:Clauses?|Sections?|Articles?|paragraphs?|paras?)\s+)?(?P<target2>(?:\d+(?:\.\d+)*[A-Za-z]?|[IVXLCDM]+|[A-Z])(?:\([A-Za-z0-9]+\))*)(?!\w))?",
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

# Roman-to-Arabic bidirectional mapping
_ROMAN_MAP = {
    "1": "I", "2": "II", "3": "III", "4": "IV", "5": "V",
    "6": "VI", "7": "VII", "8": "VIII", "9": "IX", "10": "X",
    "11": "XI", "12": "XII", "13": "XIII", "14": "XIV", "15": "XV",
    "16": "XVI", "17": "XVII", "18": "XVIII", "19": "XIX", "20": "XX",
}
_ARABIC_MAP = {v: k for k, v in _ROMAN_MAP.items()}

# External statute/act/agreement indicator following the reference.
# Examples: "of the Companies Act", "(n) or any similar provisions",
#           "of the Code of Federal Regulations", "of the Bankruptcy Code",
#           "of the Indenture", "of the General Terms", "of Regulation AB"
_EXTERNAL_FOLLOWING_PAT = re.compile(
    r"^\s*"
    r"(?:-\d+[A-Za-z0-9]*\s*)*"
    r"(?:\([A-Za-z0-9]+\)\s*)*"
    r"(?:(?:,\s*|\s+(?:and|or)\s+)(?:Sections?\s+|Articles?\s+|Clauses?\s+)?\d+[A-Za-z0-9.()\-]*\s*)*"
    r"(?:(?:and|or)\s+(?:the\s+)?following,?\s*)?"
    r"(?:,\s*respectively,?\s*)?"
    r"(?:"
    r"(?:of|under)\s+(?:the\s+|this\s+|that\s+|any\s+)?[A-Za-z0-9\s,.&'\(\)\-]{0,120}?"
    r"(?:Act|Code|Law|Regulations?|Rules?|Statutes?|Ordinance|Order|U\.?S\.?C\.?|C\.?F\.?R\.?|FD&?C|FDCA|PHSA|FAR|DFARS|U\.?C\.?C\.?|Indenture|SPA|Supplement|Annex|Appendix|Schedule|Exhibit|General\s+Terms|Terms\s+and\s+Conditions|Agreement\s+dated|Contract\s+dated)"
    r"|"
    r"\(\s*(?:or\s+similar\s+)?[A-Za-z0-9\s,.&'\-]{0,60}?(?:Law|Act|Code|Statute)\b"
    r"|"
    r"or\s+any\s+similar\s+provisions?"
    r"|"
    r"(?:through|to|-)\s+[0-9A-Za-z.()\-]+\s+of\s+the\s+[A-Za-z0-9\s,.&'\(\)\-]{2,60}?\s+(?:Agreement|Contract|License|Lease|Indenture)\b"
    r")",
    re.IGNORECASE,
)

# External agreement indicator: "of the <Name> Agreement" (where <Name> is not just "this" or empty)
_EXTERNAL_AGREEMENT_PAT = re.compile(
    r"^\s*(?:\([A-Za-z0-9]+\)\s*)*(?:(?:through|to|-)\s+[0-9A-Za-z.()\-]+\s+)?of\s+(?:the|any|such)\s+([A-Za-z0-9\s,.&'\(\)\-]{0,60}?)\s*(?:Agreement|Contract|Plan|Policy|Indenture|SPA|APA|ISDA(?:\s+Form)?|SFA|SOW|Form|Charter|Code|Act|Supplement|Lease|License|Instrument|GMA|MSA|NDA|SLA|DPA)\b",
    re.IGNORECASE,
)

# External indicator preceding the reference.
# Catches: "under Section 138", "Pub. L. No. 111-5, Section 1553",
#          "47 U.S.C. §222", "Code of Federal Regulations, Section 211.180",
#          "United States Bankruptcy Code section 365", "C.F.R. Section ...",
#          "California Civil Code section 1654", "Florida Statutes Section 817.416"
_EXTERNAL_PRECEDING_PAT = re.compile(
    r"(?:"
    r"\b(?:under|pursuant\s+to|in\s+terms\s+of|as\s+per"
    r"|Pub\.?\s*L\.?(?:\s*No\.?)?[\s\d\-]+,"
    r"|Regulation,"
    r"|Code\s+of\s+Federal\s+Regulations[,\s]*"
    r"|(?:United\s+States\s+)?Bankruptcy\s+Code[,\s]*"
    r"|Internal\s+Revenue\s+Code[,\s]*"
    r"|[A-Za-z\s]+Civil\s+Code(?:\s+in\s+its)?\s*"
    r"|[A-Za-z\s]+Statutes\s*"
    r"|mutatis\s+mutandis,?\s*(?:by\s+)?"
    r"|located\s+at|property\s+at|land\s+at|well\s+at"
    r"|(?:Schedule|Exhibit|Annex|Appendix)\s+[A-Za-z0-9]+[,\s]+"
    r")\s*$"
    r"|\b(?:in|under|of)\s+the\s+[A-Za-z0-9\s,.&'\-]{1,50}?\s+(?:Agreement|Contract|APA|ISDA)\s*\(including\s*$"
    r"|\b(?:U\.?S\.?C\.?|C\.?F\.?R\.?|I\.?R\.?C\.?|FDCA|PHSA)\b[\s\S]{0,55}$"
    r")",
    re.IGNORECASE,
)

# Self-reference patterns
_SELF_REF_PAT = re.compile(
    r"\b(?:this|such|that)\s*$",
    re.IGNORECASE,
)

_AMENDMENT_CONTEXT_PAT = re.compile(
    r"\b(?:is\s+hereby\s+amended|are\s+hereby\s+amended|is\s+amended|are\s+amended|"
    r"amends|amendment\s+of\s+section|as\s+a\s+new\s+Section|added\s+to\s+Section|"
    r"inserted\s+into\s+Section|deleted\s+in\s+its\s+entirety|deleting\s+in\s+its\s+entirety|"
    r"Existing\s+Agreement|to\s+the\s+end\s+of\s+Section|limitation\s+such\s+references|"
    r"Right\s+of\s+First\s+Refusal)\b",
    re.IGNORECASE,
)


def _clean_subitem_target(target: str) -> str:
    """Strip all trailing parenthetical sub-item designations (e.g., '4.2(a)' -> '4.2', '10.1(a)(i)' -> '10.1')."""
    return re.sub(r"(?:\([A-Za-z0-9]+\))+$", "", target.strip())


def _candidate_ancestors(target: str) -> list[str]:
    """Return candidate parent clause IDs stripping only parenthetical sub-item designations.

    Strip only parenthetical sub-item suffixes such as (a) or (i) when resolving;
    a dotted number must match exactly when the document's segmentation is reliable.
    e.g. '10.1(a)(i)' -> ['10.1']
         '4.3(a)'     -> ['4.3']
         '4(a)'       -> ['4']
         '4.9'        -> []
    """
    cleaned = re.sub(r"(?:\([A-Za-z0-9]+\))+$", "", target.strip())
    ancestors: list[str] = []
    if cleaned and cleaned != target:
        ancestors.append(cleaned)
    return ancestors


def _is_statute_subitem_chain(raw_target: str, following: str) -> bool:
    """Detect statute-style sub-paragraph chains like '351(l)(3)(A)' or '351(l) (3)(A)'."""
    combined = (raw_target + " " + following[:35]).strip()
    if re.search(r"^\d+[A-Za-z]?\s*(?:\([A-Za-z0-9]+\)\s*){2,}", combined):
        return True
    if len(re.findall(r"\([A-Za-z0-9]+\)", combined[:30])) >= 2:
        return True
    return False


_STATUTORY_CONTEXT_PAT = re.compile(
    r"\b(?:"
    r"Code|Act|Rule|Securities|Exchange|Internal\s+Revenue|Treasury|"
    r"Statutes?|Regulations?|Regs?|U\.?S\.?C\.?|C\.?F\.?R\.?|I\.?R\.?C\.?|"
    r"ERISA|FDCA|PHSA|FAR|DFARS?|GBL|BIA|CCAA|Bankruptcy|Tax"
    r")\b",
    re.IGNORECASE,
)


def _is_statutory_citation(raw_target: str, clean_target: str, context_snippet: str) -> bool:
    """Return True if target looks like a statutory citation and context has statutory keywords.

    Catches:
    - Digits followed by a letter: '409A', '280G', '162(m)', '83(b)'
    - Number followed by parenthetical letter: '12(g)', '16(b)', '13(d)', '14(a)', '365(n)'
    When surrounding context contains statutory indicators like Code, Act, Rule, Securities,
    Exchange, Internal Revenue, etc.
    """
    is_code_form = bool(re.search(r"^\d+[A-Za-z]$", clean_target)) or bool(re.search(r"^\d+[A-Za-z]", raw_target))
    is_paren_letter = bool(re.search(r"^\d+\([A-Za-z]\)", raw_target))
    if not (is_code_form or is_paren_letter):
        return False
    return bool(_STATUTORY_CONTEXT_PAT.search(context_snippet))


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


def _is_uncertain_reference(
    target: str,
    occurrences: list[tuple[Any, str]],
    existing_clause_ids: set[str],
    doc_clauses: list[Any],
    full_text: str,
    is_amending_doc: bool = False,
) -> bool:
    """Determine if a missing cross-reference is uncertain and should be reported as LOW."""
    ref_count = len(occurrences)
    _first_seg, first_snippet = occurrences[0]

    # 1. Parent clause exists: e.g. target is '4.1.1' and '4' or 'IV' exists;
    # or target is '17.2.2' and '17' or '17.2' exists.
    parts = target.split(".")
    if len(parts) > 1:
        parent_1 = parts[0]
        parent_2 = ".".join(parts[:-1])
        if (
            parent_1 in existing_clause_ids
            or parent_1.lower() in existing_clause_ids
            or _ROMAN_MAP.get(parent_1, "").lower() in existing_clause_ids
            or _ROMAN_MAP.get(parent_1, "") in existing_clause_ids
            or parent_2 in existing_clause_ids
            or parent_2.lower() in existing_clause_ids
        ):
            return True

    # 2. Context has "below", "above", "herein", "hereof", "hereto" indicating internal/exhibit pointer
    if re.search(r"\b(?:below|above|herein|hereof|hereto)\b", first_snippet, re.IGNORECASE):
        return True

    # 3. Document has redactions [***] or omitted clauses where single-ref target may reside
    if "[***]" in full_text or "omitted" in full_text.lower():
        if ref_count == 1:
            return True

    # 4. Target is in an enumerated list of 4+ sections (typical survival clause / definition list)
    if re.search(r"(?:,\s*(?:and\s+)?(?:\d+|[IVXLCDM]+)){3,}", first_snippet):
        if ref_count == 1:
            return True

    # 5. Target style mismatch (e.g. Arabic dotted number in pure Roman document)
    has_roman = any(
        re.match(r"^[IVXLCDM]+$", str(c.clause_id).strip(), re.IGNORECASE)
        for c in doc_clauses
        if str(c.clause_id).strip() != "0"
    )
    has_dotted = any("." in str(c.clause_id) for c in doc_clauses)
    if has_roman and not has_dotted and "." in target:
        return True

    return False


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
        "uncertain_moved_to_low": 0,
        "skipped_reason": None,
    }

    # Skip if unsegmented or fewer than min_clauses
    if index.is_unsegmented or len(doc.clauses) < settings.min_clauses_for_structural_checks:
        stats["skipped_reason"] = "unsegmented_or_too_few_clauses"
        return findings, stats

    # Pre-extract full document text
    full_text = "\n".join(p.text for p in doc.pages) if doc.pages else ""

    # Check if document is an amending agreement
    is_amending_doc = bool(
        re.search(
            r"\b(?:amendment(?:\s+no\.?\s*\d+)?|amend(?:s|ed|ing)?\s+agreement|addendum|supplement\s+to)\b",
            full_text[:3000],
            re.IGNORECASE,
        )
    )

    # Collect existing clause identifiers
    existing_clause_ids: set[str] = set()
    for clause in doc.clauses:
        cid = str(clause.clause_id).strip()
        existing_clause_ids.add(cid)
        existing_clause_ids.add(cid.lower())
        if "." in cid:
            parent_part = cid.split(".")[0]
            existing_clause_ids.add(parent_part)
            existing_clause_ids.add(parent_part.lower())
        # Add heading if heading starts with number (e.g. "1. Definitions" or "Clause 12 - Invoicing")
        if clause.heading:
            m_head = re.match(r"^(?:(?:Clause|Section|Article)\s+)?(\d+(?:\.\d+)*)", clause.heading.strip(), re.IGNORECASE)
            if m_head:
                existing_clause_ids.add(m_head.group(1))

    # Bidirectional Roman <-> Arabic numeral mapping
    for cid in list(existing_clause_ids):
        cid_u = cid.upper()
        if cid_u in _ARABIC_MAP:
            existing_clause_ids.add(_ARABIC_MAP[cid_u])
        if cid in _ROMAN_MAP:
            existing_clause_ids.add(_ROMAN_MAP[cid])
            existing_clause_ids.add(_ROMAN_MAP[cid].lower())

    # Detect shorthand statute section definitions: e.g. (as amended, "Section 222") or "Section 365" has the meaning
    statute_shorthand_targets: set[str] = set()
    for m_def in re.finditer(
        r'["“\'](?:Section|Clause|Article)\s+([0-9A-Za-z.]+?)["”\']\s*(?:(?:has\s+the\s+meaning|shall\s+have\s+the\s+meaning|means|refers\s+to|is\s+defined|as\s+defined)|\s*\))',
        full_text,
        re.IGNORECASE,
    ):
        statute_shorthand_targets.add(m_def.group(1).strip().lower())
    for m_def in re.finditer(
        r'\([^)]*?["“\'](?:Section|Clause|Article)\s+([0-9A-Za-z.]+?)["”\']\)',
        full_text,
        re.IGNORECASE,
    ):
        statute_shorthand_targets.add(m_def.group(1).strip().lower())

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

            preceding_context = seg_text[max(0, start_idx - 60) : start_idx]
            following_context = seg_text[end_idx : min(len(seg_text), end_idx + 120)]

            # 0. Check if self-reference ("this Clause", "such Section")
            if _SELF_REF_PAT.search(preceding_context):
                continue

            # 1. Check if preceded by external indicator ("under Section ...", "mutatis mutandis", etc.)
            if _EXTERNAL_PRECEDING_PAT.search(preceding_context):
                stats["external_ignored"] += 1
                continue

            # 2. Check if followed by external indicator ("... of the Companies Act", "... of the ... Agreement")
            if _EXTERNAL_FOLLOWING_PAT.search(following_context):
                stats["external_ignored"] += 1
                continue

            m_ext_agr = _EXTERNAL_AGREEMENT_PAT.search(following_context)
            if m_ext_agr:
                inner_name = m_ext_agr.group(1).strip().lower()
                if inner_name not in {"this", "the", "said"}:
                    stats["external_ignored"] += 1
                    continue

            # Check: followed by "of <named external instrument>" (e.g. "Article 31 of REACH")
            # Any reference followed by "of" plus a named instrument other than this Agreement,
            # the Agreement, this Contract, this Schedule or this Exhibit is external.
            m_of_inst = re.match(
                r"^\s*(?:\([A-Za-z0-9]+\)\s*)*of\s+(?:the\s+|this\s+|that\s+|said\s+|any\s+)?([A-Za-z0-9\s,.&'\(\)\-]{1,60}?\b)",
                following_context,
                re.IGNORECASE,
            )
            if m_of_inst:
                inst_norm = m_of_inst.group(1).strip().lower()
                if not (
                    inst_norm.startswith("agreement")
                    or inst_norm.startswith("contract")
                    or inst_norm.startswith("schedule")
                    or inst_norm.startswith("exhibit")
                ):
                    stats["external_ignored"] += 1
                    continue

            # 3. Check "thereof" referring to external agreement
            if re.search(r"^\s*(?:\([A-Za-z0-9]+\)\s*)*thereof\b", following_context, re.IGNORECASE):
                if re.search(r"\b(?:Agreement|Contract|License|Lease)\b", preceding_context, re.IGNORECASE):
                    stats["external_ignored"] += 1
                    continue

            # 4. Check if inside amending agreement context or text being inserted
            if is_amending_doc or _AMENDMENT_CONTEXT_PAT.search(seg_text):
                if _AMENDMENT_CONTEXT_PAT.search(preceding_context) or _AMENDMENT_CONTEXT_PAT.search(following_context[:60]):
                    stats["external_ignored"] += 1
                    continue
                # Check if inside quotation marks being inserted
                quotes_before = seg_text[:start_idx].count('"') + seg_text[:start_idx].count('“') - seg_text[:start_idx].count('”')
                if quotes_before % 2 == 1:
                    stats["external_ignored"] += 1
                    continue

            raw_target1 = m.group("target")
            raw_target2 = m.group("target2")
            conj = m.group("conj")

            # 5. Check statute-style sub-paragraph chains like 351(l)(3)(A)
            if _is_statute_subitem_chain(raw_target1, following_context):
                stats["external_ignored"] += 1
                continue

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

                # Ignore shorthand statute section definitions (e.g. "Section 222")
                if clean_t.lower() in statute_shorthand_targets:
                    stats["external_ignored"] += 1
                    continue

                # Skip self-reference (referring to the same clause)
                if segment.clause_ref and clean_t == segment.clause_ref:
                    continue

                # Check if target or any of its parent/ancestor clauses exists directly in parsed clauses
                target_candidates = [raw_t, clean_t, *_candidate_ancestors(raw_t)]
                if any(
                    cand in existing_clause_ids
                    or cand.lower() in existing_clause_ids
                    or _ROMAN_MAP.get(cand, "").lower() in existing_clause_ids
                    or _ARABIC_MAP.get(cand.upper(), "") in existing_clause_ids
                    for cand in target_candidates
                ):
                    continue

                # Statutory citations without standard keywords: e.g. "Section 409A", "Section 12(g)", "Section 16(b)"
                context_for_statute = seg_text[max(0, start_idx - 80) : min(len(seg_text), end_idx + 100)]
                if _is_statutory_citation(raw_t, clean_t, context_for_statute):
                    if clean_t not in existing_clause_ids and raw_t not in existing_clause_ids:
                        stats["external_ignored"] += 1
                        continue

                # Check safeguard: is target found in page text as a distinct clause heading line?
                escaped_t = re.escape(clean_t)
                heading_pat = (
                    rf"(?:^|\n)\s*(?:(?:Clause|Section|Article|Paragraph)\s+)?{escaped_t}(?:\.|\:|\s*[-—–])\s+[A-Z]"
                )
                if re.search(heading_pat, full_text):
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

        is_uncertain = _is_uncertain_reference(
            target,
            occurrences,
            existing_clause_ids,
            doc.clauses,
            full_text,
            is_amending_doc=is_amending_doc,
        )
        if is_uncertain:
            stats["uncertain_moved_to_low"] += 1
            severity = Severity.LOW
        else:
            severity = Severity.MEDIUM

        evidence_str = f"Target '{target}' referenced in: {first_snippet}"
        if ref_count > 1:
            evidence_str += f" (and {ref_count - 1} other occurrence(s))"
        if len(evidence_str) > MAX_EVIDENCE_CHARS:
            evidence_str = evidence_str[:MAX_EVIDENCE_CHARS]

        clause_info = f"clause(s) {', '.join(referencing_clauses)}" if referencing_clauses else "the document"
        uncertain_prefix = "Uncertain cross-reference: " if is_uncertain else ""
        explanation = (
            f"{uncertain_prefix}Cross-reference to '{target}' in {clause_info} cannot be resolved: "
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
                severity=severity,
                page=first_segment.page,
                clause_ref=first_segment.clause_ref,
                evidence=evidence_str,
                explanation=explanation,
                details={
                    "rule_id": "XRF001",
                    "missing_target": target,
                    "reference_count": ref_count,
                    "referencing_clauses": referencing_clauses,
                    "uncertain": is_uncertain,
                },
            )
        )

    return findings, stats
