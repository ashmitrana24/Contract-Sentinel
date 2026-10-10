"""Deterministic date parser and contract date consistency detectors.

Parses contract dates:
- "1st day of January, 2026", "twenty-first day of January 2026"
- "January 1, 2026", "1 Jan 2026", "1st January 2026"
- "01/01/2026", "01.01.2026", "01-01-2026", "2026-01-01"
- Configurable day/month ordering (default DMY for Indian contracts).
- Identifies ambiguous numeric dates (day <= 12, month <= 12, day != month), reducing severity by one level.
- Rejects impossible dates (e.g. 31 February).

Detectors:
- date_order_conflict: end date earlier than start date (HIGH).
- effective_date_conflict: Effective Date assigned two different dates by definition phrases (MEDIUM).
- term_length_conflict: stated period differs from date span by > tolerance days (MEDIUM).
"""

from __future__ import annotations

import datetime
import re
from dataclasses import dataclass

from clauseguard.consistency.models import (
    CONSISTENCY_MODULE,
    MAX_EVIDENCE_CHARS,
    ConsistencySettings,
)
from clauseguard.consistency.numbers import words_to_decimal
from clauseguard.consistency.text_index import ContractSegment, TextIndex, split_sentences
from clauseguard.schemas.findings import Finding, Severity
from clauseguard.schemas.parsed import ParsedDocument

# Ordinal words to integer
_ORDINALS: dict[str, int] = {
    "first": 1,
    "second": 2,
    "third": 3,
    "fourth": 4,
    "fifth": 5,
    "sixth": 6,
    "seventh": 7,
    "eighth": 8,
    "ninth": 9,
    "tenth": 10,
    "eleventh": 11,
    "twelfth": 12,
    "thirteenth": 13,
    "fourteenth": 14,
    "fifteenth": 15,
    "sixteenth": 16,
    "seventeenth": 17,
    "eighteenth": 18,
    "nineteenth": 19,
    "twentieth": 20,
    "twenty-first": 21,
    "twenty-second": 22,
    "twenty-third": 23,
    "twenty-fourth": 24,
    "twenty-fifth": 25,
    "twenty-sixth": 26,
    "twenty-seventh": 27,
    "twenty-eighth": 28,
    "twenty-ninth": 29,
    "thirtieth": 30,
    "thirty-first": 31,
}

# Month names to 1-based number
_MONTHS: dict[str, int] = {
    "january": 1,
    "jan": 1,
    "february": 2,
    "feb": 2,
    "march": 3,
    "mar": 3,
    "april": 4,
    "apr": 4,
    "may": 5,
    "june": 6,
    "jun": 6,
    "july": 7,
    "jul": 7,
    "august": 8,
    "aug": 8,
    "september": 9,
    "sep": 9,
    "sept": 9,
    "october": 10,
    "oct": 10,
    "november": 11,
    "nov": 11,
    "december": 12,
    "dec": 12,
}

# Bounded regex patterns for date extraction in text
_DATE_PATTERNS = [
    # 1. ISO: YYYY-MM-DD or YYYY/MM/DD
    re.compile(r"\b(?P<iso>\d{4}[-/]\d{1,2}[-/]\d{1,2})\b"),
    # 2. Ordinal day of Month, Year: "1st day of January, 2026" or "twenty-first day of January 2026"
    re.compile(
        r"\b(?P<ord>(?:\d{1,2}(?:st|nd|rd|th)?|[a-z-]+)\s+day\s+of\s+[A-Za-z]+[,\s]+\d{4})\b",
        re.IGNORECASE,
    ),
    # 3. Day Month Year: "1st January 2026", "1 January 2026", "1-Jan-2026"
    re.compile(
        r"\b(?P<dmy>\d{1,2}(?:st|nd|rd|th)?[\s-]+[A-Za-z]+[\s,-]+\d{4})\b",
        re.IGNORECASE,
    ),
    # 4. Month Day Year: "January 1, 2026", "January 1st, 2026"
    re.compile(
        r"\b(?P<mdy>[A-Za-z]+\s+\d{1,2}(?:st|nd|rd|th)?[,\s]+\d{4})\b",
        re.IGNORECASE,
    ),
    # 5. Numeric: DD/MM/YYYY, MM/DD/YYYY, DD.MM.YYYY, DD-MM-YYYY
    re.compile(r"\b(?P<num>\d{1,2}[/.-]\d{1,2}[/.-]\d{2,4})\b"),
]

