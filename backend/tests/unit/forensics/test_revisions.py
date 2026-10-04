"""Unit tests for PDF revision finder (forensics.revisions)."""

import pytest

from clauseguard.forensics.revisions import find_valid_revisions
from tests.unit.forensics.conftest import make_incremental_pdf, make_plain_pdf

pytestmark = pytest.mark.unit


def test_single_revision_clean_pdf():
    pdf_bytes = make_plain_pdf(num_pages=2)
    revs = find_valid_revisions(pdf_bytes)
    assert len(revs) == 1
    assert revs[0].index == 0
    assert revs[0].start_offset == 0
    assert revs[0].end_offset == len(pdf_bytes)


def test_multi_revision_incremental_pdf():
    pdf_bytes = make_incremental_pdf(edit_text=True)
    revs = find_valid_revisions(pdf_bytes)
    assert len(revs) >= 2
    for i, r in enumerate(revs):
        assert r.index == i
        assert len(r.bytes_slice) > 0


def test_trailing_garbage_after_eof():
    base = make_plain_pdf()
    corrupted = base + b"\n% Some random garbage added to the end of the file\n"
    revs = find_valid_revisions(corrupted)
    assert len(revs) >= 1
    # End offset should align with the legitimate %%EOF
    assert revs[0].end_offset <= len(base) + 10


def test_empty_or_invalid_bytes():
    assert find_valid_revisions(b"") == []
    assert find_valid_revisions(b"Not a PDF file at all") == []
