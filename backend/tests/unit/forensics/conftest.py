"""Shared fixtures and PDF builders for forensics unit tests."""

from __future__ import annotations

import pytest

from eval.synthetic import (
    make_active_content_pdf,
    make_embedded_images_pdf,
    make_filled_acroform_incremental_pdf,
    make_footnote_pdf,
    make_gdocs_like_pdf,
    make_hidden_text_pdf,
    make_incremental_pdf,
    make_linearized_pdf,
    make_metadata_pdf,
    make_mixed_fonts_pdf,
    make_ocr_scanned_pdf,
    make_pdf_with_form_fields,
    make_pdf_with_headers_footers,
    make_pdf_with_highlights,
    make_pdf_with_links,
    make_plain_pdf,
    make_resaved_pdf,
    make_scanned_pdf,
    make_signed_pdf,
    make_white_on_dark_header_pdf,
    make_word_like_pdf,
)

__all__ = [
    "make_active_content_pdf",
    "make_embedded_images_pdf",
    "make_filled_acroform_incremental_pdf",
    "make_footnote_pdf",
    "make_gdocs_like_pdf",
    "make_hidden_text_pdf",
    "make_incremental_pdf",
    "make_linearized_pdf",
    "make_metadata_pdf",
    "make_mixed_fonts_pdf",
    "make_ocr_scanned_pdf",
    "make_pdf_with_form_fields",
    "make_pdf_with_headers_footers",
    "make_pdf_with_highlights",
    "make_pdf_with_links",
    "make_plain_pdf",
    "make_resaved_pdf",
    "make_scanned_pdf",
    "make_signed_pdf",
    "make_white_on_dark_header_pdf",
    "make_word_like_pdf",
]


@pytest.fixture
def benign_plain_pdf() -> bytes:
    return make_plain_pdf()


@pytest.fixture
def benign_headers_footers_pdf() -> bytes:
    return make_pdf_with_headers_footers()


@pytest.fixture
def benign_links_pdf() -> bytes:
    return make_pdf_with_links()


@pytest.fixture
def benign_highlights_pdf() -> bytes:
    return make_pdf_with_highlights()


@pytest.fixture
def benign_form_fields_pdf() -> bytes:
    return make_pdf_with_form_fields()


@pytest.fixture
def benign_word_pdf() -> bytes:
    return make_word_like_pdf()


@pytest.fixture
def benign_gdocs_pdf() -> bytes:
    return make_gdocs_like_pdf()


@pytest.fixture
def benign_scanned_pdf() -> bytes:
    return make_scanned_pdf()


@pytest.fixture
def benign_mixed_fonts_pdf() -> bytes:
    return make_mixed_fonts_pdf()


@pytest.fixture
def benign_images_pdf() -> bytes:
    return make_embedded_images_pdf()


@pytest.fixture
def benign_filled_acroform_pdf() -> bytes:
    return make_filled_acroform_incremental_pdf()


@pytest.fixture
def benign_ocr_scanned_pdf() -> bytes:
    return make_ocr_scanned_pdf()


@pytest.fixture
def benign_white_on_dark_header_pdf() -> bytes:
    return make_white_on_dark_header_pdf()


@pytest.fixture
def benign_signed_pdf() -> bytes:
    return make_signed_pdf()


@pytest.fixture
def benign_linearized_pdf() -> bytes:
    return make_linearized_pdf()


@pytest.fixture
def benign_resaved_pdf() -> bytes:
    return make_resaved_pdf()


@pytest.fixture
def benign_footnote_pdf() -> bytes:
    return make_footnote_pdf()