# Role detection regexes
_START_ROLE_RE = re.compile(
    r"\b(?:effective\s+(?:as\s+of|on|from)|commencing\s+(?:on|from)|dated\s+(?:as\s+of|on)?|made\s+on|entered\s+into\s+(?:on|as\s+of)|Effective\s+Date\b)",
    re.IGNORECASE,
)

_END_ROLE_RE = re.compile(
    r"\b(?:terminate[sd]?\s+on|expire[sd]?\s+on|ends?\s+on|valid\s+(?:till|until)|continue\s+until|in\s+effect\s+until|Expiration\s+Date\b|Termination\s+Date\b)",
    re.IGNORECASE,
)

_EFFECTIVE_DEF_RE = re.compile(
    r"""(?ix)
    (?:
        ["'“]Effective\s+Date["'”] |
        \(the\s+["'“]Effective\s+Date["'”]\) |
        \bEffective\s+Date\b
    )
    \s*(?:means|is|shall\s+be|:)\s*
    """,
)

_TERM_PERIOD_RE = re.compile(
    r"""(?ix)
    \b(?:for\s+a\s+period\s+of|term\s+of|period\s+of|duration\s+of)\s+
    (?P<qty>\w+|\d+)\s*
    (?:\((?P<paren_qty>\w+|\d+)\))?\s*
    (?P<unit>years?|months?|days?|weeks?)\b
    """
)


@dataclass(frozen=True)
class ParsedDate:
    """Structured representation of a parsed contract date."""

    date: datetime.date
    raw: str
    is_ambiguous: bool = False


@dataclass
class DateOccurrence:
    """A date occurring in a contract with its surrounding context and detected role."""

    parsed: ParsedDate
    role: str  # "start" | "end" | "effective_def" | "other"
    clause_ref: str | None
    page: int
    context_snippet: str
    raw_match: str


def parse_date(date_str: str, date_format_order: str = "DMY") -> ParsedDate | None:
    """Parse a date string deterministically.

    Rejects impossible dates (e.g. 31 February).
    Flags ambiguous numeric dates (day <= 12, month <= 12, day != month).
    """
    if not date_str or not isinstance(date_str, str):
        return None

    s = date_str.strip().rstrip(",.")
    if not s:
        return None

    # 1. ISO format: YYYY-MM-DD or YYYY/MM/DD
    m_iso = re.fullmatch(r"(\d{4})[-/](\d{1,2})[-/](\d{1,2})", s)
    if m_iso:
        y, m, d = int(m_iso.group(1)), int(m_iso.group(2)), int(m_iso.group(3))
        if y < 1900 or y > 2100:
            return None
        try:
            return ParsedDate(date=datetime.date(y, m, d), raw=s, is_ambiguous=False)
        except ValueError:
            return None

    # 2. Ordinal day of Month, Year: "1st day of January, 2026"
    m_ord = re.fullmatch(
        r"(\d{1,2}(?:st|nd|rd|th)?|[a-z-]+)\s+day\s+of\s+([a-z]+)[,\s]+(\d{4})",
        s,
        re.IGNORECASE,
    )
    if m_ord:
        d_raw = m_ord.group(1).lower()
        m_raw = m_ord.group(2).lower()
        y_val = int(m_ord.group(3))
        day_val = None
        if re.match(r"^\d+", d_raw):
            day_val = int(re.match(r"^\d+", d_raw).group(0))
        elif d_raw in _ORDINALS:
            day_val = _ORDINALS[d_raw]
        m_num = _MONTHS.get(m_raw)
        if day_val and m_num and 1900 <= y_val <= 2100:
            try:
                return ParsedDate(date=datetime.date(y_val, m_num, day_val), raw=s, is_ambiguous=False)
            except ValueError:
                return None

    # 3. Month Day Year: "January 1, 2026", "Jan 1st, 2026"
    m_mdy = re.fullmatch(r"([a-z]+)\s+(\d{1,2})(?:st|nd|rd|th)?[,\s]+(\d{4})", s, re.IGNORECASE)
    if m_mdy:
        m_raw = m_mdy.group(1).lower()
        d_val = int(m_mdy.group(2))
        y_val = int(m_mdy.group(3))
        m_num = _MONTHS.get(m_raw)
        if m_num and 1900 <= y_val <= 2100:
            try:
                return ParsedDate(date=datetime.date(y_val, m_num, d_val), raw=s, is_ambiguous=False)
            except ValueError:
                return None

    # 4. Day Month Year: "1st January 2026", "1 Jan 2026", "1-Jan-2026"
    m_dmy = re.fullmatch(r"(\d{1,2})(?:st|nd|rd|th)?[\s-]+([a-z]+)[\s,-]+(\d{4})", s, re.IGNORECASE)
    if m_dmy:
        d_val = int(m_dmy.group(1))
        m_raw = m_dmy.group(2).lower()
        y_val = int(m_dmy.group(3))
        m_num = _MONTHS.get(m_raw)
        if m_num and 1900 <= y_val <= 2100:
            try:
                return ParsedDate(date=datetime.date(y_val, m_num, d_val), raw=s, is_ambiguous=False)
            except ValueError:
                return None

    # 5. Numeric: DD/MM/YYYY, MM/DD/YYYY, DD.MM.YYYY, DD-MM-YYYY
    m_num = re.fullmatch(r"(\d{1,2})[/.-](\d{1,2})[/.-](\d{2,4})", s)
    if m_num:
        p1, p2, yr = int(m_num.group(1)), int(m_num.group(2)), int(m_num.group(3))
        if yr < 100:
            yr += 2000 if yr < 50 else 1900
        if yr < 1900 or yr > 2100:
            return None

        is_ambiguous = p1 <= 12 and p2 <= 12 and p1 != p2
        d, m = (p1, p2) if date_format_order == "DMY" else (p2, p1)
        try:
            return ParsedDate(date=datetime.date(yr, m, d), raw=s, is_ambiguous=is_ambiguous)
        except ValueError:
            # Fall back to alternative ordering if primary is invalid (e.g. 13/05/2026 on MDY)
            try:
                d_alt, m_alt = (p2, p1) if date_format_order == "DMY" else (p1, p2)
                return ParsedDate(date=datetime.date(yr, m_alt, d_alt), raw=s, is_ambiguous=False)
            except ValueError:
                return None

    return None


