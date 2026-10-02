"""Tests for party swap tamper."""

from __future__ import annotations

import random

import pytest

from datagen.models import Clause, Contract, TamperType
from datagen.tamper.base import TamperNotApplicable
from datagen.tamper.party import PartySwapTamper


def test_party_swap_changes_name(sample_contract: Contract) -> None:
    tamper = PartySwapTamper()
    rng = random.Random(42)
    _new_contract, detail = tamper.apply(sample_contract, rng)
    assert detail.tamper_type == TamperType.PARTY_SWAP
    assert detail.original_value != detail.tampered_value


def test_party_swap_one_occurrence_only(sample_contract: Contract) -> None:
    """Only one occurrence should be replaced."""
    tamper = PartySwapTamper()
    rng = random.Random(42)
    new_contract, detail = tamper.apply(sample_contract, rng)
    original_name = detail.original_value
    substitute = detail.tampered_value

    # Count occurrences in all clause text
    all_text = " ".join(c.text for c in new_contract.clauses)
    # The substitute appears at least once
    assert all_text.count(substitute) >= 1
    # The original may still appear (other clauses/header), but changed in target
    # We can verify that the total occurrences of original is reduced by 1
    orig_all = " ".join(c.text for c in sample_contract.clauses)
    assert all_text.count(original_name) == orig_all.count(original_name) - 1


def test_party_swap_label(sample_contract: Contract) -> None:
    tamper = PartySwapTamper()
    _, detail = tamper.apply(sample_contract, random.Random(5))
    assert detail.original_value in {"Alpha Corp.", "Beta Ltd."}


def test_party_swap_no_parties_raises() -> None:
    contract = Contract(
        id="no_parties",
        title="No Parties",
        clauses=[Clause(id="1", heading="H", text="text")],
        key_facts=[],
    )
    tamper = PartySwapTamper()
    with pytest.raises(TamperNotApplicable):
        tamper.apply(contract, random.Random(1))


def test_party_swap_single_occurrence(sample_contract: Contract) -> None:
    """Party name appears only in one clause - should still swap."""
    # Remove Alpha Corp. from all clauses except one
    contract = sample_contract.model_copy_deep()
    for i, c in enumerate(contract.clauses):
        if i != 1:  # Keep only clause 2 (Payment) with Alpha Corp.
            c.text = c.text.replace("Alpha Corp.", "the provider")
    tamper = PartySwapTamper()
    _new_contract, detail = tamper.apply(contract, random.Random(3))
    assert detail.original_value == "Alpha Corp." or detail.original_value == "Beta Ltd."


def test_party_swap_deterministic(sample_contract: Contract) -> None:
    tamper = PartySwapTamper()
    _, d1 = tamper.apply(sample_contract.model_copy_deep(), random.Random(77))
    _, d2 = tamper.apply(sample_contract.model_copy_deep(), random.Random(77))
    assert d1.tampered_value == d2.tampered_value
