"""Tests for incremental edit tamper."""

from __future__ import annotations

import random

import pymupdf as fitz

from datagen.models import Contract, TamperType
from datagen.render.pdf_renderer import render_contract_to_bytes
from datagen.tamper.incremental import IncrementalEditTamper


def test_incremental_edit_produces_pdf(sample_contract: Contract) -> None:
    pdf_bytes = render_contract_to_bytes(sample_contract)
    tamper = IncrementalEditTamper()
    new_bytes, _detail = tamper.apply(pdf_bytes, random.Random(42))
    assert new_bytes[:4] == b"%PDF"


def test_incremental_edit_two_eof(sample_contract: Contract) -> None:
    pdf_bytes = render_contract_to_bytes(sample_contract)
    tamper = IncrementalEditTamper()
    new_bytes, _detail = tamper.apply(pdf_bytes, random.Random(42))
    assert new_bytes.count(b"%%EOF") >= 2


def test_incremental_edit_label(sample_contract: Contract) -> None:
    pdf_bytes = render_contract_to_bytes(sample_contract)
    tamper = IncrementalEditTamper()
    _, detail = tamper.apply(pdf_bytes, random.Random(42))
    assert detail.tamper_type == TamperType.INCREMENTAL_EDIT
    assert detail.original_value is not None
    assert detail.tampered_value is not None
    assert detail.original_value != detail.tampered_value


def test_incremental_edit_new_value_in_text(sample_contract: Contract) -> None:
    pdf_bytes = render_contract_to_bytes(sample_contract)
    tamper = IncrementalEditTamper()
    new_bytes, detail = tamper.apply(pdf_bytes, random.Random(42))

    doc = fitz.open(stream=new_bytes, filetype="pdf")
    try:
        text = "".join(page.get_text() for page in doc)
    finally:
        doc.close()

    assert detail.tampered_value in text


def test_incremental_edit_deterministic(sample_contract: Contract) -> None:
    pdf_bytes = render_contract_to_bytes(sample_contract)
    tamper = IncrementalEditTamper()
    _, d1 = tamper.apply(pdf_bytes, random.Random(13))
    _, d2 = tamper.apply(pdf_bytes, random.Random(13))
    assert d1.original_value == d2.original_value
    assert d1.tampered_value == d2.tampered_value
