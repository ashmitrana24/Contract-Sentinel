"""Tests for clause delete and insert tampers."""

from __future__ import annotations

import random

import pytest

from datagen.models import Clause, Contract, TamperType
from datagen.tamper.base import TamperNotApplicable
from datagen.tamper.clauses import ClauseDeleteTamper, ClauseInsertTamper


def test_clause_delete_removes_clause(sample_contract: Contract) -> None:
    tamper = ClauseDeleteTamper()
    rng = random.Random(42)
    new_contract, detail = tamper.apply(sample_contract, rng)
    assert detail.tamper_type == TamperType.CLAUSE_DELETE
    deleted_id = detail.clause_id
    assert deleted_id not in {c.id for c in new_contract.clauses}


def test_clause_delete_no_renumbering(sample_contract: Contract) -> None:
    """Remaining clauses should keep their original IDs."""
    tamper = ClauseDeleteTamper()
    rng = random.Random(42)
    new_contract, detail = tamper.apply(sample_contract, rng)
    deleted_id = detail.clause_id
    remaining_ids = {c.id for c in new_contract.clauses}
    original_ids = {c.id for c in sample_contract.clauses}
    assert remaining_ids == original_ids - {deleted_id}


def test_clause_delete_dangling_xrefs(sample_contract: Contract) -> None:
    tamper = ClauseDeleteTamper()
    rng = random.Random(42)
    _, detail = tamper.apply(sample_contract, rng)
    # dangling_xrefs is a list (may be empty if no xrefs pointed there)
    assert isinstance(detail.dangling_xrefs, list)


def test_clause_delete_one_clause_raises() -> None:
    """Contract with only 1 clause must raise TamperNotApplicable."""
    contract = Contract(
        id="tiny",
        title="Tiny",
        clauses=[Clause(id="1", heading="Only", text="body")],
        key_facts=[],
    )
    tamper = ClauseDeleteTamper()
    with pytest.raises(TamperNotApplicable):
        tamper.apply(contract, random.Random(1))


def test_clause_insert_adds_clause(sample_contract: Contract) -> None:
    tamper = ClauseInsertTamper()
    rng = random.Random(42)
    new_contract, detail = tamper.apply(sample_contract, rng)
    assert detail.tamper_type == TamperType.CLAUSE_INSERT
    assert len(new_contract.clauses) == len(sample_contract.clauses) + 1


def test_clause_insert_new_id_not_in_original(sample_contract: Contract) -> None:
    tamper = ClauseInsertTamper()
    rng = random.Random(42)
    _new_contract, detail = tamper.apply(sample_contract, rng)
    original_ids = {c.id for c in sample_contract.clauses}
    assert detail.clause_id not in original_ids


def test_clause_insert_risky_content(sample_contract: Contract) -> None:
    """Inserted clause should contain risky language."""
    tamper = ClauseInsertTamper()
    new_contract, detail = tamper.apply(sample_contract, random.Random(7))
    inserted = new_contract.get_clause(detail.clause_id)
    assert inserted is not None
    # Should be one of the risky clause headings
    from datagen.synth.templates import RISKY_CLAUSES

    risky_headings = {h for h, _ in RISKY_CLAUSES}
    assert detail.tampered_value in risky_headings


def test_clause_delete_deterministic(sample_contract: Contract) -> None:
    tamper = ClauseDeleteTamper()
    _, d1 = tamper.apply(sample_contract.model_copy_deep(), random.Random(11))
    _, d2 = tamper.apply(sample_contract.model_copy_deep(), random.Random(11))
    assert d1.clause_id == d2.clause_id
