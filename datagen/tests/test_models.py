"""Tests for models.py."""

from __future__ import annotations

from datagen.models import (
    Contract,
    DocLabel,
    KeyFactKind,
    MonetaryAmount,
    SourceType,
    TamperDetail,
    TamperType,
)


def test_monetary_amount_str() -> None:
    a = MonetaryAmount(figure="Rs. 10,00,000", words="Rupees Ten Lakh Only")
    assert "Rs. 10,00,000" in str(a)
    assert "Rupees Ten Lakh Only" in str(a)


def test_contract_clause_ids(sample_contract: Contract) -> None:
    ids = sample_contract.clause_ids()
    assert "1" in ids
    assert "5" in ids


def test_contract_get_clause(sample_contract: Contract) -> None:
    c = sample_contract.get_clause("2")
    assert c is not None
    assert c.heading == "Payment"


def test_contract_get_clause_missing(sample_contract: Contract) -> None:
    assert sample_contract.get_clause("999") is None


def test_contract_xref_facts(sample_contract: Contract) -> None:
    xrefs = sample_contract.xref_facts()
    assert len(xrefs) >= 1
    assert all(kf.kind == KeyFactKind.XREF for kf in xrefs)


def test_contract_deep_copy_independent(sample_contract: Contract) -> None:
    copy = sample_contract.model_copy_deep()
    copy.clauses[0].text = "MODIFIED"
    assert sample_contract.clauses[0].text != "MODIFIED"


def test_doc_label_serialisation() -> None:
    lbl = DocLabel(
        doc_id="test_001_clean",
        source_id="test_001",
        source_type=SourceType.SYNTHETIC,
        is_tampered=False,
        seed=42,
        generator_version="datagen-0.1.0",
        sha256="abc123",
        split="train",
    )
    json_str = lbl.model_dump_json()
    restored = DocLabel.model_validate_json(json_str)
    assert restored.doc_id == lbl.doc_id
    assert restored.split == "train"


def test_tamper_detail_dangling_xrefs() -> None:
    detail = TamperDetail(
        tamper_type=TamperType.CLAUSE_DELETE,
        clause_id="3",
        dangling_xrefs=["1", "2"],
    )
    assert len(detail.dangling_xrefs) == 2
