"""Amount tampers (content-level).

Tamper 1: amount_figure_only - change the figure but leave the words.
Tamper 2: amount_both - change both figure and words consistently.
"""

from __future__ import annotations

import random
import re

from datagen.models import (
    Contract,
    KeyFactKind,
    MonetaryAmount,
    TamperDetail,
    TamperType,
)
from datagen.synth.builder import _amount_to_words_indian, _indian_format
from datagen.tamper.base import ContentTamper, TamperNotApplicable


def _new_lakh_value(rng: random.Random, old_lakh: int) -> int:
    """Pick a new lakh value that differs from *old_lakh*."""
    candidates = [v for v in range(1, 201) if abs(v - old_lakh) > 2]
    if not candidates:
        return old_lakh + 10
    return rng.choice(candidates)


def _extract_lakh(figure: str) -> int | None:
    """Extract the lakh count from an Indian-formatted figure string, e.g. 'Rs. 10,00,000'."""
    # Strip 'Rs.' and commas
    cleaned = re.sub(r"[^\d]", "", figure)
    if not cleaned:
        return None
    try:
        val = int(cleaned)
        return val // 100_000
    except ValueError:
        return None


def _tamper_amount(
    amount: MonetaryAmount,
    rng: random.Random,
    *,
    change_words: bool,
) -> tuple[MonetaryAmount, str, str]:
    """Return (new_amount, original_str, tampered_str)."""
    old_lakh = _extract_lakh(amount.figure)
    if old_lakh is None or old_lakh < 1:
        raise TamperNotApplicable(f"Cannot parse lakh value from figure: {amount.figure!r}")

    new_lakh = _new_lakh_value(rng, old_lakh)
    new_rupees = new_lakh * 100_000
    new_figure = f"Rs. {_indian_format(new_rupees)}"

    original_str = str(amount)

    if change_words:
        new_words = _amount_to_words_indian(new_rupees)
        new_amount = MonetaryAmount(
            figure=new_figure,
            words=new_words,
            currency_symbol=amount.currency_symbol,
        )
    else:
        # Figure changes but words stay (mismatch)
        new_amount = MonetaryAmount(
            figure=new_figure,
            words=amount.words,  # deliberately unchanged
            currency_symbol=amount.currency_symbol,
        )

    tampered_str = str(new_amount)
    return new_amount, original_str, tampered_str


class AmountFigureOnlyTamper(ContentTamper):
    """Tamper 1: change the numeric figure; leave the words unchanged (mismatch)."""

    tamper_type = TamperType.AMOUNT_FIGURE_ONLY

    def apply(self, artifact: Contract, rng: random.Random) -> tuple[Contract, TamperDetail]:
        contract = artifact.model_copy_deep()

        # Find a clause with an amount fact
        amount_facts = [
            kf for kf in contract.key_facts if kf.kind == KeyFactKind.AMOUNT and kf.amount
        ]
        if not amount_facts:
            raise TamperNotApplicable("No amount facts found in contract.")

        kf = rng.choice(amount_facts)
        old_amount = kf.amount  # type: ignore[assignment]
        new_amount, _original_str, _tampered_str = _tamper_amount(
            old_amount, rng, change_words=False
        )

        # Patch clauses: replace figure occurrence in text
        old_figure = old_amount.figure
        new_figure = new_amount.figure
        patched = False
        for clause in contract.clauses:
            if old_figure in clause.text:
                clause.text = clause.text.replace(old_figure, new_figure, 1)
                patched = True
                break

        if not patched:
            raise TamperNotApplicable(f"Figure '{old_figure}' not found in any clause text.")

        # Update the key fact
        kf.amount = new_amount

        detail = TamperDetail(
            tamper_type=TamperType.AMOUNT_FIGURE_ONLY,
            clause_id=kf.clause_id,
            original_value=old_figure,
            tampered_value=new_figure,
            subtype="figure_words_mismatch",
        )
        return contract, detail


class AmountBothTamper(ContentTamper):
    """Tamper 2: change both figure and words consistently (hard case)."""

    tamper_type = TamperType.AMOUNT_BOTH

    def apply(self, artifact: Contract, rng: random.Random) -> tuple[Contract, TamperDetail]:
        contract = artifact.model_copy_deep()

        amount_facts = [
            kf for kf in contract.key_facts if kf.kind == KeyFactKind.AMOUNT and kf.amount
        ]
        if not amount_facts:
            raise TamperNotApplicable("No amount facts found in contract.")

        kf = rng.choice(amount_facts)
        old_amount = kf.amount  # type: ignore[assignment]
        new_amount, original_str, tampered_str = _tamper_amount(old_amount, rng, change_words=True)

        old_figure = old_amount.figure
        old_words = old_amount.words
        new_figure = new_amount.figure
        new_words = new_amount.words

        patched = False
        for clause in contract.clauses:
            if old_figure in clause.text:
                clause.text = clause.text.replace(old_figure, new_figure, 1)
                clause.text = clause.text.replace(old_words, new_words, 1)
                patched = True
                break

        if not patched:
            raise TamperNotApplicable(f"Figure '{old_figure}' not found in any clause text.")

        kf.amount = new_amount

        detail = TamperDetail(
            tamper_type=TamperType.AMOUNT_BOTH,
            clause_id=kf.clause_id,
            original_value=original_str,
            tampered_value=tampered_str,
            subtype="consistent_change",
        )
        return contract, detail
