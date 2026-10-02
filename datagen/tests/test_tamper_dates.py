"""Tests for date shift tamper."""

from __future__ import annotations

import random

from datagen.models import Contract, TamperType
from datagen.tamper.dates import DateShiftTamper


def test_date_shift_changes_termination(sample_contract: Contract) -> None:
    tamper = DateShiftTamper()
    rng = random.Random(42)
    _new_contract, detail = tamper.apply(sample_contract, rng)
    assert detail.tamper_type == TamperType.DATE_SHIFT
    assert detail.original_value != detail.tampered_value


def test_date_shift_termination_before_effective(sample_contract: Contract) -> None:
    tamper = DateShiftTamper()
    rng = random.Random(42)
    new_contract, detail = tamper.apply(sample_contract, rng)
    # When strategy A is chosen, termination_date < effective_date
    if detail.subtype == "termination_before_effective":
        assert new_contract.termination_date < new_contract.effective_date


def test_date_shift_tampered_in_contract(sample_contract: Contract) -> None:
    tamper = DateShiftTamper()
    rng = random.Random(42)
    new_contract, detail = tamper.apply(sample_contract, rng)
    # Tampered date should appear somewhere
    all_dates = {
        new_contract.effective_date,
        new_contract.termination_date,
        *(c.text for c in new_contract.clauses),
    }
    assert any(detail.tampered_value in s for s in all_dates)


def test_date_shift_label_correct(sample_contract: Contract) -> None:
    tamper = DateShiftTamper()
    rng = random.Random(1)
    _, detail = tamper.apply(sample_contract, rng)
    assert detail.tamper_type == TamperType.DATE_SHIFT
    assert detail.original_value
    assert detail.tampered_value


def test_date_shift_deterministic(sample_contract: Contract) -> None:
    tamper = DateShiftTamper()
    _, d1 = tamper.apply(sample_contract.model_copy_deep(), random.Random(99))
    _, d2 = tamper.apply(sample_contract.model_copy_deep(), random.Random(99))
    assert d1.tampered_value == d2.tampered_value
