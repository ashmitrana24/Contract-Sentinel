"""Unit tests for parse_document function."""

from __future__ import annotations

import pymupdf
import pytest

from clauseguard.parsing.parse_document import ParseError, parse_document


def _create_sample_pdf(text: str, password: str | None = None) -> bytes:
    doc = pymupdf.open()
    page = doc.new_page(width=595, height=842)
    page.insert_text((50, 72), text)
    doc.set_metadata({"title": "Sample Contract", "author": "ClauseGuard Tests"})
    if password:
        pdf_bytes = doc.tobytes(
            encryption=pymupdf.PDF_ENCRYPT_AES_256,
            user_pw=password,
            owner_pw="owner_pass",
        )
    else:
        pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


@pytest.mark.unit
def test_parse_valid_document() -> None:
    text = (
        "CONFIDENTIAL SERVICE AGREEMENT\n\n"
        "1. Definitions\n"
        "Terms and conditions are defined here.\n\n"
        "2. Payment Terms\n"
        "Invoices are payable within 30 days."
    )
    pdf_bytes = _create_sample_pdf(text)
    parsed = parse_document(pdf_bytes)

    assert parsed.page_count == 1
    assert parsed.needs_ocr is False
    assert len(parsed.pages) == 1
    assert len(parsed.clauses) >= 2
    assert parsed.pdf_metadata.get("title") == "Sample Contract"


@pytest.mark.unit
def test_parse_empty_bytes_raises() -> None:
    with pytest.raises(ParseError, match="Empty PDF bytes"):
        parse_document(b"")


@pytest.mark.unit
def test_parse_corrupt_pdf_raises() -> None:
    with pytest.raises(ParseError, match="Cannot open PDF"):
        parse_document(b"not a valid pdf content header or trailer")


@pytest.mark.unit
def test_parse_encrypted_pdf_raises() -> None:
    pdf_bytes = _create_sample_pdf("Secret text", password="my_password")
    with pytest.raises(ParseError, match="PDF is password-protected"):
        parse_document(pdf_bytes)


@pytest.mark.unit
def test_parse_low_text_density_sets_needs_ocr() -> None:
    # Very short text (< 20 chars per page threshold)
    pdf_bytes = _create_sample_pdf("Hi")
    parsed = parse_document(pdf_bytes)

    assert parsed.page_count == 1
    assert parsed.needs_ocr is True
