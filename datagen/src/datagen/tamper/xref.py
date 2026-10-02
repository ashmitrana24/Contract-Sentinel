"""Cross-reference break tamper (content-level).

Tamper 7: xref_break - change one valid cross-reference to point to a
non-existent clause.
"""

from __future__ import annotations

import random
import re

from datagen.models import Contract, KeyFactKind, TamperDetail, TamperType
from datagen.tamper.base import ContentTamper, TamperNotApplicable

# Pattern to find "Clause X.Y" references in text
_CLAUSE_REF_RE = re.compile(r"Clause\s+(\d+(?:\.\d+)?)")


def _non_existent_id(existing_ids: set[str], rng: random.Random) -> str:
    """Generate a clause ID not in *existing_ids*."""
    for _ in range(200):
        n = rng.randint(50, 999)
        cid = str(n)
        if cid not in existing_ids:
            return cid
    return "999"


class XrefBreakTamper(ContentTamper):
    """Tamper 7: break one valid cross-reference to point to a ghost clause."""

    tamper_type = TamperType.XREF_BREAK

    def apply(self, artifact: Contract, rng: random.Random) -> tuple[Contract, TamperDetail]:
        contract = artifact.model_copy_deep()
        existing_ids = contract.clause_ids()

        # Collect all (clause, match) pairs
        candidates: list[tuple[object, re.Match]] = []  # type: ignore[type-arg]
        for clause in contract.clauses:
            for m in _CLAUSE_REF_RE.finditer(clause.text):
                ref_target = m.group(1)
                if ref_target in existing_ids:
                    candidates.append((clause, m))

        if not candidates:
            raise TamperNotApplicable("No valid cross-references found in contract clauses.")

        target_clause, match = rng.choice(candidates)  # type: ignore[assignment]
        original_ref = match.group(1)
        ghost_id = _non_existent_id(existing_ids, rng)

        # Replace only this occurrence
        old_text = target_clause.text  # type: ignore[union-attr]
        new_text = old_text[: match.start(1)] + ghost_id + old_text[match.end(1) :]
        target_clause.text = new_text  # type: ignore[union-attr]

        # Update the xref key fact if it exists
        for kf in contract.key_facts:
            if (
                kf.kind == KeyFactKind.XREF
                and kf.xref_target == original_ref
                and kf.xref_source_clause == target_clause.id  # type: ignore[union-attr]
            ):
                kf.xref_target = ghost_id
                break

        detail = TamperDetail(
            tamper_type=TamperType.XREF_BREAK,
            clause_id=target_clause.id,  # type: ignore[union-attr]
            original_value=f"Clause {original_ref}",
            tampered_value=f"Clause {ghost_id}",
            subtype="ghost_reference",
        )
        return contract, detail
