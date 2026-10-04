"""Shared fixtures and PDF builders for forensics unit tests."""

from __future__ import annotations

import pytest

from eval.synthetic import (
    make_active_content_pdf,
    make_embedded_images_pdf,
    make_gdocs_like_pdf,
    make_hidden_text_pdf,
    make_incremental_pdf,
    make_metadata_pdf,
    make_mixed_fonts_pdf,
    make_pdf_with_form_fields,
    make_pdf_with_headers_footers,
    make_pdf_with_highlights,
    make_pdf_with_links,
    make_plain_pdf,
    make_scanned_pdf,
    make_signed_pdf,
    make_word_like_pdf,
)

__all__ = [
    "make_active_content_pdf",
    "make_embedded_images_pdf",
    "make_gdocs_like_pdf",
    "make_hidden_text_pdf",
    "make_incremental_pdf",
    "make_metadata_pdf",
    "make_mixed_fonts_pdf",
    "make_pdf_with_form_fields",
    "make_pdf_with_headers_footers",
    "make_pdf_with_highlights",
    "make_pdf_with_links",
    "make_plain_pdf",
    "make_scanned_pdf",
    "make_signed_pdf",
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
