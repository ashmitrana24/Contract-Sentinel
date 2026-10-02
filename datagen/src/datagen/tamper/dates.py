"""Date tamper (content-level).

Tamper 3: date_shift - either move termination_date before effective_date,
or change one occurrence of a date that appears more than once.
"""

from __future__ import annotations

import random
import re

from datagen.models import Contract, KeyFactKind, TamperDetail, TamperType
from datagen.tamper.base import ContentTamper, TamperNotApplicable

_DATE_RE = re.compile(r"\b(\d{4}-\d{2}-\d{2})\b")


def _shift_date(date_str: str, delta_days: int) -> str:
    """Shift an ISO date by *delta_days* (may be negative)."""
    import datetime

    d = datetime.date.fromisoformat(date_str)
    d2 = d + datetime.timedelta(days=delta_days)
    return d2.isoformat()


class DateShiftTamper(ContentTamper):
    """Tamper 3: shift a date to create an inconsistency."""

    tamper_type = TamperType.DATE_SHIFT

    def apply(self, artifact: Contract, rng: random.Random) -> tuple[Contract, TamperDetail]:
        contract = artifact.model_copy_deep()

        # Strategy A: move termination before effective (if both are set)
        if contract.effective_date and contract.termination_date:
            original = contract.termination_date
            # Move termination to BEFORE effective date
            # Shift it back by 1 year + random days
            delta = -(365 + rng.randint(1, 365))
            tampered = _shift_date(contract.effective_date, delta)

            # Update the termination_date in header
            contract.termination_date = tampered

            # Also update in clause text where it appears
            for clause in contract.clauses:
                if original in clause.text:
                    clause.text = clause.text.replace(original, tampered, 1)
                    break

            # Update key fact
            for kf in contract.key_facts:
                if kf.kind == KeyFactKind.DATE and kf.date_label == "termination_date":
                    kf.date_str = tampered
                    break

            detail = TamperDetail(
                tamper_type=TamperType.DATE_SHIFT,
                original_value=original,
                tampered_value=tampered,
                subtype="termination_before_effective",
            )
            return contract, detail

        # Strategy B: find a date that appears in more than one clause and change one
        date_occurrences: dict[str, list[str]] = {}
        for clause in contract.clauses:
            for m in _DATE_RE.finditer(clause.text):
                date_val = m.group(1)
                date_occurrences.setdefault(date_val, []).append(clause.id)

        multi = {d: cids for d, cids in date_occurrences.items() if len(cids) > 1}
        if not multi:
            raise TamperNotApplicable(
                "Contract has neither valid date pair nor repeated dates for date_shift."
            )

        original = rng.choice(list(multi.keys()))
        clause_ids = multi[original]
        target_clause_id = rng.choice(clause_ids)
        delta = rng.choice([-400, -200, 400, 600])
        tampered = _shift_date(original, delta)

        for clause in contract.clauses:
            if clause.id == target_clause_id:
                clause.text = clause.text.replace(original, tampered, 1)
                break

        detail = TamperDetail(
            tamper_type=TamperType.DATE_SHIFT,
            clause_id=target_clause_id,
            original_value=original,
            tampered_value=tampered,
            subtype="repeated_date_change",
        )
        return contract, detail
