"""Party swap tamper (content-level).

Tamper 4: replace exactly one occurrence of a party name with a different
name or a plausible variant.
"""

from __future__ import annotations

import random

from datagen.models import Contract, TamperDetail, TamperType
from datagen.tamper.base import ContentTamper, TamperNotApplicable

# Replacement pool - used when no alias is available
_SUBSTITUTE_SUFFIXES = [
    "Global Pvt. Ltd.",
    "International Ltd.",
    "Holdings Inc.",
    "Ventures LLP",
    "Group Corp.",
]


def _make_substitute(original_name: str, rng: random.Random) -> str:
    """Create a plausible substitute name that is different from *original_name*."""
    parts = original_name.split()
    if len(parts) >= 2:
        # Swap first word or change corporate type
        new_suffix = rng.choice(_SUBSTITUTE_SUFFIXES)
        return f"{parts[0]} {new_suffix}"
    return original_name + " & Associates"


class PartySwapTamper(ContentTamper):
    """Tamper 4: swap exactly one occurrence of a party name."""

    tamper_type = TamperType.PARTY_SWAP

    def apply(self, artifact: Contract, rng: random.Random) -> tuple[Contract, TamperDetail]:
        contract = artifact.model_copy_deep()

        if not contract.parties:
            raise TamperNotApplicable("Contract has no parties.")

        # Choose which party to swap
        party = rng.choice(contract.parties)
        original_name = party.name

        # Choose a substitute: prefer aliases, else generate one
        if party.aliases:
            substitute = rng.choice(party.aliases)
        else:
            substitute = _make_substitute(original_name, rng)

        # Ensure substitute != original
        if substitute == original_name:
            substitute = _make_substitute(original_name, rng)

        # Find all clauses containing the party name and pick one occurrence
        candidate_clauses = [c for c in contract.clauses if original_name in c.text]

        # Also check title / header fields
        if not candidate_clauses:
            # Try preamble substitution in contract title
            if original_name in contract.title:
                contract.title = contract.title.replace(original_name, substitute, 1)
                detail = TamperDetail(
                    tamper_type=TamperType.PARTY_SWAP,
                    original_value=original_name,
                    tampered_value=substitute,
                    subtype="title_substitution",
                )
                return contract, detail
            raise TamperNotApplicable(
                f"Party name '{original_name}' not found in any clause text or title."
            )

        target_clause = rng.choice(candidate_clauses)
        target_clause.text = target_clause.text.replace(original_name, substitute, 1)

        detail = TamperDetail(
            tamper_type=TamperType.PARTY_SWAP,
            clause_id=target_clause.id,
            original_value=original_name,
            tampered_value=substitute,
            subtype="name_substitution",
        )
        return contract, detail
