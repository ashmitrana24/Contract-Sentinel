"""Shared pytest fixtures."""

from __future__ import annotations

import random

import pytest

from datagen.models import (
    Clause,
    Contract,
    KeyFact,
    KeyFactKind,
    MonetaryAmount,
    Party,
)
from datagen.synth.builder import build_synthetic_contract


@pytest.fixture
def sample_contract() -> Contract:
    """A minimal but realistic Contract for testing tampers."""
    return Contract(
        id="test_001",
        title="TEST SERVICE AGREEMENT between Alpha Corp. and Beta Ltd.",
        contract_type="service_agreement",
        parties=[
            Party(name="Alpha Corp.", aliases=["Alpha", "A.C."], role="Service Provider"),
            Party(name="Beta Ltd.", aliases=["Beta"], role="Client"),
        ],
        effective_date="2024-01-01",
        termination_date="2026-01-01",
        clauses=[
            Clause(
                id="1",
                heading="Definitions",
                text=(
                    "In this Agreement 'Services' means the technical services "
                    "referenced in Clause 3. Alpha Corp. shall provide services "
                    "to Beta Ltd. commencing 2024-01-01."
                ),
            ),
            Clause(
                id="2",
                heading="Payment",
                text=(
                    "Beta Ltd. shall pay Alpha Corp. a fee of Rs. 10,00,000 "
                    "(Rupees Ten Lakh Only) per annum. Payment is due within "
                    "thirty days of invoice."
                ),
            ),
            Clause(
                id="3",
                heading="Scope of Work",
                text=(
                    "The scope of services is detailed herein. See also Clause 2 "
                    "for payment terms. Completion by 2026-01-01."
                ),
            ),
            Clause(
                id="4",
                heading="Termination",
                text=(
                    "Either party may terminate with 30 days' notice. "
                    "Upon termination Beta Ltd. shall pay all outstanding fees. "
                    "See Clause 2 for fee schedule."
                ),
            ),
            Clause(
                id="5",
                heading="Governing Law",
                text="This Agreement is governed by the laws of India.",
            ),
        ],
        key_facts=[
            KeyFact(
                kind=KeyFactKind.AMOUNT,
                clause_id="2",
                label="service_fee",
                amount=MonetaryAmount(
                    figure="Rs. 10,00,000",
                    words="Rupees Ten Lakh Only",
                    currency_symbol="Rs.",
                ),
            ),
            KeyFact(
                kind=KeyFactKind.DATE,
                label="effective_date",
                date_str="2024-01-01",
                date_label="effective_date",
            ),
            KeyFact(
                kind=KeyFactKind.DATE,
                label="termination_date",
                date_str="2026-01-01",
                date_label="termination_date",
            ),
            KeyFact(
                kind=KeyFactKind.XREF,
                clause_id="1",
                xref_target="3",
                xref_source_clause="1",
            ),
            KeyFact(
                kind=KeyFactKind.XREF,
                clause_id="3",
                xref_target="2",
                xref_source_clause="3",
            ),
        ],
        governing_law="the laws of India",
        notice_period_days=30,
    )


@pytest.fixture
def seeded_rng() -> random.Random:
    return random.Random(42)


@pytest.fixture
def synth_contract() -> Contract:
    rng = random.Random(99)
    return build_synthetic_contract("synth_test_001", rng=rng)
