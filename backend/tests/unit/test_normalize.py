"""Unit tests for text normalization."""

from __future__ import annotations

import unicodedata

import pytest

from clauseguard.parsing.normalize import normalize_text


@pytest.mark.unit
def test_normalize_unicode_nfc() -> None:
    """Combining character forms normalized to NFC."""
    # 'e' + combining acute accent -> single character 'é'
    decomposed = "e\u0301"
    normalized = normalize_text(decomposed)
    assert normalized == "é"
    assert unicodedata.is_normalized("NFC", normalized)


@pytest.mark.unit
def test_normalize_invisible_characters() -> None:
    """Zero-width spaces and invisible characters removed."""
    raw = "Hello\u200bWorld\ufeff!\u200c"
    assert normalize_text(raw) == "HelloWorld!"


@pytest.mark.unit
def test_normalize_non_breaking_spaces() -> None:
    """Non-breaking spaces converted to standard spaces."""
    raw = "Section\u00a01.1\u202fDefinitions"
    assert normalize_text(raw) == "Section 1.1 Definitions"


@pytest.mark.unit
def test_normalize_collapses_whitespace_preserves_newlines() -> None:
    """Intra-line spaces collapsed but newlines preserved without dehyphenation."""
    raw = "Line   one   with   spaces.\nLine-two   is   here.\n\nLine   three."
    expected = "Line one with spaces.\nLine-two is here.\n\nLine three."
    assert normalize_text(raw) == expected
