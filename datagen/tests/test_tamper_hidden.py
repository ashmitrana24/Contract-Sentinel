"""Tests for hidden text tamper."""

from __future__ import annotations

import random

import pymupdf as fitz

from datagen.models import Contract, TamperType
from datagen.render.pdf_renderer import render_contract_to_bytes
from datagen.tamper.hidden_text import HIDDEN_SENTENCES, HiddenTextTamper


def test_hidden_text_tamper_produces_pdf(sample_contract: Contract) -> None:
    pdf_bytes = render_contract_to_bytes(sample_contract)
    tamper = HiddenTextTamper()
    new_bytes, _detail = tamper.apply(pdf_bytes, random.Random(42))
    assert new_bytes[:4] == b"%PDF"


def test_hidden_text_extractable(sample_contract: Contract) -> None:
    pdf_bytes = render_contract_to_bytes(sample_contract)
    tamper = HiddenTextTamper()
    new_bytes, _detail = tamper.apply(pdf_bytes, random.Random(42))

    doc = fitz.open(stream=new_bytes, filetype="pdf")
    try:
        text = "".join(page.get_text() for page in doc)
    finally:
        doc.close()

    assert "HIDDEN CLAUSE" in text


def test_hidden_text_label(sample_contract: Contract) -> None:
    pdf_bytes = render_contract_to_bytes(sample_contract)
    tamper = HiddenTextTamper()
    _, detail = tamper.apply(pdf_bytes, random.Random(42))
    assert detail.tamper_type == TamperType.HIDDEN_TEXT
    assert detail.subtype == "white_tiny_text"
    assert detail.tampered_value in HIDDEN_SENTENCES


def test_hidden_text_deterministic(sample_contract: Contract) -> None:
    pdf_bytes = render_contract_to_bytes(sample_contract)
    tamper = HiddenTextTamper()
    _, d1 = tamper.apply(pdf_bytes, random.Random(7))
    _, d2 = tamper.apply(pdf_bytes, random.Random(7))
    assert d1.tampered_value == d2.tampered_value
