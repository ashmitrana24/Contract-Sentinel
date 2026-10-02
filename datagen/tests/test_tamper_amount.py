"""Tests for amount tampers."""

from __future__ import annotations

import random

import pytest

from datagen.models import (
    Clause,
    Contract,
    TamperType,
)
from datagen.tamper.amount import AmountBothTamper, AmountFigureOnlyTamper
from datagen.tamper.base import TamperNotApplicable


@pytest.fixture
def contract_with_amount(sample_contract: Contract) -> Contract:
    return sample_contract


def test_figure_only_changes_figure(
    contract_with_amount: Contract, seeded_rng: random.Random
) -> None:
    tamper = AmountFigureOnlyTamper()
    new_contract, detail = tamper.apply(contract_with_amount, seeded_rng)
    assert detail.tamper_type == TamperType.AMOUNT_FIGURE_ONLY

    # Figure must have changed
    orig_figure = "Rs. 10,00,000"
    assert detail.tampered_value != orig_figure
    # New figure must appear in a clause
    assert any(detail.tampered_value in c.text for c in new_contract.clauses)


def test_figure_only_words_unchanged(
    contract_with_amount: Contract, seeded_rng: random.Random
) -> None:
    tamper = AmountFigureOnlyTamper()
    new_contract, _detail = tamper.apply(contract_with_amount, seeded_rng)
    # Words "Rupees Ten Lakh Only" must still be present
    all_text = " ".join(c.text for c in new_contract.clauses)
    assert "Rupees Ten Lakh Only" in all_text


def test_figure_only_label(contract_with_amount: Contract, seeded_rng: random.Random) -> None:
    tamper = AmountFigureOnlyTamper()
    _, detail = tamper.apply(contract_with_amount, seeded_rng)
    assert detail.subtype == "figure_words_mismatch"
    assert detail.original_value == "Rs. 10,00,000"


def test_amount_both_changes_figure_and_words(
    contract_with_amount: Contract, seeded_rng: random.Random
) -> None:
    tamper = AmountBothTamper()
    new_contract, detail = tamper.apply(contract_with_amount, seeded_rng)
    assert detail.tamper_type == TamperType.AMOUNT_BOTH

    # Check that the key fact was updated (not the original amount)
    amount_facts = [kf for kf in new_contract.key_facts if kf.kind is not None and kf.amount]
    if amount_facts:
        updated = amount_facts[0].amount
        assert updated is not None
        assert updated.figure != "Rs. 10,00,000"

    # Tampered value should be present in text (in target clause)
    assert detail.tampered_value is not None


def test_amount_both_subtype(contract_with_amount: Contract, seeded_rng: random.Random) -> None:
    tamper = AmountBothTamper()
    _, detail = tamper.apply(contract_with_amount, seeded_rng)
    assert detail.subtype == "consistent_change"


def test_no_amount_raises(seeded_rng: random.Random) -> None:
    """Contract with no amount facts must raise TamperNotApplicable."""
    contract = Contract(
        id="no_amount",
        title="Empty Contract",
        clauses=[Clause(id="1", heading="Only Clause", text="No money here.")],
        key_facts=[],
    )
    tamper = AmountFigureOnlyTamper()
    with pytest.raises(TamperNotApplicable):
        tamper.apply(contract, seeded_rng)


def test_amount_deterministic(
    contract_with_amount: Contract,
) -> None:
    """Same seed → same tamper output."""
    tamper = AmountFigureOnlyTamper()
    _, d1 = tamper.apply(contract_with_amount.model_copy_deep(), random.Random(42))
    _, d2 = tamper.apply(contract_with_amount.model_copy_deep(), random.Random(42))
    assert d1.tampered_value == d2.tampered_value
