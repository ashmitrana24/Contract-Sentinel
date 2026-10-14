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
from rapidfuzz.distance import Levenshtein

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
    r"\b((?:(?:[A-Z][A-Za-z0-9&'\-]*|&)[ \t]+){0,7}[A-Z][A-Za-z0-9&'\-]+"
    r"(?:,\s*|\s+)"
    r"(?:Pvt\.?\s*Ltd\.?|Private\s+Limited|Private\s+Ltd\.?|Ltd\.?|Limited|"
    r"Inc\.?|Incorporated|Corp\.?|Corporation|L\.?L\.?C\.?|L\.?L\.?P\.?))\b",
    re.UNICODE,
)

_SUFFIX_QUICK_CHECK = (
    "ltd", "inc", "corp", "llc", "llp", "limited", "private", "pvt", "plc", "l.l.c", "l.l.p",
)

# Common words to filter out if accidentally matched as entity names
_IGNORE_ENTITY_PREFIXES = {
    "the", "and", "or", "in", "of", "to", "for", "by", "under", "between",
}

_COMMON_NON_PARTY_WORDS = {
    # Ordinals and generic adjectives
    "first", "second", "third", "general", "united", "national", "state", "total",
    "standard", "global", "international", "federal", "local", "joint",
    # Legal document structure terms
    "agreement", "contract", "party", "parties", "section", "clause", "article",
    "schedule", "exhibit", "annex", "appendix", "amendment", "addendum",
    # Common generic business roles
    "service", "services", "each", "both", "either", "neither", "other", "such",
    "this", "that", "all",
    # Corporate structure terms (non-identifying on their own)
    "bank", "trust", "fund", "holdings", "group", "associates", "partners", "capital",
    "ventures", "management", "licensor", "licensee", "buyer", "seller", "vendor",
    "supplier", "distributor", "customer", "client", "provider", "operator",
    "owner", "agent", "trustee", "lender", "borrower",
    # Statutory reference markers — never a party short-name
    "rule", "rules", "regulation", "regulations", "act", "code", "statute",
    "order", "directive", "law",
    # Generic product/service terms commonly used as entity prefixes
    "hosting", "communication", "communications", "technology", "technologies",
    "systems", "solutions", "software", "platform", "network", "networks",
    "data", "digital", "cyber", "cloud", "media", "marketing", "consulting",
    "financial", "insurance", "healthcare", "medical", "pharma", "energy",
    "realty", "property", "logistics", "transport", "construction",
    # Geographic / state names used as short names
    "arkansas", "california", "texas", "new", "north", "south", "east", "west",
    "american", "british", "european", "asian", "indian", "chinese",
    "members", "maintenance", "freedom", "improved", "excluded", "termination",
    "mitchell", "deutsche", "legacy", "howmedica",
}

_NON_PARTY_ALIASES = {
    "effective date", "execution date", "commencement date", "initial term", "term",
    "joint ip", "equipment", "failure notice", "purpose", "act", "schedule", "agreement",
    "amendment", "exhibit", "section", "permitted applications", "background ip",
    "closing date", "expiration date", "confidential information", "work product",
    "services", "specifications", "notice", "notices", "premises", "property",
    "territory", "products", "goods", "trademark", "trademarks", "intellectual property", "ip",
}