def extract_date_occurrences(
    text_index: TextIndex,
    settings: ConsistencySettings,
) -> list[DateOccurrence]:
    """Scan all contract segments and extract date occurrences with detected roles."""
    occurrences: list[DateOccurrence] = []

    for seg in text_index.segments:
        sentences = split_sentences(seg.text)

        for sent in sentences:
            # Find all date matches
            found_spans: list[tuple[int, int, str]] = []

            for pat in _DATE_PATTERNS:
                for match in pat.finditer(sent):
                    span = match.span()
                    # Check overlap with already found spans
                    if any(s[0] <= span[0] and span[1] <= s[1] for s in found_spans):
                        continue
                    found_spans.append((span[0], span[1], match.group(0)))

            # Sort spans by position in sentence
            found_spans.sort(key=lambda s: s[0])

            prev_end = 0
            for start_idx, end_idx, raw_match in found_spans:
                p_date = parse_date(raw_match, settings.date_format_order)
                if p_date is None:
                    prev_end = end_idx
                    continue

                # Context window scoped between previous date end and this date start
                scoped_preceding = sent[prev_end:start_idx]
                full_window = sent[max(0, start_idx - 40) : min(len(sent), end_idx + 40)]

                # Find closest role phrase in preceding text
                role = "other"
                if _EFFECTIVE_DEF_RE.search(scoped_preceding):
                    role = "effective_def"
                else:
                    m_start = list(_START_ROLE_RE.finditer(scoped_preceding))
                    m_end = list(_END_ROLE_RE.finditer(scoped_preceding))

                    last_start = m_start[-1].end() if m_start else -1
                    last_end = m_end[-1].end() if m_end else -1

                    if last_end > last_start and last_end != -1:
                        role = "end"
                    elif last_start > last_end and last_start != -1:
                        role = "start"

                occurrences.append(
                    DateOccurrence(
                        parsed=p_date,
                        role=role,
                        clause_ref=seg.clause_ref,
                        page=seg.page,
                        context_snippet=full_window.strip(),
                        raw_match=raw_match,
                    )
                )
                prev_end = end_idx

    return occurrences


