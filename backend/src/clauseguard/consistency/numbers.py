"""Deterministic number-word and figure parsers for contract consistency checks.

Parses English number words (units, teens, tens, hundreds, thousands, lakhs,
crores, millions, billions, optional "and", trailing "only") into exact Decimal values.
Parses numeric figures in Indian (10,00,000) and Western (1,000,000) groupings,
decimals, percentages, currency markers, and figure-plus-unit forms ("10.5 lakh", "$1.5 million").
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

# Base words
_UNITS: dict[str, int] = {
    "zero": 0,
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
    "eleven": 11,
    "twelve": 12,
    "thirteen": 13,
    "fourteen": 14,
    "fifteen": 15,
    "sixteen": 16,
    "seventeen": 17,
    "eighteen": 18,
    "nineteen": 19,
}

_TENS: dict[str, int] = {
    "twenty": 20,
    "thirty": 30,
    "forty": 40,
    "fifty": 50,
    "sixty": 60,
    "seventy": 70,
    "eighty": 80,
    "ninety": 90,
}

# Major scales
_SCALES: dict[str, int] = {
    "thousand": 1_000,
    "thousands": 1_000,
    "lakh": 100_000,
    "lakhs": 100_000,
    "lac": 100_000,
    "lacs": 100_000,
    "million": 1_000_000,
    "millions": 1_000_000,
    "crore": 10_000_000,
    "crores": 10_000_000,
    "billion": 1_000_000_000,
    "billions": 1_000_000_000,
}

_FIGURE_UNITS: dict[str, Decimal] = {
    "hundred": Decimal(100),
    "hundreds": Decimal(100),
    "thousand": Decimal(1_000),
    "thousands": Decimal(1_000),
    "lakh": Decimal(100_000),
    "lakhs": Decimal(100_000),
    "lac": Decimal(100_000),
    "lacs": Decimal(100_000),
    "million": Decimal(1_000_000),
    "millions": Decimal(1_000_000),
    "crore": Decimal(10_000_000),
    "crores": Decimal(10_000_000),
    "billion": Decimal(1_000_000_000),
    "billions": Decimal(1_000_000_000),
}

_CURRENCIES: dict[str, str] = {
    "rupees": "INR",
    "rupee": "INR",
    "rs.": "INR",
    "rs": "INR",
    "inr": "INR",
    "₹": "INR",
    "usd": "USD",
    "us$": "USD",
    "$": "USD",
    "dollars": "USD",
    "dollar": "USD",
    "eur": "EUR",
    "€": "EUR",
    "euros": "EUR",
    "euro": "EUR",
    "gbp": "GBP",
    "£": "GBP",
    "pounds": "GBP",
    "pound": "GBP",
}

_IGNORABLE_TOKENS = {
    "and",
    "only",
    "cents",
    "cents.",
    "paise",
    "paisa",
}


@dataclass(frozen=True)
class ParsedNumber:
    """Structured representation of a parsed number value."""

    value: Decimal
    raw: str
    currency: str | None = None
    is_percentage: bool = False
    is_currency: bool = False

    def is_compatible_kind(self, other: ParsedNumber) -> bool:
        """Check if both numbers represent compatible entities (both currency, both %, or both bare)."""
        if self.is_percentage != other.is_percentage:
            return False
        if self.is_currency and other.is_currency:
            if self.currency and other.currency and self.currency != other.currency:
                return False
        return True


def _clean_word_tokens(raw: str) -> tuple[list[str], str | None, bool]:
    """Clean a word string into tokens and extract currency / percent indicators."""
    text = raw.lower().strip()
    currency: str | None = None
    is_percent = False

    # Check for percentage keywords
    if re.search(r"\b(percent|per cent|percentage)\b", text):
        is_percent = True
        text = re.sub(r"\b(percent|per cent|percentage)\b", " ", text)

    # Check for currency markers
    for sym, code in sorted(_CURRENCIES.items(), key=lambda x: -len(x[0])):
        if re.search(rf"\b{re.escape(sym)}\b", text) or (sym in ("$", "₹", "€", "£") and sym in text):
            currency = code
            text = text.replace(sym, " ")
            break

    # Replace hyphens with spaces to split "twenty-five" -> "twenty", "five"
    text = text.replace("-", " ")
    text = re.sub(r"[^\w\s]", " ", text)

    tokens = [t for t in text.split() if t]
    filtered_tokens = [t for t in tokens if t not in _IGNORABLE_TOKENS]
    return filtered_tokens, currency, is_percent


def words_to_decimal(words_str: str) -> ParsedNumber | None:
    """Parse an English words representation of a number into a ParsedNumber.

    Handles units, teens, tens, hundreds, thousands, lakhs, crores, millions,
    billions, optional 'and', and trailing 'only'. Returns None on invalid words.
    """
    if not words_str or not isinstance(words_str, str):
        return None

    tokens, currency, is_percent = _clean_word_tokens(words_str)
    if not tokens:
        return None

    # Handle decimal point words: e.g. "ten point five"
    if "point" in tokens:
        point_idx = tokens.index("point")
        int_tokens = tokens[:point_idx]
        frac_tokens = tokens[point_idx + 1 :]

        int_part = Decimal(0)
        if int_tokens:
            int_res = words_to_decimal(" ".join(int_tokens))
            if int_res is None:
                return None
            int_part = int_res.value

        frac_str = ""
        for ft in frac_tokens:
            if ft in _UNITS:
                frac_str += str(_UNITS[ft])
            elif ft in _TENS:
                frac_str += str(_TENS[ft])
            else:
                return None
        if not frac_str:
            return None
        try:
            val = int_part + Decimal(f"0.{frac_str}")
            return ParsedNumber(
                value=val,
                raw=words_str.strip(),
                currency=currency,
                is_percentage=is_percent,
                is_currency=currency is not None,
            )
        except InvalidOperation:
            return None

    # Validate all tokens are numbers or scale words
    for t in tokens:
        if t not in _UNITS and t not in _TENS and t != "hundred" and t not in _SCALES:
            return None

    # Evaluate hierarchy: scale words multiply current group
    total = Decimal(0)
    current_group = Decimal(0)

    for t in tokens:
        if t in _UNITS:
            current_group += Decimal(_UNITS[t])
        elif t in _TENS:
            current_group += Decimal(_TENS[t])
        elif t == "hundred":
            if current_group == Decimal(0):
                current_group = Decimal(1)
            current_group *= Decimal(100)
        elif t in _SCALES:
            scale_val = Decimal(_SCALES[t])
            if current_group == Decimal(0):
                current_group = Decimal(1)
            total += current_group * scale_val
            current_group = Decimal(0)

    total += current_group

    return ParsedNumber(
        value=total,
        raw=words_str.strip(),
        currency=currency,
        is_percentage=is_percent,
        is_currency=currency is not None,
    )


def parse_figure(fig_str: str) -> ParsedNumber | None:
    """Parse a numeric figure string into a ParsedNumber.

    Supports:
    - Indian grouping: 'Rs. 10,00,000', '1,99,00,000'
    - Western grouping: '$1,000,000', '1,500,000'
    - Decimal quantities: '10.5', '1,000.50'
    - Figure plus unit words: 'Rs. 10.5 lakh', '$1.5 million', '2.5 crore'
    - Percentages: '5%', '5.5 percent'
    - Bare quantities: '30', '5'
    """
    if not fig_str or not isinstance(fig_str, str):
        return None

    cleaned = fig_str.strip()
    if not cleaned:
        return None

    currency: str | None = None
    is_percent = False

    # Check percentage at end
    if cleaned.endswith("%"):
        is_percent = True
        cleaned = cleaned[:-1].strip()
    elif re.search(r"\bpercent\b", cleaned, re.IGNORECASE):
        is_percent = True
        cleaned = re.sub(r"\bpercent\b", "", cleaned, flags=re.IGNORECASE).strip()

    # Check currency markers at start or end
    for sym, code in sorted(_CURRENCIES.items(), key=lambda x: -len(x[0])):
        lower = cleaned.lower()
        if lower.startswith(sym):
            currency = code
            cleaned = cleaned[len(sym) :].strip()
            break
        elif lower.endswith(sym):
            currency = code
            cleaned = cleaned[: -len(sym)].strip()
            break

    # Check for unit suffix e.g. "10.5 lakh", "1.5 million"
    parts = cleaned.split()
    multiplier = Decimal(1)

    if len(parts) == 2:
        unit_word = parts[1].lower()
        if unit_word in _FIGURE_UNITS:
            multiplier = _FIGURE_UNITS[unit_word]
            cleaned = parts[0]
        else:
            return None
    elif len(parts) > 2:
        return None

    # Remove standard digit separators (commas and spaces)
    num_clean = cleaned.replace(",", "").replace(" ", "").strip()
    if not num_clean:
        return None

    # Validate that remainder is purely numeric (with optional decimal dot)
    if not re.fullmatch(r"\d+(?:\.\d+)?", num_clean):
        return None

    try:
        val = Decimal(num_clean) * multiplier
        return ParsedNumber(
            value=val,
            raw=fig_str.strip(),
            currency=currency,
            is_percentage=is_percent,
            is_currency=currency is not None,
        )
    except (InvalidOperation, ValueError):
        return None
