"""Tests for the PDF renderer."""

from __future__ import annotations

import pymupdf as fitz

from datagen.models import Contract
from datagen.render.pdf_renderer import render_contract_to_bytes


def test_render_produces_pdf(sample_contract: Contract) -> None:
    pdf = render_contract_to_bytes(sample_contract)
    assert pdf[:4] == b"%PDF"


def test_render_text_extractable(sample_contract: Contract) -> None:
    pdf = render_contract_to_bytes(sample_contract)
    doc = fitz.open(stream=pdf, filetype="pdf")
    try:
        text = "".join(page.get_text() for page in doc)
    finally:
        doc.close()
    assert "Alpha Corp." in text
    assert "Beta Ltd." in text
    assert "Payment" in text


def test_render_single_eof_clean(sample_contract: Contract) -> None:
    pdf = render_contract_to_bytes(sample_contract, is_tampered=False)
    assert pdf.count(b"%%EOF") == 1


def test_render_title_in_text(sample_contract: Contract) -> None:
    pdf = render_contract_to_bytes(sample_contract)
    doc = fitz.open(stream=pdf, filetype="pdf")
    try:
        text = "".join(page.get_text() for page in doc)
    finally:
        doc.close()
    # Title is uppercased in the renderer
    assert "TEST SERVICE AGREEMENT" in text.upper()


def test_render_clause_headings(sample_contract: Contract) -> None:
    pdf = render_contract_to_bytes(sample_contract)
    doc = fitz.open(stream=pdf, filetype="pdf")
    try:
        text = "".join(page.get_text() for page in doc)
    finally:
        doc.close()
    for clause in sample_contract.clauses:
        assert clause.heading in text, f"Heading '{clause.heading}' not in PDF text."


def test_render_deterministic(sample_contract: Contract) -> None:
    """Two renders of the same contract should produce same extracted text."""
    pdf1 = render_contract_to_bytes(sample_contract)
    pdf2 = render_contract_to_bytes(sample_contract)
    # Extract text (byte-level equality is achievable with invariant=1)
    doc1 = fitz.open(stream=pdf1, filetype="pdf")
    doc2 = fitz.open(stream=pdf2, filetype="pdf")
    try:
        text1 = "".join(page.get_text() for page in doc1)
        text2 = "".join(page.get_text() for page in doc2)
    finally:
        doc1.close()
        doc2.close()
    assert text1 == text2


def test_render_tampered_flag_metadata(sample_contract: Contract) -> None:
    """Tampered flag should affect the PDF byte content (producer string)."""
    clean = render_contract_to_bytes(sample_contract, is_tampered=False)
    tampered = render_contract_to_bytes(sample_contract, is_tampered=True)
    assert b"datagen-0.1.0" in clean
    assert b"Adobe Acrobat" in tampered