def detect_dates(
    doc_or_index: ParsedDocument | TextIndex,
    index_or_settings: TextIndex | ConsistencySettings,
    settings: ConsistencySettings | None = None,
) -> tuple[list[Finding], dict[str, int]]:
    """Detect date conflicts in contract text.

    Checks:
    - (a) date_order_conflict: end date earlier than start date (HIGH)
    - (b) effective_date_conflict: conflicting definitions of Effective Date (MEDIUM)
    - (c) term_length_conflict: stated term vs date span mismatch (MEDIUM)
    """
    if isinstance(doc_or_index, TextIndex):
        text_index = doc_or_index
        resolved_settings = index_or_settings if isinstance(index_or_settings, ConsistencySettings) else ConsistencySettings()
    else:
        text_index = index_or_settings  # type: ignore[assignment]
        resolved_settings = settings or ConsistencySettings()
    settings = resolved_settings
    findings: list[Finding] = []
    stats: dict[str, int] = {
        "dates_found": 0,
        "date_order_conflicts": 0,
        "effective_date_conflicts": 0,
        "term_conflicts": 0,
    }

    occurrences = extract_date_occurrences(text_index, settings)
    stats["dates_found"] = len(occurrences)

    # ---------------------------------------------------------------------------
    # Check (a): date_order_conflict (end date earlier than start date)
    # ---------------------------------------------------------------------------
    start_dates = [o for o in occurrences if o.role in ("start", "effective_def")]
    end_dates = [o for o in occurrences if o.role == "end"]

    for ed in end_dates:
        for sd in start_dates:
            if ed.parsed.date < sd.parsed.date:
                stats["date_order_conflicts"] += 1
                is_ambiguous = ed.parsed.is_ambiguous or sd.parsed.is_ambiguous
                sev = Severity.MEDIUM if is_ambiguous else Severity.HIGH

                amb_note = " (note: numeric date was ambiguous)" if is_ambiguous else ""
                evidence = (
                    f"Start date: '{sd.raw_match}' ({sd.parsed.date.isoformat()}) in '{sd.context_snippet}'; "
                    f"End date: '{ed.raw_match}' ({ed.parsed.date.isoformat()}) in '{ed.context_snippet}'"
                )[:MAX_EVIDENCE_CHARS]

                c_info = f" in clause {ed.clause_ref}" if ed.clause_ref else ""
                explanation = (
                    f"Termination/expiration date ({ed.parsed.date.isoformat()}) is earlier than "
                    f"the effective/commencement date ({sd.parsed.date.isoformat()}){c_info}{amb_note}."
                )

                findings.append(
                    Finding(
                        module=CONSISTENCY_MODULE,
                        type="date_order_conflict",
                        severity=sev,
                        page=ed.page,
                        clause_ref=ed.clause_ref,
                        evidence=evidence,
                        explanation=explanation,
                        details={
                            "rule_id": "CONSISTENCY_DATE_ORDER_CONFLICT",
                            "start_date": sd.parsed.date.isoformat(),
                            "end_date": ed.parsed.date.isoformat(),
                            "start_raw": sd.raw_match,
                            "end_raw": ed.raw_match,
                            "is_ambiguous": is_ambiguous,
                        },
                    )
                )
                break  # report first conflict per end date

    # ---------------------------------------------------------------------------
    # Check (b): effective_date_conflict (two conflicting definition dates)
    # ---------------------------------------------------------------------------
    eff_defs = [o for o in occurrences if o.role == "effective_def"]
    # Group by unique date values
    unique_eff_dates: dict[datetime.date, list[DateOccurrence]] = {}
    for ed in eff_defs:
        unique_eff_dates.setdefault(ed.parsed.date, []).append(ed)

    if len(unique_eff_dates) >= 2:
        date_keys = sorted(unique_eff_dates.keys())
        first_d = date_keys[0]
        second_d = date_keys[1]
        occ_1 = unique_eff_dates[first_d][0]
        occ_2 = unique_eff_dates[second_d][0]

        is_ambiguous = occ_1.parsed.is_ambiguous or occ_2.parsed.is_ambiguous
        sev = Severity.LOW if is_ambiguous else Severity.MEDIUM
        amb_note = " (note: numeric date was ambiguous)" if is_ambiguous else ""

        stats["effective_date_conflicts"] += 1
        evidence = (
            f"Effective Date definition 1: '{occ_1.raw_match}' ({first_d.isoformat()}); "
            f"Definition 2: '{occ_2.raw_match}' ({second_d.isoformat()})"
        )[:MAX_EVIDENCE_CHARS]

        c_info = f" in clause {occ_2.clause_ref}" if occ_2.clause_ref else ""
        explanation = (
            f"The Effective Date is assigned conflicting dates ({first_d.isoformat()} and {second_d.isoformat()})"
            f"{c_info}{amb_note}."
        )

        findings.append(
            Finding(
                module=CONSISTENCY_MODULE,
                type="effective_date_conflict",
                severity=sev,
                page=occ_2.page,
                clause_ref=occ_2.clause_ref,
                evidence=evidence,
                explanation=explanation,
                details={
                    "rule_id": "CONSISTENCY_EFFECTIVE_DATE_CONFLICT",
                    "date_1": first_d.isoformat(),
                    "date_2": second_d.isoformat(),
                    "is_ambiguous": is_ambiguous,
                },
            )
        )

    # ---------------------------------------------------------------------------
    # Check (c): term_length_conflict
    # Stated term vs date span when exactly 1 candidate exists for each role
    # ---------------------------------------------------------------------------
    unique_start = {sd.parsed.date for sd in start_dates}
    unique_end = {ed.parsed.date for ed in end_dates}

    term_candidates: list[tuple[ContractSegment, re.Match[str], int, str, int]] = []
    _NON_TERM_PHRASES = (
        "survive",
        "after termination",
        "after its termination",
        "following termination",
        "upon termination",
        "prior written notice",
        "notice of",
        "notice period",
        "cure period",
        "cure within",
        "warranty period",
        "defect liability",
        "probation",
    )

    for seg in text_index.segments:
        sentences = split_sentences(seg.text)
        for sent in sentences:
            sent_lower = sent.lower()
            if any(phrase in sent_lower for phrase in _NON_TERM_PHRASES):
                continue
            for m_term in _TERM_PERIOD_RE.finditer(sent):
                qty_str = m_term.group("qty")
                unit_str = m_term.group("unit").lower()

                # Parse quantity (numeric or words)
                qty_val = None
                if qty_str.isdigit():
                    qty_val = int(qty_str)
                else:
                    pw = words_to_decimal(qty_str)
                    if pw:
                        qty_val = int(pw.value)

                if qty_val is not None:
                    if "year" in unit_str:
                        stated_days = qty_val * 365
                    elif "month" in unit_str:
                        stated_days = round(qty_val * 30.4375)
                    elif "week" in unit_str:
                        stated_days = qty_val * 7
                    else:
                        stated_days = qty_val
                    term_candidates.append((seg, m_term, qty_val, unit_str, stated_days))

    # Only run (c) when exactly one candidate exists for each role; otherwise skip silently
    if len(unique_start) == 1 and len(unique_end) == 1 and len(term_candidates) == 1:
        s_date = next(iter(unique_start))
        e_date = next(iter(unique_end))
        span_days = (e_date - s_date).days

        if span_days > 0:
            seg, m_term, qty_val, unit_str, stated_days = term_candidates[0]
            diff = abs(span_days - stated_days)
            if diff > settings.term_tolerance_days:
                stats["term_conflicts"] += 1
                evidence = (
                    f"Stated term: '{m_term.group(0).strip()}'; "
                    f"Start: {s_date.isoformat()}, End: {e_date.isoformat()} (span: {span_days} days)"
                )[:MAX_EVIDENCE_CHARS]
                c_info = f" in clause {seg.clause_ref}" if seg.clause_ref else ""
                explanation = (
                    f"Stated contract term ({qty_val} {unit_str} ≈ {stated_days} days) differs "
                    f"from actual date span ({span_days} days between {s_date.isoformat()} and {e_date.isoformat()}) "
                    f"by {diff} days{c_info}."
                )
                findings.append(
                    Finding(
                        module=CONSISTENCY_MODULE,
                        type="term_length_conflict",
                        severity=Severity.MEDIUM,
                        page=seg.page,
                        clause_ref=seg.clause_ref,
                        evidence=evidence,
                        explanation=explanation,
                        details={
                            "rule_id": "CONSISTENCY_TERM_LENGTH_CONFLICT",
                            "stated_days": stated_days,
                            "actual_days": span_days,
                            "difference_days": diff,
                            "tolerance_days": settings.term_tolerance_days,
                        },
                    )
                )

    return findings, stats
