"""Clause-level tampers (content-level).

Tamper 5: clause_delete - remove a clause without renumbering;
          records which cross-references became dangling.
Tamper 6: clause_insert - insert a risky clause at a random position.
"""

from __future__ import annotations

import random

from datagen.models import (
    Clause,
    Contract,
    KeyFactKind,
    TamperDetail,
    TamperType,
)
from datagen.synth.templates import RISKY_CLAUSES
from datagen.tamper.base import ContentTamper, TamperNotApplicable


class ClauseDeleteTamper(ContentTamper):
    """Tamper 5: delete a clause, leaving dangling xrefs."""

    tamper_type = TamperType.CLAUSE_DELETE

    def apply(self, artifact: Contract, rng: random.Random) -> tuple[Contract, TamperDetail]:
        contract = artifact.model_copy_deep()

        if len(contract.clauses) < 2:
            raise TamperNotApplicable("Contract has fewer than 2 clauses; cannot delete one.")

        # Pick a clause to delete (not the first)
        target = rng.choice(contract.clauses[1:])
        target_id = target.id
        target_heading = target.heading

        # Remove it
        contract.clauses = [c for c in contract.clauses if c.id != target_id]

        # Remove any key facts tied to this clause
        contract.key_facts = [kf for kf in contract.key_facts if kf.clause_id != target_id]

        # Find xrefs that now dangle (point to the deleted clause)
        dangling: list[str] = []
        for kf in contract.key_facts:
            if kf.kind == KeyFactKind.XREF and kf.xref_target == target_id:
                dangling.append(kf.xref_source_clause or "?")

        detail = TamperDetail(
            tamper_type=TamperType.CLAUSE_DELETE,
            clause_id=target_id,
            original_value=target_heading,
            tampered_value="<deleted>",
            subtype="clause_removed",
            dangling_xrefs=dangling,
        )
        return contract, detail


class ClauseInsertTamper(ContentTamper):
    """Tamper 6: insert a risky clause at a random position."""

    tamper_type = TamperType.CLAUSE_INSERT

    def apply(self, artifact: Contract, rng: random.Random) -> tuple[Contract, TamperDetail]:
        contract = artifact.model_copy_deep()

        # Pick a risky clause from the bank
        heading_tpl, body_tpl = rng.choice(RISKY_CLAUSES)

        # Generate a fractional clause ID (e.g. "3.99") that doesn't collide
        existing_top = sorted(
            {int(c.id.split(".")[0]) for c in contract.clauses if c.id.split(".")[0].isdigit()}
        )
        if existing_top:
            insert_after = (
                rng.choice(existing_top[:-1]) if len(existing_top) > 1 else existing_top[0]
            )
        else:
            insert_after = 1
        new_id = f"{insert_after}.99"

        # Expand template
        party_a = contract.parties[0].name if contract.parties else "Party A"
        party_b = contract.parties[1].name if len(contract.parties) > 1 else "Party B"
        # xref_governing: pick a real clause id
        clause_ids = [c.id for c in contract.clauses]
        xref_governing = rng.choice(clause_ids) if clause_ids else "1"

        ctx = {
            "party_a": party_a,
            "party_b": party_b,
            "xref_governing": f"Clause {xref_governing}",
        }
        body = body_tpl.format_map(_SafeDict(ctx))
        heading = heading_tpl.format_map(_SafeDict(ctx))

        risky_clause = Clause(id=new_id, heading=heading, text=body)

        # Insert after the chosen top-level clause index
        insert_pos = next(
            (
                i + 1
                for i, c in enumerate(contract.clauses)
                if c.id.split(".")[0] == str(insert_after)
            ),
            len(contract.clauses),
        )
        contract.clauses.insert(insert_pos, risky_clause)

        detail = TamperDetail(
            tamper_type=TamperType.CLAUSE_INSERT,
            clause_id=new_id,
            original_value="<none>",
            tampered_value=heading,
            subtype="risky_clause_inserted",
        )
        return contract, detail


class _SafeDict(dict):  # type: ignore[type-arg]
    def __missing__(self, key: str) -> str:
        return f"{{{key}}}"
