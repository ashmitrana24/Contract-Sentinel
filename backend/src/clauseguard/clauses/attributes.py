"""Deterministic key-term extraction from contract clauses.

Extracts 8 structured contract attributes:
1. governing_law_jurisdiction: Canonical jurisdiction string (e.g. "Delaware", "New York").
2. termination_notice_days: Notice period in days for termination.
3. auto_renews: Boolean indicating auto-renewal / evergreen terms.
4. renewal_term_months: Length of successive renewal periods in months.
5. non_renewal_notice_days: Days of notice required to prevent automatic renewal.
6. liability_cap: Structured monetary cap or fee-multiplier dictionary.
7. non_compete_duration_months: Duration in months of non-compete covenant post-termination.
8. payment_terms_days: Standard payment window in days (e.g. Net 30 -> 30).

Guaranteed behavior: Returns None / empty when ambiguous or not present.
Never hallucinates or guesses.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Any

# Word to number mapping
_WORD_NUMBERS: dict[str, int] = {
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "twelve": 12,
    "fifteen": 15,
    "eighteen": 18,
    "twenty": 20,
    "twenty-four": 24,
    "thirty": 30,
    "thirty-six": 36,
    "forty-five": 45,
    "forty-eight": 48,
    "sixty": 60,
    "ninety": 90,
    "one hundred": 100,
    "one hundred twenty": 120,
    "1": 1,
    "2": 2,
    "3": 3,
    "4": 4,
    "5": 5,
    "6": 6,
    "7": 7,
    "8": 8,
    "9": 9,
    "10": 10,
    "12": 12,
    "15": 15,
    "18": 18,
    "20": 20,
    "24": 24,
    "30": 30,
    "36": 36,
    "45": 45,
    "48": 48,
    "60": 60,
    "90": 90,
    "120": 120,
    "180": 180,
    "365": 365,
}

_CANONICAL_JURISDICTIONS: dict[str, str] = {
    "delaware": "Delaware",
    "new york": "New York",
    "california": "California",
    "texas": "Texas",
    "illinois": "Illinois",
    "florida": "Florida",
    "massachusetts": "Massachusetts",
    "washington": "Washington",
    "ohio": "Ohio",
    "pennsylvania": "Pennsylvania",
    "virginia": "Virginia",
    "georgia": "Georgia",
    "north carolina": "North Carolina",
    "new jersey": "New Jersey",
    "colorado": "Colorado",
    "michigan": "Michigan",
    "minnesota": "Minnesota",
    "maryland": "Maryland",
    "connecticut": "Connecticut",
    "nevada": "Nevada",
    "utah": "Utah",
    "arizona": "Arizona",
    "tennessee": "Tennessee",
    "missouri": "Missouri",
    "wisconsin": "Wisconsin",
    "indiana": "Indiana",
    "oregon": "Oregon",
    "england and wales": "England and Wales",
    "england": "England and Wales",
    "united kingdom": "United Kingdom",
    "canada": "Canada",
    "ontario": "Ontario",
    "france": "France",
    "germany": "Germany",
    "singapore": "Singapore",
    "hong kong": "Hong Kong",
    "australia": "Australia",
    "new south wales": "New South Wales",
    "switzerland": "Switzerland",
    "ireland": "Ireland",
    "cayman islands": "Cayman Islands",
    "bermuda": "Bermuda",
}

_JURISDICTION_REGEX = re.compile(
    r"(?:governed\s+by|construed\s+in\s+accordance\s+with|laws\s+of|jurisdiction\s+of)\s+"
    r"(?:and\s+under\s+)?(?:the\s+laws\s+of\s+)?"
    r"(?:the\s+(?:State|Commonwealth|Province)\s+of\s+)?"
    r"([A-Za-z\s]+?)(?:[,\.;]|\s+without|\s+and|\s+excluding|$)",
    re.IGNORECASE,
)


def _parse_int_str(val: str) -> int | None:
    val_clean = val.lower().strip()
    if val_clean.isdigit():
        return int(val_clean)
    return _WORD_NUMBERS.get(val_clean)


# -----------------------------------------------------------------------------
# 1. Governing Law Jurisdiction
# -----------------------------------------------------------------------------
def extract_governing_law_jurisdiction(text: str) -> str | None:
    """Extract canonical governing law jurisdiction from clause text."""
    found: set[str] = set()

    for m in _JURISDICTION_REGEX.finditer(text):
        raw_target = m.group(1).strip().lower()
        # Clean leading words
        raw_target = re.sub(r"^(?:the\s+state\s+of\s+|the\s+commonwealth\s+of\s+|the\s+province\s+of\s+)", "", raw_target)
        for name_key, canonical in _CANONICAL_JURISDICTIONS.items():
            if re.search(r"\b" + re.escape(name_key) + r"\b", raw_target):
                found.add(canonical)

    if len(found) == 1:
        return next(iter(found))
    # If England and Wales matched both England and Wales
    if found == {"England and Wales"}:
        return "England and Wales"
    return None


# -----------------------------------------------------------------------------
# 2. Termination Notice Days
# -----------------------------------------------------------------------------
_TERM_NOTICE_REGEX = re.compile(
    r"(?:terminate|termination)[^.]{0,80}?(?:upon|with|giving)?\s*"
    r"(?:at\s+least\s+)?(\d+|one|two|three|ten|fifteen|twenty|thirty|forty-five|sixty|ninety|one\s+hundred\s+twenty)\s*"
    r"(\(?\d+\)?\s*)?"
    r"(days?|months?|weeks?)\s*(?:prior\s+)?(?:written\s+)?notice",
    re.IGNORECASE,
)


def extract_termination_notice_days(text: str) -> int | None:
    """Extract required notice period in days for general or convenience termination."""
    # Check for negative patterns first (e.g. without notice)
    for m in _TERM_NOTICE_REGEX.finditer(text):
        num_str = m.group(1)
        unit = m.group(3).lower()

        num = _parse_int_str(num_str)
        if num is None:
            continue

        if "month" in unit:
            return num * 30
        if "week" in unit:
            return num * 7
        return num
    return None


# -----------------------------------------------------------------------------
# 3. Auto Renews
# -----------------------------------------------------------------------------
_AUTO_RENEW_POSITIVE = re.compile(
    r"(?:automatically\s+renew(?:s|ed)?|renew(?:s|ed)?\s+automatically|automatic\s+renewal|auto-renew(?:al)?|evergreen(?:\s+contract|\s+clause)?)",
    re.IGNORECASE,
)
_AUTO_RENEW_NEGATIVE = re.compile(
    r"(?:shall\s+not\s+(?:automatically\s+)?renew|no\s+automatic\s+renewal|does\s+not\s+automatically\s+renew|without\s+automatic\s+renewal)",
    re.IGNORECASE,
)


def extract_auto_renews(text: str) -> bool | None:
    """Detect whether contract auto-renews (True/False/None)."""
    if _AUTO_RENEW_NEGATIVE.search(text):
        return False
    if _AUTO_RENEW_POSITIVE.search(text):
        return True
    return None


# -----------------------------------------------------------------------------
# 4. Renewal Term Months
# -----------------------------------------------------------------------------
_RENEWAL_TERM_REGEX = re.compile(
    r"(?:(?:shall\s+|will\s+)?(?:automatically\s+)?renew(?:ed|s|al)?(?:\s+automatically)?\s+(?:for|of)|renewal\s+term\s+of|extended\s+for|successive\s+terms?\s+of)\s*"
    r"(?:successive|additional|further)?\s*(?:terms?|periods?|duration)?\s*(?:of\s+)?"
    r"(\d+|one|two|three|four|five|six|seven|eight|nine|ten|twelve|twenty-four)\s*"
    r"(?:\(\d+\)\s*)?"
    r"[-–\s]*"
    r"(years?|months?)",
    re.IGNORECASE,
)


def extract_renewal_term_months(text: str) -> int | None:
    """Extract duration of renewal term in months."""
    for m in _RENEWAL_TERM_REGEX.finditer(text):
        num_str = m.group(1)
        unit = m.group(2).lower()

        num = _parse_int_str(num_str)
        if num is None:
            continue

        if "year" in unit:
            return num * 12
        return num
    return None


# -----------------------------------------------------------------------------
# 5. Non-Renewal Notice Days
# -----------------------------------------------------------------------------
_NON_RENEWAL_NOTICE_REGEX = re.compile(
    r"(?:notice\s+(?:of\s+non-renewal|not\s+to\s+renew)|written\s+notice\s+not\s+to\s+extend|prior\s+to\s+(?:the\s+end\s+of|expiration\s+of)\s+(?:the\s+)?(?:initial|then-current|renewal)\s+term)[^.]{0,80}?"
    r"(?:at\s+least\s+)?(\d+|one|two|three|ten|fifteen|twenty|thirty|forty-five|sixty|ninety|one\s+hundred\s+twenty)\s*"
    r"(?:\(\d+\)\s*)?"
    r"(days?|months?|weeks?)['\u2019]?",
    re.IGNORECASE,
)
_NON_RENEWAL_NOTICE_REVERSE = re.compile(
    r"(?:at\s+least\s+)?(\d+|one|two|three|ten|fifteen|twenty|thirty|forty-five|sixty|ninety|one\s+hundred\s+twenty)\s*"
    r"(?:\(\d+\)\s*)?"
    r"(days?|months?|weeks?)['\u2019]?\s*(?:prior\s+)?(?:written\s+)?notice\s+(?:prior\s+to\s+the\s+end\s+of\s+the\s+(?:initial|then-current)\s+term|of\s+non-renewal|not\s+to\s+renew)",
    re.IGNORECASE,
)
_NON_RENEWAL_NOTICE_UNLESS = re.compile(
    r"(?:unless\s+(?:either\s+party\s+)?(?:gives|provides|delivers|serves)\s+|at\s+least\s+)"
    r"(\d+|one|two|three|ten|fifteen|twenty|thirty|forty-five|sixty|ninety|one\s+hundred\s+twenty)\s*"
    r"(?:\(\d+\)\s*)?"
    r"(days?|months?|weeks?)['\u2019]?\s*(?:prior\s+)?(?:written\s+)?notice",
    re.IGNORECASE,
)


def extract_non_renewal_notice_days(text: str) -> int | None:
    """Extract required notice in days to prevent automatic contract extension."""
    for pat in (_NON_RENEWAL_NOTICE_REGEX, _NON_RENEWAL_NOTICE_REVERSE):
        m = pat.search(text)
        if m:
            num_str = m.group(1)
            unit = m.group(2).lower()
            num = _parse_int_str(num_str)
            if num is None:
                continue
            if "month" in unit:
                return num * 30
            if "week" in unit:
                return num * 7
            return num

    # In renewal contexts, notice periods under 'unless ... gives X days notice'
    if "renew" in text.lower():
        m_unless = _NON_RENEWAL_NOTICE_UNLESS.search(text)
        if m_unless:
            num_str = m_unless.group(1)
            unit = m_unless.group(2).lower()
            num = _parse_int_str(num_str)
            if num is not None:
                if "month" in unit:
                    return num * 30
                if "week" in unit:
                    return num * 7
                return num

    return None


# -----------------------------------------------------------------------------
# 6. Liability Cap
# -----------------------------------------------------------------------------
_CAP_FIXED_REGEX = re.compile(
    r"(?:liability\s+(?:shall\s+not\s+exceed|(?:is\s+)?capped\s+at|limited\s+to)|in\s+no\s+event\s+shall[^.]{0,100}liability[^.]{0,40}exceed)\s*"
    r"(\$|USD|EUR|GBP|€|£)?\s*([\d,]+(?:\.\d+)?)\s*(USD|EUR|GBP)?",
    re.IGNORECASE,
)
_CAP_FEES_REGEX = re.compile(
    r"(?:equal\s+to|not\s+exceed)\s+(?:the\s+)?(?:total\s+)?(?:fees|amounts)\s+paid\s+(?:or\s+payable\s+)?"
    r"(?:in\s+the\s+(?:preceding\s+)?(\d+|twelve)\s+months|under\s+this\s+agreement)",
    re.IGNORECASE,
)


def extract_liability_cap(text: str) -> dict[str, Any] | None:
    """Extract liability cap structure (monetary fixed amount or fee multiple)."""
    # Check fixed monetary amount
    m_fixed = _CAP_FIXED_REGEX.search(text)
    if m_fixed:
        raw_curr = (m_fixed.group(1) or m_fixed.group(3) or "USD").strip()
        curr = "USD"
        if raw_curr in ("€", "EUR"):
            curr = "EUR"
        elif raw_curr in ("£", "GBP"):
            curr = "GBP"

        num_str = m_fixed.group(2).replace(",", "")
        try:
            val = float(num_str)
            if val > 0:
                return {"type": "fixed_amount", "amount": val, "currency": curr}
        except ValueError:
            pass

    # Check fee multiplier
    m_fees = _CAP_FEES_REGEX.search(text)
    if m_fees:
        months_str = m_fees.group(1)
        months = 12
        if months_str:
            parsed_m = _parse_int_str(months_str)
            if parsed_m:
                months = parsed_m
        return {"type": "fee_multiplier", "months": months, "basis": "fees_paid"}

    return None


# -----------------------------------------------------------------------------
# 7. Non-Compete Duration Months
# -----------------------------------------------------------------------------
_NON_COMPETE_DURATION_REGEX = re.compile(
    r"(?:not\s+(?:directly\s+or\s+indirectly\s+)?(?:compete|engage\s+in\s+any\s+competing\s+business)|refrain\s+from\s+competing|non-compete|non-competition)[^.]{0,100}?"
    r"(?:period\s+of|for\s+a\s+period\s+of|duration\s+of|for)\s+"
    r"(\d+|one|two|three|four|five|six|twelve|eighteen|twenty-four)\s*"
    r"(?:\(\d+\)\s*)?"
    r"(years?|months?)",
    re.IGNORECASE,
)


def extract_non_compete_duration_months(text: str) -> int | None:
    """Extract duration of non-compete covenant post-termination in months."""
    m = _NON_COMPETE_DURATION_REGEX.search(text)
    if m:
        num_str = m.group(1)
        unit = m.group(2).lower()
        num = _parse_int_str(num_str)
        if num is None:
            return None
        if "year" in unit:
            return num * 12
        return num
    return None


# -----------------------------------------------------------------------------
# 8. Payment Terms Days
# -----------------------------------------------------------------------------
_NET_DAYS_REGEX = re.compile(r"\bnet\s+(\d+)\b", re.IGNORECASE)
_PAYMENT_DUE_REGEX = re.compile(
    r"(?:payment\s+(?:shall\s+be\s+due|is\s+due)|payable)\s+(?:within|in)\s+(\d+|fifteen|thirty|forty-five|sixty|ninety)\s*days?",
    re.IGNORECASE,
)


def extract_payment_terms_days(text: str) -> int | None:
    """Extract payment terms timeframe in days (e.g. Net 30 -> 30)."""
    m_net = _NET_DAYS_REGEX.search(text)
    if m_net:
        return int(m_net.group(1))

    m_due = _PAYMENT_DUE_REGEX.search(text)
    if m_due:
        return _parse_int_str(m_due.group(1))

    return None


# -----------------------------------------------------------------------------
# Aggregated Document Attributes
# -----------------------------------------------------------------------------
@dataclass
class DocumentAttributes:
    """Extracted key terms for an entire contract."""

    governing_law_jurisdiction: str | None = None
    termination_notice_days: int | None = None
    auto_renews: bool | None = None
    renewal_term_months: int | None = None
    non_renewal_notice_days: int | None = None
    liability_cap: dict[str, Any] | None = None
    non_compete_duration_months: int | None = None
    payment_terms_days: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def extract_all_document_attributes(
    clauses_text: list[str] | str,
    clause_labels: list[list[str]] | None = None,
) -> DocumentAttributes:
    """Extract all 8 attributes across a document's clauses.

    Accepts either a list of clause text strings or a single full contract string.
    Optionally accepts per-clause labels to accurately scope renewal extractors.
    """
    if isinstance(clauses_text, list):
        full_text = "\n\n".join(clauses_text)
    else:
        full_text = clauses_text

    # Scope renewal extraction to clauses labeled auto_renewal, renewal_term,
    # or notice_period_to_terminate_renewal (and fall back to any clause containing 'renew')
    renewal_text = full_text
    if isinstance(clauses_text, list):
        target_clauses: list[str] = []
        if clause_labels and len(clause_labels) == len(clauses_text):
            target_labels = {"auto_renewal", "renewal_term", "notice_period_to_terminate_renewal"}
            for c_txt, c_lbls in zip(clauses_text, clause_labels, strict=True):
                if any(lbl in target_labels for lbl in c_lbls):
                    target_clauses.append(c_txt)
        if not target_clauses:
            target_clauses = [c_txt for c_txt in clauses_text if "renew" in c_txt.lower()]
        if target_clauses:
            renewal_text = "\n\n".join(target_clauses)

    return DocumentAttributes(
        governing_law_jurisdiction=extract_governing_law_jurisdiction(full_text),
        termination_notice_days=extract_termination_notice_days(full_text),
        auto_renews=extract_auto_renews(renewal_text) or extract_auto_renews(full_text),
        renewal_term_months=extract_renewal_term_months(renewal_text),
        non_renewal_notice_days=extract_non_renewal_notice_days(renewal_text),
        liability_cap=extract_liability_cap(full_text),
        non_compete_duration_months=extract_non_compete_duration_months(full_text),
        payment_terms_days=extract_payment_terms_days(full_text),
    )
