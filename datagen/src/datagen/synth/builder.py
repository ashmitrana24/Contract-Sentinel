"""Synthetic contract builder.

Generates Contract models from templates using a seeded RNG.
All randomness goes through the supplied random.Random instance
for full reproducibility.
"""

from __future__ import annotations

import logging
import random
from typing import Any

from num2words import num2words

from datagen.models import (
    Clause,
    Contract,
    KeyFact,
    KeyFactKind,
    MonetaryAmount,
    Party,
)
from datagen.synth.templates import (
    CITIES,
    COMMON_CLAUSES,
    COMPANY_PREFIXES,
    COMPANY_SUFFIXES,
    COMPANY_TYPES,
    CONTRACT_TYPES,
    GOVERNING_LAWS,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Monetary amount helpers
# ---------------------------------------------------------------------------


def _make_amount(
    rng: random.Random,
    *,
    min_lakh: int = 1,
    max_lakh: int = 100,
) -> MonetaryAmount:
    """Generate a random INR amount with both figure and words forms."""
    # Pick a round lakh amount
    lakh_val = rng.randint(min_lakh, max_lakh)
    rupees = lakh_val * 100_000

    # Format figure with Indian comma style: e.g. 10,00,000
    figure = _indian_format(rupees)
    words = _amount_to_words_indian(rupees)
    return MonetaryAmount(
        figure=f"Rs. {figure}",
        words=words,
        currency_symbol="Rs.",
    )


def _indian_format(n: int) -> str:
    """Format integer with Indian numbering: 1,00,000 style."""
    s = str(n)
    if len(s) <= 3:
        return s
    # last 3 digits always grouped together, then groups of 2
    last3 = s[-3:]
    rest = s[:-3]
    groups = []
    while len(rest) > 2:
        groups.append(rest[-2:])
        rest = rest[:-2]
    if rest:
        groups.append(rest)
    groups.reverse()
    return ",".join(groups) + "," + last3


def _amount_to_words_indian(amount: int) -> str:
    """Convert an integer rupee amount to Indian words form."""
    # Use num2words for the base conversion
    try:
        words = num2words(amount, lang="en_IN")
    except Exception:
        words = num2words(amount, lang="en")
    # Capitalise first letter and add suffix
    words = words.strip().capitalize()
    if not words.endswith("."):
        words += " Only"
    return f"Rupees {words}"


# ---------------------------------------------------------------------------
# Date helpers
# ---------------------------------------------------------------------------


def _make_date(rng: random.Random, year_min: int = 2022, year_max: int = 2025) -> str:
    """Return a random ISO date string."""
    year = rng.randint(year_min, year_max)
    month = rng.randint(1, 12)
    day = rng.randint(1, 28)
    return f"{year:04d}-{month:02d}-{day:02d}"


def _add_years(date_str: str, years: int) -> str:
    """Add *years* to an ISO date string."""
    y, m, d = (int(x) for x in date_str.split("-"))
    return f"{y + years:04d}-{m:02d}-{d:02d}"


# ---------------------------------------------------------------------------
# Party helpers
# ---------------------------------------------------------------------------


def _make_company_name(rng: random.Random, used: set[str]) -> str:
    """Generate a unique company name."""
    for _ in range(100):
        name = (
            f"{rng.choice(COMPANY_PREFIXES)} "
            f"{rng.choice(COMPANY_SUFFIXES)} "
            f"{rng.choice(COMPANY_TYPES)}"
        )
        if name not in used:
            used.add(name)
            return name
    # Fallback with random suffix
    name = f"Corp_{rng.randint(1000, 9999)} Ltd."
    used.add(name)
    return name


def _make_aliases(name: str, rng: random.Random) -> list[str]:
    """Create plausible short-form aliases for a company name."""
    # Take the first word and remove the corporate type suffix
    parts = name.split()
    aliases: list[str] = []
    if len(parts) >= 2:
        aliases.append(parts[0])  # "Apex"
    # Abbreviation: e.g. "A.T." from "Apex Technologies"
    initials = "".join(p[0] for p in parts if p[0].isupper() and len(p) > 2)
    if len(initials) >= 2:
        aliases.append(initials)
    return aliases


# ---------------------------------------------------------------------------
# Clause ID helpers
# ---------------------------------------------------------------------------


def _make_clause_id(section: int, subsection: int | None = None) -> str:
    if subsection is None:
        return str(section)
    return f"{section}.{subsection}"


# ---------------------------------------------------------------------------
# Cross-reference injection
# ---------------------------------------------------------------------------


def _inject_xrefs(
    text: str,
    clause_ids: list[str],
    ctx: dict[str, Any],
    rng: random.Random,
) -> tuple[str, list[str]]:
    """Replace {xref_*} placeholders in *text* with real clause IDs.

    Returns (filled_text, list_of_xref_targets).
    """
    xrefs: list[str] = []
    import re

    def _replacer(m: re.Match) -> str:  # type: ignore[type-arg]
        if clause_ids:
            cid = rng.choice(clause_ids)
            xrefs.append(cid)
            return f"Clause {cid}"
        return "Clause 1"

    filled = re.sub(r"\{xref_[^}]+\}", _replacer, text)
    return filled, xrefs


# ---------------------------------------------------------------------------
# Main builder
# ---------------------------------------------------------------------------


def build_synthetic_contract(
    contract_id: str,
    rng: random.Random,
    used_names: set[str] | None = None,
) -> Contract:
    """Build one synthetic Contract model from templates.

    Parameters
    ----------
    contract_id:
        Unique identifier for this contract.
    rng:
        Seeded random.Random instance (caller controls seed).
    used_names:
        Set of already-used company names to avoid collisions.

    Returns
    -------
    Contract
        Fully populated Contract model with key facts.
    """
    if used_names is None:
        used_names = set()

    # Pick contract type
    ctype_key = rng.choice(list(CONTRACT_TYPES.keys()))
    ctype = CONTRACT_TYPES[ctype_key]

    # Generate parties
    name_a = _make_company_name(rng, used_names)
    name_b = _make_company_name(rng, used_names)
    party_a = Party(
        name=name_a,
        aliases=_make_aliases(name_a, rng),
        role=ctype["party_a_role"],
    )
    party_b = Party(
        name=name_b,
        aliases=_make_aliases(name_b, rng),
        role=ctype["party_b_role"],
    )

    # Generate dates
    eff_date = _make_date(rng, 2022, 2024)
    term_date = _add_years(eff_date, rng.randint(1, 5))

    # Monetary amounts (primary + secondary)
    amount_primary = _make_amount(rng, min_lakh=1, max_lakh=200)
    _ = _make_amount(rng, min_lakh=5, max_lakh=500)

    # City, law, notice
    city = rng.choice(CITIES)
    law = rng.choice(GOVERNING_LAWS)
    notice = rng.choice([15, 30, 60, 90])

    # Select clauses
    n_clauses = rng.randint(ctype["min_clauses"], ctype["max_clauses"])
    selected = rng.sample(COMMON_CLAUSES, min(n_clauses, len(COMMON_CLAUSES)))
    if len(selected) < n_clauses:
        # If we need more clauses than available unique ones, allow repeats with new IDs
        extras = rng.choices(COMMON_CLAUSES, k=n_clauses - len(selected))
        selected = selected + extras

    # Build context dict for format_map
    ctx: dict[str, Any] = {
        "party_a": name_a,
        "party_b": name_b,
        "eff_date": eff_date,
        "term_date": term_date,
        "amount": str(amount_primary),
        "notice": str(notice),
        "city": city,
        "law": law,
        "contract_type": ctype_key.replace("_", " "),
    }

    # First pass: assign IDs so xrefs can reference them
    clauses: list[Clause] = []
    key_facts: list[KeyFact] = []
    clause_ids_so_far: list[str] = []

    for i, (heading_tpl, body_tpl) in enumerate(selected, start=1):
        cid = _make_clause_id(i)
        clause_ids_so_far.append(cid)

        # Fill xref placeholders
        body_filled, xref_targets = _inject_xrefs(body_tpl, clause_ids_so_far[:-1], ctx, rng)

        # Fill remaining template vars safely
        try:
            body = body_filled.format_map(_SafeDict(ctx))
        except (KeyError, ValueError):
            body = body_filled  # leave unfilled placeholders as-is

        try:
            heading = heading_tpl.format_map(_SafeDict(ctx))
        except (KeyError, ValueError):
            heading = heading_tpl

        clause = Clause(id=cid, heading=heading, text=body)
        clauses.append(clause)

        # Record xrefs as key facts
        for xref_tgt in xref_targets:
            key_facts.append(
                KeyFact(
                    kind=KeyFactKind.XREF,
                    clause_id=cid,
                    xref_target=xref_tgt,
                    xref_source_clause=cid,
                )
            )

        # Record amount facts (look for the amount in body)
        if str(amount_primary) in body:
            key_facts.append(
                KeyFact(
                    kind=KeyFactKind.AMOUNT,
                    clause_id=cid,
                    label="primary_fee",
                    amount=amount_primary,
                )
            )

    # Add date key facts
    key_facts.append(
        KeyFact(
            kind=KeyFactKind.DATE,
            label="effective_date",
            date_str=eff_date,
            date_label="effective_date",
        )
    )
    key_facts.append(
        KeyFact(
            kind=KeyFactKind.DATE,
            label="termination_date",
            date_str=term_date,
            date_label="termination_date",
        )
    )

    # Build title: "SERVICE AGREEMENT between {party_a} and {party_b}"
    title = f"{ctype['title']} between {name_a} and {name_b}"

    contract = Contract(
        id=contract_id,
        title=title,
        contract_type=ctype_key,
        parties=[party_a, party_b],
        effective_date=eff_date,
        termination_date=term_date,
        clauses=clauses,
        key_facts=key_facts,
        governing_law=law,
        notice_period_days=notice,
    )
    return contract


class _SafeDict(dict):  # type: ignore[type-arg]
    """Return the key as {key} when missing, avoiding KeyError in format_map."""

    def __missing__(self, key: str) -> str:
        return f"{{{key}}}"