_COMMON_ACRONYMS = {
    "SEC", "IRS", "FDA", "FCC", "FTC", "EPA", "DOJ", "EEOC", "GAAP", "HIPAA",
    "GDPR", "FERPA", "ERISA", "FINRA", "NASDAQ", "NYSE", "UCC", "CFR", "USC",
    "LLC", "LLP", "PLC", "USA", "UK", "EU", "CEO", "CFO", "COO", "CTO", "CIO",
    "VP", "SVP", "EVP", "HR", "IP", "NDA", "RFP", "RFQ", "SOW", "SLA", "API",
    "SDK", "URL", "PDF", "CSV", "XML", "HTML", "JSON", "HTTP", "HTTPS", "FTP",
    "SSH", "SSL", "TLS", "LAN", "WAN", "VPN", "IT", "QA", "QC", "ADA", "GCP",
    "SOP", "GLP", "GMP", "ICH", "ISO", "IND", "BLA", "ANDA", "DMF", "EMA",
    "PMDA", "WHO", "NIH", "CDC", "RGC", "VRB", "ERB", "FPI",
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
    res = " ".join(cleaned.lower().split())
    if res.startswith("the "):
        res = res[4:].strip()
    return res


def get_base_entity_name(normalized_name: str) -> str:
    """Strip known normalized corporate suffixes, jurisdictional phrases, and role qualifiers from normalized name."""
    res = normalized_name
    # Strip role qualifiers like ", as servicer", ", as agent" that follow the suffix
    res = re.sub(r"\s*,?\s+as\s+\w[\w\s]{0,30}$", "", res).strip()
    res = re.sub(r"\s*,?\s+(?:in\s+its\s+capacity\s+as)[\w\s,]{0,40}$", "", res).strip()
    # Strip jurisdictional descriptions like "a maryland corporation", "an ohio llc"
    res = re.sub(r"\s+an?\s+[a-z\s]+(?:corporation|company|llc|entity)[\w\s]*$", "", res).strip()
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
        # Filter out standalone dates
        if re.match(
            r"^(?:January|February|March|April|May|June|July|August|September|October|November|December|\d{1,2})[\s\d,]+$",
            name,
            re.I,
        ):
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
        # Strip trailing legal descriptions like ", a Delaware corporation", ", as Owner"
        name = re.sub(
            r",?\s+an?\s+[A-Za-z\s]+(?:corporation|company|limited\s+liability\s+company|partnership|banking\s+association|national\s+association|entity)[\w\s]*$",
            "",
            name,
            flags=re.I,
        ).strip()
        name = re.sub(r",?\s+as\s+\w[\w\s]{0,30}$", "", name, flags=re.I).strip()
        # Strip trailing DBA / Trade names, addresses, and jurisdiction clauses
        name = re.sub(r",?\s+(?:d/?b/?a|doing\s+business\s+as)\s+.*$", "", name, flags=re.I).strip()
        name = re.sub(r",?\s+located\s+at\s+.*$", "", name, flags=re.I).strip()
        name = re.sub(r",?\s+having\s+(?:its\s+principal\s+office|its\s+office|an\s+office)\s+.*$", "", name, flags=re.I).strip()
        name = re.sub(r",?\s+a\s+(?:corporation|entity)\s+organized\s+.*$", "", name, flags=re.I).strip()

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
    party_cand = (
        r"([A-Z0-9][A-Za-z0-9&'.\-\s]{1,80}?"
        r"(?:(?:,\s*|\s+)(?:Pvt\.?\s*Ltd\.?|Ltd\.?|Inc\.?|Corp\.?|LLC\.?|LLP\.?|Limited|Corporation|Company)(?:\b|(?=[,.\s]))"
        r"|(?=\s*\(|,\s*an?\b|,\s*having\b)))"
    )
    m_by_between = re.search(
        r"(?:entered\s+into\s+)?(?:by\s+and\s+)?(?:between|among)\s+"
        + party_cand +
        r"(?:,\s*an?\s+[^,\n\(]+?(?:corporation|company|limited\s+liability\s+company|entity))?"
        r"(?:,\s*having[^,\n\(]+)*?"
        r"(?:\s*\((?:hereinafter\s+(?:referred\s+to\s+as\s+)?(?:the\s+)?|the\s+)?[\"']([^\"']+)[\"']\))?"
        r"\s*,?\s+and\s+"
        + party_cand +
        r"(?:,\s*an?\s+[^,\n\(]+?(?:corporation|company|limited\s+liability\s+company|entity))?"
        r"(?:,\s*having[^,\n\(]+)*?"
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

    # 4. Search preamble for defined terms like (the "Company"), ("Client"), ("Vyera")
    defined_matches = re.finditer(
        r"(?:between|among|\band\b|;\s*|\n|^)\s*"
        r"([A-Z][A-Za-z0-9&',.\-\s]{2,100}?)"
        r"(?:,\s*an?\s+[^,\n\(]+?(?:corporation|company|limited\s+liability\s+company|entity))?"
        r"(?:,\s*having[^,\n\(]+)*?"
        r"\s*\((?:hereinafter\s+(?:referred\s+to\s+as\s+)?(?:the\s+)?|the\s+)?[\"']([^\"']+)[\"']\)",
        intro_text,
        re.I,
    )
    for m_def in defined_matches:
        raw_n = m_def.group(1).strip()
        alias = m_def.group(2).strip()
        if alias.lower() in _NON_PARTY_ALIASES:
            continue
        clean_name = re.sub(
            r"^(?:(?:this\s+)?[A-Za-z\s]+?Agreement\s+)?(?:dated\s+[A-Za-z0-9,\s]+?\s+)?(?:is\s+)?(?:entered\s+into\s+)?(?:by\s+and\s+)?(?:between|among)\s+",
            "",
            raw_n,
            flags=re.I,
        ).strip()
        clean_name = re.sub(r"^\band\s+", "", clean_name, flags=re.I).strip()
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
    full_text = "\n".join(p.text for p in doc.pages) if doc.pages else ""

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
        seg_lower = seg_text.lower()
        entity_matches = _ENTITY_SUFFIX_BODY_REGEX.finditer(seg_text) if any(s in seg_lower for s in _SUFFIX_QUICK_CHECK) else ()
        for m in entity_matches:
            cand_raw = m.group(1).strip()
            # If cand_raw contains a sentence boundary period followed by space (e.g. "Party. Horizon Systems Corp"),
            # trim to the portion following the sentence boundary, preserving abbreviations like Pvt., Co., Inc.
            if ". " in cand_raw:
                _parts = re.split(r"\.\s+", cand_raw)
                if len(_parts) > 1:
                    _valid_parts = [_parts[0]]
                    for _p in _parts[1:]:
                        _last_tok = _valid_parts[-1].split()[-1] if _valid_parts[-1].split() else ""
                        if _last_tok.lower().rstrip(".") in {"pvt", "co", "inc", "corp", "ltd", "llc", "llp", "u", "s", "no"} or (len(_last_tok.rstrip(".")) == 1 and _last_tok[0].isupper()):
                            _valid_parts[-1] = _valid_parts[-1] + ". " + _p
                        else:
                            _valid_parts = [_p]
                    cand_raw = _valid_parts[-1].strip()

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
            cand_raw = re.sub(r"^(?:About|CEO|President|Director|Signed\s+by|By\s*:?|Name\s*:?|To\s*:?|Attention\s*:?)\s+", "", cand_raw, flags=re.I).strip()
            # Deduplicate repeated identical leading token (e.g., 'Aimmune Aimmune')
            cand_raw = re.sub(r"^(\b[A-Za-z]+\b)\s+\1\b", r"\1", cand_raw, flags=re.I).strip()
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
                    score = max(score, score_part)

                if score > best_score:
                    best_score = score
                    best_party = party

            # Determine whether it's a party_name_variant or unknown_party_entity
            if best_party and best_score >= settings.party_similarity_threshold:
                if cand_norm != best_party.normalized_name:
                    # Check occurrence counts and affiliate usage: only flag if rarer than canonical
                    # and not consistently used as a separate entity across multiple clauses
                    cand_count = len(re.findall(rf"\b{re.escape(cand_raw)}\b", full_text, re.IGNORECASE))
                    canon_count = len(re.findall(rf"\b{re.escape(best_party.raw_name)}\b", full_text, re.IGNORECASE))

                    # If candidate is more frequent than canonical name, or used 2+ times across the document,
                    # treat as established entity/affiliate rather than a single-instance typo/variant
                    if cand_count > canon_count:
                        continue
                    if cand_count >= 2:
                        continue

                    is_affiliate = bool(
                        re.search(
                            rf"\b{re.escape(cand_raw)}\b[^.;\n]{{0,120}}?\b(?:affiliate|subsidiary|parent|consultant|contractor|supplier|predecessor|assign)\b",
                            full_text,
                            re.I,
                        )
                        or re.search(
                            rf"\b(?:affiliate|subsidiary|parent|including)\b[^.;\n]{{0,120}}?\b{re.escape(cand_raw)}\b",
                            full_text,
                            re.I,
                        )
                    )
                    if is_affiliate:
                        continue

                    _AFFILIATE_MODIFIER_WORDS = {
                        "services", "service", "group", "holdings", "holding",
                        "international", "consultants", "consultant",
                    }

                    cand_toks = set(cand_base.lower().split())
                    party_toks = set(best_party.base_name.lower().split())
                    diff_toks = cand_toks ^ party_toks
                    diff_clean = {t.strip(".,;:()") for t in diff_toks}

                    is_affiliate_word_diff = bool(
                        diff_clean and diff_clean.issubset(_AFFILIATE_MODIFIER_WORDS)
                    )

                    # Near-identical spellings (similarity >= 0.92, e.g. plural or one-letter differences)
                    # without corporate affiliate modifiers stay MEDIUM.
                    cb = cand_base.lower()
                    pb = best_party.base_name.lower()
                    base_ratio = fuzz.ratio(cb, pb) / 100.0
                    full_ratio = fuzz.ratio(cand_norm.lower(), best_party.normalized_name.lower()) / 100.0
                    sim_ratio = max(base_ratio, full_ratio)

                    is_one_letter = Levenshtein.distance(cb, pb) <= 1 or Levenshtein.distance(cand_norm.lower(), best_party.normalized_name.lower()) <= 1
                    is_plural = (
                        (cb.endswith("s") and cb[:-1] == pb)
                        or (pb.endswith("s") and pb[:-1] == cb)
                        or (cb.endswith("es") and cb[:-2] == pb)
                        or (pb.endswith("es") and pb[:-2] == cb)
                        or (cb.endswith("ies") and cb[:-3] + "y" == pb)
                        or (pb.endswith("ies") and pb[:-3] + "y" == cb)
                    )

                    if not is_affiliate_word_diff and (sim_ratio >= 0.92 or is_one_letter or is_plural):
                        prt1_sev = Severity.MEDIUM
                        expl = (
                            f"Party name variant '{cand_raw}' differs slightly from defined party "
                            f"'{best_party.raw_name}' (near-identical spelling; similarity {best_score:.1f}%)."
                        )
                    else:
                        prt1_sev = Severity.LOW
                        expl = (
                            f"Party name variant '{cand_raw}' extends or shortens defined party "
                            f"'{best_party.raw_name}' (possible affiliate; similarity {best_score:.1f}%)."
                        )

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
                                severity=prt1_sev,
                                page=segment.page,
                                clause_ref=segment.clause_ref,
                                evidence=f"Found '{cand_raw}' (expected party '{best_party.raw_name}') in: {snippet}",
                                explanation=expl,
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
        # 2. Undefined acronym or single-word variant in body (PRT003 / PRT004)
        # -------------------------------------------------------------------
        for party in parties:
            # Skip if this party already has a variant finding in this segment
            if any(f.clause_ref == segment.clause_ref and f.details.get("party_name") == party.raw_name for f in findings):
                continue

            p_tokens = party.raw_name.split()
            sec_word = p_tokens[1] if len(p_tokens) > 1 else ""
            cand_short = party.first_token if (party.first_token and len(party.first_token) >= 4 and len(p_tokens) > 1) else ""
            cand_acronym = party.initials if (party.initials and len(party.initials) >= 3 and cand_short != party.initials) else ""

            # Check PRT003: Undefined acronym acting as contracting party
            if cand_acronym and cand_acronym.lower() not in all_defined_aliases and cand_acronym.upper() not in _COMMON_ACRONYMS:
                a_pat = re.compile(rf"\b{re.escape(cand_acronym)}\b", re.IGNORECASE)
                m_init = a_pat.search(seg_text)
                if m_init:
                    # Must appear at most 2 times across the entire document
                    total_cand_count = len(a_pat.findall(full_text))
                    if 0 < total_cand_count <= 2:
                        after_text = seg_text[m_init.end() : m_init.end() + 60].lower()
                        before_text = seg_text[max(0, m_init.start() - 100) : m_init.start()].lower()

                        is_subject = bool(re.search(r"^\s+(?:shall|will|must|agrees|warrants|represents|covenants|undertakes|is\s+obligated|or\s+its\s+authorised|and\s+its\s+authorised|grants)\b", after_text))
                        is_possessive = bool(re.match(r"^['’]s\s+(?:obligations|records|rights|discretion|consent|personnel|duties|liabilities|confidential|performance|services|reasonable|employees)\b", after_text))
                        is_prepositional = bool(re.search(r"\b(?:consent\s+of|notice\s+to|provided\s+by|approved\s+by|entered\s+into\s+with|between\s+[\w\s,.\-'\"]+?and|for\s+all\s+services\s+rendered\s+by|deliverables\s+created\s+specifically\s+for|provide\s+to|provides\s+to|pay)\s*$", before_text))
                        is_between_x_and_y = bool(re.search(r"\bbetween\s*$", before_text) and re.match(r"^\s+and\b", after_text))

                        if is_subject or is_possessive or is_prepositional or is_between_x_and_y:
                            is_notice_or_sig = bool(
                                re.search(r"\b(?:notice|notices|communication|addresses)\b", str(segment.clause_ref or "").lower())
                                or re.search(r"\b(?:If to\s+|Attention:\s*|Attn:\s*|Facsimile:|Telecopy:|notices\s+shall\s+be\s+sent|notice\s+to\s*:)\b", seg_text, re.I)
                                or re.search(r"\b(?:IN WITNESS WHEREOF|executed as of|By:\s*|Title:\s*|Name:\s*|Authorized Signatory|Duly Authorized)\b", seg_text, re.I)
                            )
                            sev = Severity.LOW if is_notice_or_sig else Severity.MEDIUM

                            v_key = f"{party.raw_name}::{party.initials}::{segment.clause_ref}"
                            if v_key not in seen_variant_keys:
                                seen_variant_keys.add(v_key)
                                stats["variants_detected"] += 1
                                snippet = seg_text[max(0, m_init.start() - 40) : min(len(seg_text), m_init.end() + 40)]
                                findings.append(
                                    Finding(
                                        module=CONSISTENCY_MODULE,
                                        type="party_name_variant",
                                        severity=sev,
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

            # Check PRT004: Undefined short name acting as contracting party
            if (
                cand_short
                and cand_short.lower() not in all_defined_aliases
                and cand_short.lower() not in _COMMON_NON_PARTY_WORDS
                and first_token_counts.get(cand_short.lower(), 0) == 1
                and party.raw_name in party_first_tok_pats
            ):
                m_tok = party_first_tok_pats[party.raw_name].search(seg_text)
                if m_tok:
                    # Must appear at most 2 times across the entire document
                    total_cand_count = len(party_first_tok_pats[party.raw_name].findall(full_text))
                    if 0 < total_cand_count <= 2:
                        after_text = seg_text[m_tok.end() : m_tok.end() + 60].lower()
                        before_text = seg_text[max(0, m_tok.start() - 100) : m_tok.start()].lower()

                        is_subject = bool(re.search(r"^\s+(?:shall|will|must|agrees|warrants|represents|covenants|undertakes|is\s+obligated|or\s+its\s+authorised|and\s+its\s+authorised|grants)\b", after_text))
                        is_possessive = bool(re.match(r"^['’]s\s+(?:obligations|records|rights|discretion|consent|personnel|duties|liabilities|confidential|performance|services|reasonable|employees)\b", after_text))
                        is_prepositional = bool(re.search(r"\b(?:consent\s+of|notice\s+to|provided\s+by|approved\s+by|entered\s+into\s+with|between\s+[\w\s,.\-'\"]+?and|for\s+all\s+services\s+rendered\s+by|deliverables\s+created\s+specifically\s+for|provide\s+to|provides\s+to|pay)\s*$", before_text))
                        is_between_x_and_y = bool(re.search(r"\bbetween\s*$", before_text) and re.match(r"^\s+and\b", after_text))

                        if is_subject or is_possessive or is_prepositional or is_between_x_and_y:
                            is_notice_or_sig = bool(
                                re.search(r"\b(?:notice|notices|communication|addresses)\b", str(segment.clause_ref or "").lower())
                                or re.search(r"\b(?:If to\s+|Attention:\s*|Attn:\s*|Facsimile:|Telecopy:|notices\s+shall\s+be\s+sent|notice\s+to\s*:)\b", seg_text, re.I)
                                or re.search(r"\b(?:IN WITNESS WHEREOF|executed as of|By:\s*|Title:\s*|Name:\s*|Authorized Signatory|Duly Authorized)\b", seg_text, re.I)
                            )
                            sev = Severity.LOW if is_notice_or_sig else Severity.MEDIUM

                            v_key = f"{party.raw_name}::{party.first_token}::{segment.clause_ref}"
                            if v_key not in seen_variant_keys:
                                seen_variant_keys.add(v_key)
                                stats["variants_detected"] += 1
                                snippet = seg_text[max(0, m_tok.start() - 40) : min(len(seg_text), m_tok.end() + 40)]
                                findings.append(
                                    Finding(
                                        module=CONSISTENCY_MODULE,
                                        type="party_name_variant",
                                        severity=sev,
                                        page=segment.page,
                                        clause_ref=segment.clause_ref,
                                        evidence=f"Found undefined short name '{party.first_token}' for party '{party.raw_name}' in: {snippet}",
                                        explanation=f"Short name '{party.first_token}' is used in clause {segment.clause_ref} without being defined as an alias for '{party.raw_name}'.",
                                        details={
                                            "rule_id": "PRT004",
                                            "party_name": party.raw_name,
                                            "variant": party.first_token,
                                            "similarity": 85.0,
                                        },
                                    )
                            )

    return findings, stats
