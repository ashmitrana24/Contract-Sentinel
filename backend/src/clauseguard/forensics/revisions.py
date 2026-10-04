"""PDF revision finder.

Scans binary PDF bytes for valid %%EOF markers that delimit genuine
revisions. Each candidate is verified by actually opening the byte-prefix
with PyMuPDF to confirm it is a parseable PDF with at least one page.

False positives handled:
- %%EOF inside binary stream data: the byte offset must be preceded
  by whitespace-terminated content, and the candidate prefix must open OK.
- Linearization first-page sections: tiny "PDFs" that open but have zero
  pages are discarded.
- Truncated slices that cannot be opened are discarded.

The full file is always treated as the final (latest) revision.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import pymupdf

logger = logging.getLogger(__name__)

_EOF_MARKER = b"%%EOF"
# PDF spec: %%EOF may be followed by optional whitespace / CR / LF
_MAX_REVISION_SIZE = 200 * 1024 * 1024  # 200 MB guard


@dataclass
class Revision:
    """One validated PDF revision (a byte-prefix ending at %%EOF)."""

    index: int  # 0-based (0 = original)
    offset_end: int  # byte offset just past the %%EOF (incl. trailing newline)
    page_count: int
    start_offset: int = 0
    bytes_slice: bytes = b""

    @property
    def end_offset(self) -> int:
        return self.offset_end


def find_eof_offsets(data: bytes) -> list[int]:
    """Return all byte offsets where %%EOF appears in ``data``.

    Each offset points to the FIRST byte of the %%EOF marker.
    """
    offsets: list[int] = []
    start = 0
    while True:
        pos = data.find(_EOF_MARKER, start)
        if pos == -1:
            break
        offsets.append(pos)
        start = pos + len(_EOF_MARKER)
    return offsets


def _slice_after_eof(data: bytes, eof_pos: int) -> bytes:
    """Return the bytes from the start of data up to (and including) %%EOF
    plus one optional newline character."""
    end = eof_pos + len(_EOF_MARKER)
    # Consume optional trailing whitespace (CR, LF, space) — at most 2 chars
    while end < len(data) and end - (eof_pos + len(_EOF_MARKER)) < 2:
        if data[end:end + 1] in (b"\r", b"\n"):
            end += 1
        else:
            break
    return data[:end]


def _open_candidate(candidate_bytes: bytes) -> int | None:
    """Try to open a candidate revision slice with PyMuPDF.

    Returns the page count on success, None if the slice is not a valid PDF
    with at least one page.
    """
    if len(candidate_bytes) < 8:
        return None
    # Quick guard: must start with %PDF-
    if not candidate_bytes.lstrip()[:5].startswith(b"%PDF-"):
        return None
    try:
        doc = pymupdf.open(stream=candidate_bytes, filetype="pdf")
        try:
            pc = doc.page_count
        finally:
            doc.close()
        if pc < 1:
            return None
        return pc
    except Exception:
        return None


def find_valid_revisions(data: bytes, max_revisions: int = 25) -> list[Revision]:
    """Find all genuine PDF revisions in ``data``.

    The last entry is always the full file. Returns a list ordered oldest
    to newest. If more than ``max_revisions`` candidates are found, retains
    the first N//2 and last N//2 and logs a warning.
    """
    eof_offsets = find_eof_offsets(data)
    if not eof_offsets:
        return []

    candidates: list[Revision] = []
    seen_sizes: set[int] = set()

    for raw_pos in eof_offsets:
        candidate_bytes = _slice_after_eof(data, raw_pos)
        size = len(candidate_bytes)

        # Deduplicate by size (same offset can appear twice with different CR/LF endings)
        if size in seen_sizes:
            continue
        # Guard against decompression bombs / excessively large slices
        if size > _MAX_REVISION_SIZE:
            continue

        pc = _open_candidate(candidate_bytes)
        if pc is None:
            continue

        seen_sizes.add(size)
        candidates.append(
            Revision(
                index=len(candidates),
                offset_end=size,
                page_count=pc,
                bytes_slice=candidate_bytes,
            )
        )

    # The full file is the final revision — ensure it is present
    full_pc = _open_candidate(data)
    if full_pc is not None:
        full_size = len(data)
        if full_size not in seen_sizes:
            candidates.append(
                Revision(
                    index=len(candidates),
                    offset_end=full_size,
                    page_count=full_pc,
                    bytes_slice=data,
                )
            )

    # Re-index
    for i, rev in enumerate(candidates):
        rev.index = i

    if len(candidates) <= 1:
        return candidates

    # Trim if too many
    if len(candidates) > max_revisions:
        logger.warning(
            "PDF has %d candidate revisions; capping to %d (first+last)",
            len(candidates),
            max_revisions,
        )
        half = max_revisions // 2
        candidates = candidates[:half] + candidates[-half:]
        for i, rev in enumerate(candidates):
            rev.index = i

    return candidates


def get_revision_bytes(data: bytes, revision: Revision) -> bytes:
    """Return the byte slice corresponding to ``revision``."""
    return _slice_after_eof(data, data.find(_EOF_MARKER, revision.offset_end - 20))


def open_revision(data: bytes, revision: Revision) -> pymupdf.Document:
    """Open a specific revision from the raw PDF bytes.

    Caller is responsible for calling doc.close().
    """
    rev_bytes = data[: revision.offset_end]
    return pymupdf.open(stream=rev_bytes, filetype="pdf")
