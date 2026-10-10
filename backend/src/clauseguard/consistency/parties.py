"""Party extraction and party name consistency detector.

Detects:
1. party_name_variant (MEDIUM):
   A name found in the body that is a close variant of a known party name
   (e.g. rapidfuzz similarity >= 85, or undefined alias/acronym substitution),
   but not identical after entity suffix normalization.
   Reports both spellings and location.
2. unknown_party_entity (LOW):
   A legal entity name (ending in a corporate suffix like Pvt. Ltd., Ltd., Inc.)
   found in the body that matches no party and no variant.
   Capped at 10 per document.

Entity suffix normalization:
  "Private Limited" == "Pvt. Ltd." == "Pvt Ltd"
  "Limited" == "Ltd." == "Ltd"
  "Incorporated" == "Inc." == "Inc"
  "Corporation" == "Corp." == "Corp"
  "L.L.C." == "LLC"
  "LLP"
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from rapidfuzz import fuzz

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
# Suffix normalization rules
# ---------------------------------------------------------------------------

_SUFFIX_NORMALIZATIONS: list[tuple[re.Pattern[str], str]] = [
    # Private Limited variants -> "pvt ltd"
    (
        re.compile(
            r"\b(?:pvt\.?\s*ltd\.?|private\s+limited|private\s+ltd\.?|pvt\.?\s*limited)\b",
            re.IGNORECASE,
        ),
        "pvt ltd",
    ),
    # Public Limited Company -> "plc"
    (
        re.compile(
            r"\b(?:public\s+limited\s+company|p\.?l\.?c\.?)\b",
            re.IGNORECASE,
        ),
        "plc",
    ),
    # Limited -> "ltd" (must run after pvt ltd and plc)
    (
        re.compile(r"\b(?:limited|ltd\.?)\b", re.IGNORECASE),
        "ltd",
    ),
    # Incorporated -> "inc"
    (
        re.compile(r"\b(?:incorporated|inc\.?)\b", re.IGNORECASE),
        "inc",
    ),
    # Corporation -> "corp"
    (
        re.compile(r"\b(?:corporation|corp\.?)\b", re.IGNORECASE),
        "corp",
    ),
    # LLC -> "llc"
    (
        re.compile(
            r"\b(?:limited\s+liability\s+company|l\.?l\.?c\.?)\b",
            re.IGNORECASE,
        ),
        "llc",
    ),
    # LLP -> "llp"
    (
        re.compile(
            r"\b(?:limited\s+liability\s+partnership|l\.?l\.?p\.?)\b",
            re.IGNORECASE,
        ),
        "llp",
    ),
]

_ENTITY_SUFFIX_BODY_REGEX = re.compile(
    r"\b([A-Z][A-Za-z0-9&',.\- \t]{1,60}?[ \t]+"
    r"(?:Pvt\.?\s*Ltd\.?|Private\s+Limited|Private\s+Ltd\.?|Ltd\.?|Limited|"
    r"Inc\.?|Incorporated|Corp\.?|Corporation|L\.?L\.?C\.?|L\.?L\.?P\.?))\b",
    re.UNICODE,
)

# Common words to filter out if accidentally matched as entity names
_IGNORE_ENTITY_PREFIXES = {
    "the", "and", "or", "in", "of", "to", "for", "by", "under", "between",
}

_COMMON_NON_PARTY_WORDS = {
    "first", "second", "third", "general", "united", "national", "state", "total",
    "standard", "global", "international", "agreement", "contract", "party", "parties",
    "section", "clause", "article", "schedule", "exhibit", "service", "services",
    "each", "both", "either", "neither", "other", "such", "this", "that", "all",
    "bank", "trust", "fund", "holdings", "group", "associates", "partners", "capital",
    "ventures", "management", "licensor", "licensee", "buyer", "seller", "vendor",
    "supplier", "distributor", "customer", "client", "provider",
}


def normalize_entity_name(name: str) -> str:
    """Normalize a company/entity name for comparison.

    Strips punctuation, case-folds, and normalizes legal entity suffixes
    (e.g., 'Private Limited' -> 'pvt ltd', 'Ltd.' -> 'ltd').
    """
    cleaned = name.strip()
    # Normalize suffixes
    for pattern, replacement in _SUFFIX_NORMALIZATIONS:
        cleaned = pattern.sub(f" {replacement} ", cleaned)

    # Remove commas, periods, quotes, extra punctuation
    cleaned = re.sub(r"[,.'\"`\(\)]", " ", cleaned)
    # Normalize whitespace and lowercase
    return " ".join(cleaned.lower().split())


def get_base_entity_name(normalized_name: str) -> str:
    """Strip known normalized corporate suffixes from normalized name."""
    res = normalized_name
    for sfx in ["pvt ltd", "plc", "ltd", "inc", "corp", "llc", "llp"]:
        if res.endswith(f" {sfx}"):
            res = res[: -len(sfx) - 1].strip()
    return res


@dataclass
class PartyInfo:
    """Information about an extracted contract party."""

    raw_name: str
    normalized_name: str
    base_name: str
    defined_aliases: list[str] = field(default_factory=list)
    initials: str = ""
    first_token: str = ""


# ---------------------------------------------------------------------------
# Party extraction from preamble and early clauses
# ---------------------------------------------------------------------------

def extract_parties(
    doc: ParsedDocument,
    intro_text: str,
) -> list[PartyInfo]:
    """Extract parties, their entity forms, and defined aliases from preamble text."""
    parties: list[PartyInfo] = []
    seen_normalized: set[str] = set()

    def _add_party(name: str, aliases: list[str] | None = None) -> None:
        name = name.strip().rstrip(" ,.;:")
        # Filter obvious non-entity labels
        if not name or len(name) < 3 or len(name) > 100:
            return
        # If name has leading preamble markers like "dated ... between" or "Between:", strip it
        name = re.sub(
            r"^(?:(?:this\s+)?[A-Za-z\s]+?Agreement\s+)?(?:dated\s+[A-Za-z0-9,\s]+?\s+)?(?:is\s+)?(?:entered\s+into\s+)?(?:by\s+and\s+)?(?:between|among)\s+",
            "",
            name,
            flags=re.I,
        ).strip()
        name = re.sub(r"^(?:Between|Among|Party\s*\d+)\s*[:\-]?\s*", "", name, flags=re.I).strip()
        name = re.sub(r"^\band\s+", "", name, flags=re.I).strip()

        norm = normalize_entity_name(name)
        if norm in seen_normalized or not norm:
            return
        seen_normalized.add(norm)

        base = get_base_entity_name(norm)
        # Compute initials from capitalized words
        tokens = [w for w in re.split(r"[\s\-]+", name) if w and w[0].isupper()]
        initials = "".join(w[0] for w in tokens) if len(tokens) >= 2 else ""
        first_tok = tokens[0] if tokens else ""

        alias_list = [a.strip() for a in (aliases or []) if a and a.strip()]
        parties.append(
            PartyInfo(
                raw_name=name,
                normalized_name=norm,
                base_name=base,
                defined_aliases=alias_list,
                initials=initials,
                first_token=first_tok,
            )
        )

    # 1. Structured "Between: X (Role) and Y (Role)"
    m_between = re.search(
        r"Between:\s*([^\n\(\)]+?)(?:\s*\((.*?)\))?\s+and\s+([^\n\(\)]+?)(?:\s*\((.*?)\))?(?:\r?\n|$)",
        intro_text,
        re.I,
    )
    if m_between:
        aliases_a = [m_between.group(2)] if m_between.group(2) else []
        aliases_b = [m_between.group(4)] if m_between.group(4) else []
        _add_party(m_between.group(1), aliases_a)
        _add_party(m_between.group(3), aliases_b)
        if len(parties) >= 2:
            return parties

    # 2. Preamble "entered into by and between X ... and Y"
    m_by_between = re.search(
        r"(?:entered\s+into\s+)?(?:by\s+and\s+)?(?:between|among)\s+([^\n,]+?(?:Pvt\.?\s*Ltd\.?|Ltd\.?|Inc\.?|Corp\.?|LLC|LLP|Limited|Corporation|Company)?)"
        r"(?:,\s*having[^,\n]+)*?"
        r"(?:\s*\((?:hereinafter\s+(?:referred\s+to\s+as\s+)?(?:the\s+)?|the\s+)?[\"']([^\"']+)[\"']\))?"
        r"\s+and\s+"
        r"([^\n,]+?(?:Pvt\.?\s*Ltd\.?|Ltd\.?|Inc\.?|Corp\.?|LLC|LLP|Limited|Corporation|Company)?)"
        r"(?:,\s*having[^,\n]+)*?"
        r"(?:\s*\((?:hereinafter\s+(?:referred\s+to\s+as\s+)?(?:the\s+)?|the\s+)?[\"']([^\"']+)[\"']\))?",
        intro_text,
        re.I,
    )
    if m_by_between:
        aliases_a = [m_by_between.group(2)] if m_by_between.group(2) else []
        aliases_b = [m_by_between.group(4)] if m_by_between.group(4) else []
        _add_party(m_by_between.group(1), aliases_a)
        _add_party(m_by_between.group(3), aliases_b)
        if len(parties) >= 2:
            return parties

    # 3. Title format: "... BETWEEN X AND Y"
    m_title = re.search(
        r"\b(?:AGREEMENT|CONTRACT)\s+(?:BY\s+AND\s+)?BETWEEN\s+([^\n]+?)\s+AND\s+([^\n]+?)(?:\n|$)",
        intro_text,
        re.I,
    )
    if m_title:
        _add_party(m_title.group(1))
        _add_party(m_title.group(2))
        if len(parties) >= 2:
            return parties

    # 4. Search preamble for defined terms like (the "Company"), ("Client")
    defined_matches = re.findall(
        r"([A-Z][A-Za-z0-9&',.\-\s]{2,60}?)\s*\((?:hereinafter\s+(?:referred\s+to\s+as\s+)?(?:the\s+)?|the\s+)?[\"']([^\"']+)[\"']\)",
        intro_text,
    )
    for name, alias in defined_matches:
        name_parts = re.split(r"\b(?:is\s+between|between|among|\band\b)\s+", name, flags=re.I)
        clean_name = name_parts[-1] if name_parts else name
        _add_party(clean_name, [alias])

    return parties


# ---------------------------------------------------------------------------
# Detector
# ---------------------------------------------------------------------------

def detect_party_inconsistencies(
    doc: ParsedDocument,
    index: TextIndex,
    settings: ConsistencySettings,
) -> tuple[list[Finding], dict[str, Any]]:
    """Check party name consistency across contract segments."""
    findings: list[Finding] = []
    stats: dict[str, Any] = {
        "parties_found": 0,
        "variants_detected": 0,
        "unknown_entities_detected": 0,
        "skipped_reason": None,
    }

    # Build intro text from page 0 and early clauses (clause 0 and 1)
    p0_text = doc.pages[0].text if doc.pages else ""
    early_clauses_text = "\n".join(c.text for c in doc.clauses[:2])
    intro_text = f"{p0_text}\n{early_clauses_text}"

    parties = extract_parties(doc, intro_text)
    stats["parties_found"] = len(parties)

    if len(parties) < settings.min_parties_for_detector:
        stats["skipped_reason"] = "fewer_than_2_parties"
        return findings, stats

    # Precompute party normalized names, base names, aliases, and acronyms
    party_normalized_set = {p.normalized_name for p in parties}
    party_bases = {p.base_name for p in parties}
    all_defined_aliases = {
        normalize_entity_name(alias)
        for p in parties
        for alias in p.defined_aliases
    }

    # Count distinct party first tokens to prevent flagging if both parties share a prefix
    first_token_counts: dict[str, int] = {}
    for p in parties:
        if p.first_token and len(p.first_token) >= 3:
            tok = p.first_token.lower()
            first_token_counts[tok] = first_token_counts.get(tok, 0) + 1

    # Precompute standalone token counts across all body segments once
    sfx_pat_str = r"(?:Pvt\.?|Ltd\.?|Inc\.?|Corp\.?|LLP|LLC|Limited|Private|Holdings|Group)"
    standalone_token_counts: dict[str, int] = {}
    party_first_tok_pats: dict[str, re.Pattern] = {}
    for p in parties:
        if p.first_token and len(p.first_token) >= 4:
            p_toks = p.raw_name.split()
            sec_word = p_toks[1] if len(p_toks) > 1 else ""
            p_pat = re.compile(rf"\b{re.escape(p.first_token)}\b(?!\s+(?:{re.escape(sec_word)}|{sfx_pat_str}))", re.IGNORECASE)
            party_first_tok_pats[p.raw_name] = p_pat
            count = 0
            for s in index.segments:
                if s.clause_ref not in ("0", "preamble", "title") and p_pat.search(s.text):
                    count += 1
                    if count >= 3:
                        break
            standalone_token_counts[p.raw_name] = count

    unknown_party_count = 0
    seen_variant_keys: set[str] = set()

    for segment in index.segments:
        # Skip preamble or clause 0 where parties are formally introduced and defined
        if segment.clause_ref in ("0", "preamble", "title"):
            continue

        seg_text = segment.text
        if not seg_text.strip():
            continue

        # -------------------------------------------------------------------
        # 1. Entity-suffix matches (e.g., "Acme Technology Pvt Ltd", "SINA International Ltd.")
        # -------------------------------------------------------------------
        for m in _ENTITY_SUFFIX_BODY_REGEX.finditer(seg_text):
            cand_raw = m.group(1).strip()
            # If cand_raw contains a sentence boundary period followed by space (e.g. "Party. Horizon Systems Corp"),
            # trim to the portion following the sentence boundary.
            if ". " in cand_raw:
                cand_raw = re.split(r"\.\s+", cand_raw)[-1].strip()

            # Check if preceding capitalized words before m.start() complete the entity name (line wraps)
            prec_words = re.findall(r"[A-Z][A-Za-z0-9&'\-]+", seg_text[max(0, m.start() - 50) : m.start()])
            if prec_words:
                for k in range(len(prec_words), 0, -1):
                    prefix = " ".join(prec_words[-k:])
                    cand_expanded = f"{prefix} {cand_raw}"
                    if normalize_entity_name(cand_expanded) in party_normalized_set:
                        cand_raw = cand_expanded
                        break

            # Clean up leading punctuation or words
            first_word = cand_raw.split()[0].lower() if cand_raw.split() else ""
            if first_word in _IGNORE_ENTITY_PREFIXES:
                cand_raw = " ".join(cand_raw.split()[1:])
            if len(cand_raw) < 4:
                continue

            cand_norm = normalize_entity_name(cand_raw)
            if not cand_norm or cand_norm in party_normalized_set or cand_norm in all_defined_aliases:
                # Exact normalized match: e.g. "Acme Technologies Private Limited" == "Acme Technologies Pvt. Ltd."
                continue

            cand_base = get_base_entity_name(cand_norm)
            if not cand_base or cand_base in party_bases:
                continue

            # Check fuzzy similarity against known parties
            best_party: PartyInfo | None = None
            best_score = 0.0

            for party in parties:
                score_full = fuzz.ratio(cand_norm, party.normalized_name)
                score_base = fuzz.ratio(cand_base, party.base_name)
                score_tok = fuzz.token_sort_ratio(cand_norm, party.normalized_name)
                score_part = fuzz.partial_ratio(cand_base, party.base_name) if len(party.base_name) >= 4 else 0.0

                shared_brand = False
                c_toks = cand_base.split()
                p_toks = party.base_name.split()
                if c_toks and p_toks and c_toks[0] == p_toks[0] and len(c_toks[0]) >= 3:
                    if c_toks[0] not in _COMMON_NON_PARTY_WORDS:
                        shared_brand = True

                score = max(score_full, score_base, score_tok)
                if shared_brand:
                    score = max(score, score_part, 88.0)

                if score > best_score:
                    best_score = score
                    best_party = party

            # Determine whether it's a party_name_variant or unknown_party_entity
            if best_party and best_score >= settings.party_similarity_threshold:
                if cand_norm != best_party.normalized_name:
                    v_key = f"{best_party.raw_name}::{cand_raw}::{segment.clause_ref}"
                    if v_key not in seen_variant_keys:
                        seen_variant_keys.add(v_key)
                        stats["variants_detected"] += 1
                        snippet = seg_text[max(0, m.start() - 40) : min(len(seg_text), m.end() + 40)]
                        if len(snippet) > MAX_EVIDENCE_CHARS:
                            snippet = snippet[:MAX_EVIDENCE_CHARS]

                        findings.append(
                            Finding(
                                module=CONSISTENCY_MODULE,
                                type="party_name_variant",
                                severity=Severity.MEDIUM,
                                page=segment.page,
                                clause_ref=segment.clause_ref,
                                evidence=f"Found '{cand_raw}' (expected party '{best_party.raw_name}') in: {snippet}",
                                explanation=(
                                    f"Party name variant '{cand_raw}' differs from defined party "
                                    f"'{best_party.raw_name}' (similarity {best_score:.1f}%)."
                                ),
                                details={
                                    "rule_id": "PRT001",
                                    "party_name": best_party.raw_name,
                                    "variant": cand_raw,
                                    "similarity": round(best_score, 1),
                                },
                            )
                        )
            else:
                # Matches no party closely: unknown_party_entity (LOW, capped)
                if cand_base not in party_bases and unknown_party_count < settings.max_unknown_parties:
                    unknown_party_count += 1
                    stats["unknown_entities_detected"] += 1
                    snippet = seg_text[max(0, m.start() - 40) : min(len(seg_text), m.end() + 40)]
                    if len(snippet) > MAX_EVIDENCE_CHARS:
                        snippet = snippet[:MAX_EVIDENCE_CHARS]

                    findings.append(
                        Finding(
                            module=CONSISTENCY_MODULE,
                            type="unknown_party_entity",
                            severity=Severity.LOW,
                            page=segment.page,
                            clause_ref=segment.clause_ref,
                            evidence=f"Entity name '{cand_raw}' in: {snippet}",
                            explanation=(
                                f"Legal entity '{cand_raw}' appears in the text but is not among "
                                f"the defined contracting parties."
                            ),
                            details={
                                "rule_id": "PRT002",
                                "entity_name": cand_raw,
                            },
                        )
                    )

        # -------------------------------------------------------------------
        # 2. Undefined acronym or single-word variant in body
        # -------------------------------------------------------------------
        for party in parties:
            # Skip if this party already has a variant finding in this segment
            if any(f.clause_ref == segment.clause_ref and f.details.get("party_name") == party.raw_name for f in findings):
                continue

            if party.initials and len(party.initials) >= 3:
                if party.initials.lower() not in all_defined_aliases:
                    m_init = re.search(rf"\b{re.escape(party.initials)}\b", seg_text)
                    if m_init:
                        v_key = f"{party.raw_name}::{party.initials}::{segment.clause_ref}"
                        if v_key not in seen_variant_keys:
                            seen_variant_keys.add(v_key)
                            stats["variants_detected"] += 1
                            snippet = seg_text[max(0, m_init.start() - 40) : min(len(seg_text), m_init.end() + 40)]
                            findings.append(
                                Finding(
                                    module=CONSISTENCY_MODULE,
                                    type="party_name_variant",
                                    severity=Severity.MEDIUM,
                                    page=segment.page,
                                    clause_ref=segment.clause_ref,
                                    evidence=f"Found undefined abbreviation '{party.initials}' for party '{party.raw_name}' in: {snippet}",
                                    explanation=f"Party abbreviation '{party.initials}' is used in clause {segment.clause_ref} but not defined as an alias for '{party.raw_name}'.",
                                    details={
                                        "rule_id": "PRT003",
                                        "party_name": party.raw_name,
                                        "variant": party.initials,
                                        "similarity": 90.0,
                                    },
                                )
                            )
                            continue

            p_tokens = party.raw_name.split()
            second_word = p_tokens[1] if len(p_tokens) > 1 else ""
            if party.first_token and len(party.first_token) >= 4 and second_word:
                tok_lower = party.first_token.lower()
                # If defined aliases are only generic placeholders ("party 1", "party 2"), using first token is standard
                has_substantive_alias = any(
                    a.lower() not in {"party 1", "party 2", "party", "party one", "party two"}
                    for a in party.defined_aliases
                )
                if not has_substantive_alias and party.defined_aliases:
                    continue

                # If first token alone appears in 3 or more clauses, it is established informal usage, not a rogue tamper
                if standalone_token_counts.get(party.raw_name, 0) >= 3:
                    continue

                if (
                    tok_lower not in all_defined_aliases
                    and tok_lower not in _COMMON_NON_PARTY_WORDS
                    and first_token_counts.get(tok_lower, 0) == 1
                    and party.raw_name in party_first_tok_pats
                ):
                    m_tok = party_first_tok_pats[party.raw_name].search(seg_text)
                    if m_tok:
                        after_text = seg_text[m_tok.end() : m_tok.end() + 35].lower()
                        before_text = seg_text[max(0, m_tok.start() - 35) : m_tok.start()].lower()
                        is_possessive = after_text.startswith(("'s", "’s", " 's"))
                        is_action = any(w in after_text for w in ["shall", "may", "will", "agrees", "warrants", "represents", "or its", "and its", "covenants", "undertakes", "bears", "pays", "liable", "process"])
                        is_prep = any(
                            re.search(rf"\b{prep}\s*$", before_text)
                            for prep in ["between", "among", "to", "by", "of", "with", "for", "against", "from", "audit", "consent", "and", "or"]
                        )
                        if is_possessive or is_action or is_prep:
                            v_key = f"{party.raw_name}::{party.first_token}::{segment.clause_ref}"
                            if v_key not in seen_variant_keys:
                                seen_variant_keys.add(v_key)
                                stats["variants_detected"] += 1
                                snippet = seg_text[max(0, m_tok.start() - 40) : min(len(seg_text), m_tok.end() + 40)]
                                findings.append(
                                    Finding(
                                        module=CONSISTENCY_MODULE,
                                        type="party_name_variant",
                                        severity=Severity.MEDIUM,
                                        page=segment.page,
                                        clause_ref=segment.clause_ref,
                                        evidence=f"Found undefined short name '{party.first_token}' for party '{party.raw_name}' in: {snippet}",
                                        explanation=f"Short name '{party.first_token}' is used in clause {segment.clause_ref} without being defined as an alias for '{party.raw_name}'.",
                                        details={
                                            "rule_id": "PRT004",
                                            "party_name": party.raw_name,
                                            "variant": party.first_token,
                                            "similarity": 90.0,
                                        },
                                    )
                                )

    return findings, stats
