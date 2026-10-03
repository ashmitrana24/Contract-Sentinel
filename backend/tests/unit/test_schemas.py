"""Unit tests for Pydantic schemas."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from clauseguard.schemas.findings import Finding, Severity
from clauseguard.schemas.parsed import ClauseModel, PageModel, ParsedDocument, SpanModel


@pytest.mark.unit
def test_finding_roundtrip() -> None:
    f = Finding(
        module="forensics",
        type="amount_mismatch",
        severity=Severity.HIGH,
        page=1,
        clause_ref="4.2",
        bbox=(50.0, 100.0, 200.0, 150.0),
        evidence="Rs. 10,000 vs Rupees One Lakh",
        explanation="Figure does not match word value",
        confidence=0.95,
    )
    dumped = f.model_dump_json()
    loaded = Finding.from_json(dumped)
    assert loaded == f
    assert loaded.model_dump_json_roundtrip() == f


@pytest.mark.unit
def test_finding_confidence_clamping() -> None:
    f_high = Finding(
        module="test",
        type="test_type",
        severity=Severity.LOW,
        evidence="sample",
        explanation="sample",
        confidence=1.5,
    )
    assert f_high.confidence == 1.0

    f_low = Finding(
        module="test",
        type="test_type",
        severity=Severity.LOW,
        evidence="sample",
        explanation="sample",
        confidence=-0.5,
    )
    assert f_low.confidence == 0.0


@pytest.mark.unit
def test_finding_bbox_validation() -> None:
    # 4 floats valid
    f = Finding(
        module="test",
        type="test_type",
        severity=Severity.LOW,
        evidence="sample",
        explanation="sample",
        bbox=(10.0, 20.0, 30.0, 40.0),
    )
    assert f.bbox == (10.0, 20.0, 30.0, 40.0)

    # 3 or 5 elements must raise ValueError
    with pytest.raises(ValidationError):
        Finding(
            module="test",
            type="test_type",
            severity=Severity.LOW,
            evidence="sample",
            explanation="sample",
            bbox=(10.0, 20.0, 30.0),  # type: ignore[arg-type]
        )


@pytest.mark.unit
def test_parsed_document_schema() -> None:
    span = SpanModel(
        text="Hello",
        bbox=(10.0, 20.0, 30.0, 40.0),
        size=12.0,
        font="Helvetica",
        color=0,
        flags=0,
    )
    page = PageModel(
        page_no=1,
        width=595.0,
        height=842.0,
        text="Hello",
        char_count=5,
        spans=[span],
    )
    clause = ClauseModel(
        order_idx=0,
        clause_id="1",
        heading="Title",
        text="Hello",
        level=1,
        parent_clause_id=None,
        page_start=1,
        page_end=1,
        kind="clause",
    )
    doc = ParsedDocument(
        pdf_metadata={"author": "Lawyer"},
        page_count=1,
        needs_ocr=False,
        pages=[page],
        clauses=[clause],
    )
    assert doc.page_count == 1
    assert len(doc.pages) == 1
    assert len(doc.clauses) == 1
    assert doc.pages[0].spans[0].font == "Helvetica"
