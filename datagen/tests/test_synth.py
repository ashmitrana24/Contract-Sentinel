"""Tests for the synthetic builder."""

from __future__ import annotations

import random

from datagen.models import Contract, KeyFactKind
from datagen.synth.builder import (
    _amount_to_words_indian,
    _indian_format,
    build_synthetic_contract,
)


def test_indian_format_basic() -> None:
    assert _indian_format(100000) == "1,00,000"
    assert _indian_format(1000000) == "10,00,000"
    assert _indian_format(10000000) == "1,00,00,000"
    assert _indian_format(500) == "500"


def test_amount_to_words() -> None:
    words = _amount_to_words_indian(1_000_000)
    assert "Rupees" in words
    assert len(words) > 5


def test_build_contract_structure() -> None:
    rng = random.Random(42)
    contract = build_synthetic_contract("c001", rng=rng)
    assert isinstance(contract, Contract)
    assert contract.id == "c001"
    assert len(contract.parties) == 2
    assert len(contract.clauses) >= 8


def test_build_contract_has_dates(synth_contract: Contract) -> None:
    date_facts = synth_contract.date_facts()
    assert len(date_facts) >= 2  # effective + termination


def test_build_contract_has_key_facts(synth_contract: Contract) -> None:
    assert len(synth_contract.key_facts) > 0


def test_build_contract_clause_ids_unique(synth_contract: Contract) -> None:
    ids = [c.id for c in synth_contract.clauses]
    assert len(ids) == len(set(ids)), "Duplicate clause IDs found."


def test_build_contract_deterministic() -> None:
    """Same seed → same contract id, parties, clauses."""
    rng1 = random.Random(7)
    rng2 = random.Random(7)
    c1 = build_synthetic_contract("same", rng=rng1)
    c2 = build_synthetic_contract("same", rng=rng2)
    assert c1.parties[0].name == c2.parties[0].name
    assert len(c1.clauses) == len(c2.clauses)
    assert c1.effective_date == c2.effective_date


def test_build_contract_different_seeds() -> None:
    rng1 = random.Random(1)
    rng2 = random.Random(2)
    c1 = build_synthetic_contract("a", rng=rng1)
    c2 = build_synthetic_contract("b", rng=rng2)
    # Very unlikely to be identical with different seeds
    assert not (c1.parties[0].name == c2.parties[0].name and c1.effective_date == c2.effective_date)


def test_build_contract_no_name_collision() -> None:
    used: set[str] = set()
    rng = random.Random(55)
    contracts = [
        build_synthetic_contract(f"c{i}", rng=random.Random(rng.randint(0, 99999)), used_names=used)
        for i in range(20)
    ]
    all_names = [p.name for c in contracts for p in c.parties]
    # All company names should be unique
    assert len(all_names) == len(set(all_names))


def test_synth_contract_has_amount_in_text(synth_contract: Contract) -> None:
    """Amount figure should appear in at least one clause body."""
    for kf in synth_contract.key_facts:
        if kf.kind == KeyFactKind.AMOUNT and kf.amount:
            figure = kf.amount.figure
            found = any(figure in c.text for c in synth_contract.clauses)
            assert found, f"Figure {figure!r} not found in any clause."
            break
