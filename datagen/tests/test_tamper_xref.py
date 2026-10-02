"""Tests for cross-reference break tamper."""

from __future__ import annotations

import random

import pytest

from datagen.models import Clause, Contract, TamperType
from datagen.tamper.base import TamperNotApplicable
from datagen.tamper.xref import XrefBreakTamper


def test_xref_break_changes_reference(sample_contract: Contract) -> None:
    tamper = XrefBreakTamper()
    rng = random.Random(42)
    _new_contract, detail = tamper.apply(sample_contract, rng)
    assert detail.tamper_type == TamperType.XREF_BREAK
    assert detail.original_value != detail.tampered_value


def test_xref_break_target_non_existent(sample_contract: Contract) -> None:
    tamper = XrefBreakTamper()
    rng = random.Random(42)
    new_contract, detail = tamper.apply(sample_contract, rng)
    # The new reference should NOT be a valid clause id
    ghost = detail.tampered_value.replace("Clause ", "").strip()
    assert ghost not in new_contract.clause_ids()


def test_xref_break_in_text(sample_contract: Contract) -> None:
    tamper = XrefBreakTamper()
    rng = random.Random(42)
    new_contract, detail = tamper.apply(sample_contract, rng)
    # Ghost reference should appear in the clause text
    all_text = " ".join(c.text for c in new_contract.clauses)
    assert detail.tampered_value in all_text


def test_xref_break_no_xrefs_raises() -> None:
    contract = Contract(
        id="no_xref",
        title="No XRefs",
        clauses=[
            Clause(id="1", heading="H1", text="No references to other clauses."),
            Clause(id="2", heading="H2", text="Standalone clause."),
        ],
        key_facts=[],
    )
    tamper = XrefBreakTamper()
    with pytest.raises(TamperNotApplicable):
        tamper.apply(contract, random.Random(1))


def test_xref_break_deterministic(sample_contract: Contract) -> None:
    tamper = XrefBreakTamper()
    _, d1 = tamper.apply(sample_contract.model_copy_deep(), random.Random(33))
    _, d2 = tamper.apply(sample_contract.model_copy_deep(), random.Random(33))
    assert d1.tampered_value == d2.tampered_value
