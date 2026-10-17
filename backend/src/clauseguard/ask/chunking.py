"""Retrieval unit chunking for ClauseGuard Ask.

Builds searchable retrieval chunks from parsed contracts:
- Normal clauses (<= 250 words): clause is the chunk.
- Long clauses (> 250 words): split into sliding 120-word windows with stride 100.
  Window boundaries avoid cutting sentences when possible. Overlap is ~20 words.
  Sub-chunks inherit parent clause_id, heading, and page span.
- Unsegmented documents: full text split into sliding 120-word windows with stride 100,
  page attributed from Page boundaries, assigned synthetic clause_id c1.w0, c1.w1, etc.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Sequence

WORD_RE = re.compile(r"\S+")
SENTENCE_END_RE = re.compile(r"[.!?](?:[\"')\]}]*)\s+")


@dataclass(frozen=True)
class RetrievalChunk:
    """A granular, searchable unit of evidence."""

    chunk_id: str
    clause_id: str
    heading: str | None
    text: str
    page_start: int
    page_end: int
    word_count: int
    char_start: int | None = None
    char_end: int | None = None


def _find_sentence_ends(text: str, words: list[re.Match]) -> set[int]:
    """Return the set of word indices (0-based) that terminate a sentence."""
    if not words:
        return set()

    sentence_end_word_indices: set[int] = set()
    # Find all sentence boundary matches
    for m in SENTENCE_END_RE.finditer(text):
        end_pos = m.start() + 1  # punctuation character position
        # Binary search or scan for the word token covering this punctuation
        # Since word matches are sorted, scan
        for idx, w in enumerate(words):
            if w.start() <= end_pos <= w.end():
                sentence_end_word_indices.add(idx)
                break
    return sentence_end_word_indices


def split_text_into_sentence_windows(
    text: str,
    target_words: int = 120,
    stride: int = 100,
    tolerance: int = 20,
) -> list[dict[str, Any]]:
    """Split text into sliding windows, snapping to sentence boundaries when possible.

    Returns a list of dicts with:
    - text: window text
    - start_word, end_word
    - start_char, end_char
    - word_count
    """
    cleaned = text.strip()
    if not cleaned:
        return []

    words = list(WORD_RE.finditer(cleaned))
    total_words = len(words)
    if total_words == 0:
        return []

    if total_words <= target_words:
        return [
            {
                "text": cleaned,
                "start_word": 0,
                "end_word": total_words,
                "start_char": 0,
                "end_char": len(cleaned),
                "word_count": total_words,
            }
        ]

    sentence_ends = _find_sentence_ends(cleaned, words)
    windows: list[dict[str, Any]] = []
    w_start = 0

    while w_start < total_words:
        ideal_end = min(w_start + target_words, total_words)

        if ideal_end >= total_words:
            chosen_end = total_words
        else:
            # Search for a sentence end around ideal_end within tolerance
            candidates = [
                idx
                for idx in sentence_ends
                if (ideal_end - tolerance) <= idx <= (ideal_end + tolerance) and idx > w_start + 40
            ]
            if candidates:
                # Pick the sentence end closest to ideal_end
                best_end = min(candidates, key=lambda idx: abs(idx - ideal_end))
                chosen_end = best_end + 1
            else:
                chosen_end = ideal_end

        start_char = words[w_start].start()
        end_char = words[chosen_end - 1].end()
        window_text = cleaned[start_char:end_char]

        windows.append(
            {
                "text": window_text,
                "start_word": w_start,
                "end_word": chosen_end,
                "start_char": start_char,
                "end_char": end_char,
                "word_count": chosen_end - w_start,
            }
        )

        if chosen_end >= total_words:
            break

        # Calculate next start with stride
        ideal_next_start = w_start + stride
        if ideal_next_start >= total_words:
            break

        # Check for sentence start near ideal_next_start within tolerance
        # A sentence starts at idx if idx - 1 is in sentence_ends
        next_candidates = [
            idx + 1
            for idx in sentence_ends
            if (ideal_next_start - tolerance) <= (idx + 1) <= (ideal_next_start + tolerance)
            and w_start < (idx + 1) < chosen_end
        ]
        if next_candidates:
            next_start = min(next_candidates, key=lambda idx: abs(idx - ideal_next_start))
        else:
            next_start = ideal_next_start

        if next_start <= w_start:
            next_start = w_start + max(1, stride)
        w_start = next_start

    return windows


def build_retrieval_chunks(
    clauses: Sequence[Any],
    pages: Sequence[Any] | None = None,
    max_words_threshold: int = 250,
    window_size: int = 120,
    stride: int = 100,
) -> list[RetrievalChunk]:
    """Build retrieval chunks from clauses and optional pages.

    - If no clauses or kind == 'unsegmented': splits document text into sentence windows.
    - If clauses exist:
      * Clause <= max_words_threshold: kept whole.
      * Clause > max_words_threshold: split into sliding windows.
    """
    # Check if unsegmented
    is_unsegmented = (
        not clauses
        or len(clauses) == 0
        or (len(clauses) == 1 and getattr(clauses[0], "kind", "") == "unsegmented")
        or all(getattr(c, "kind", "") == "unsegmented" for c in clauses)
    )

    # Build page boundaries if pages provided
    page_bounds: list[tuple[int, int, int]] = []  # (page_no, start_char, end_char)
    if pages:
        cur_offset = 0
        for p in pages:
            p_no = getattr(p, "page_no", 1)
            p_text = getattr(p, "text", "")
            p_len = len(p_text)
            page_bounds.append((p_no, cur_offset, cur_offset + p_len))
            cur_offset += p_len + 1  # 1 for newline separator

    def _attrib_page(start_c: int, end_c: int, fallback_start: int, fallback_end: int) -> tuple[int, int]:
        if not page_bounds:
            return fallback_start, fallback_end
        p_start = fallback_start
        p_end = fallback_end
        for p_no, b_start, b_end in page_bounds:
            if b_start <= start_c <= b_end:
                p_start = p_no
            if b_start <= end_c <= b_end:
                p_end = p_no
        return max(1, p_start), max(1, p_end)

    chunks: list[RetrievalChunk] = []

    if is_unsegmented:
        # Full text from pages or single unsegmented clause
        if pages:
            full_text = "\n".join(getattr(p, "text", "") for p in pages)
        elif clauses:
            full_text = getattr(clauses[0], "text", "")
        else:
            full_text = ""

        windows = split_text_into_sentence_windows(
            full_text, target_words=window_size, stride=stride
        )
        for idx, win in enumerate(windows):
            p_start, p_end = _attrib_page(win["start_char"], win["end_char"], 1, 1)
            chunk_id = f"c1.w{idx}"
            chunks.append(
                RetrievalChunk(
                    chunk_id=chunk_id,
                    clause_id="c1",
                    heading=None,
                    text=win["text"],
                    page_start=p_start,
                    page_end=p_end,
                    word_count=win["word_count"],
                    char_start=win["start_char"],
                    char_end=win["end_char"],
                )
            )
        return chunks

    # Process structured clauses
    for clause in clauses:
        c_id = str(getattr(clause, "clause_id", "c"))
        heading = getattr(clause, "heading", "") or None
        text = getattr(clause, "text", "") or ""
        p_start = getattr(clause, "page_start", 1) or 1
        p_end = getattr(clause, "page_end", 1) or 1
        words_count = len(WORD_RE.findall(text))

        if words_count <= max_words_threshold:
            chunks.append(
                RetrievalChunk(
                    chunk_id=c_id,
                    clause_id=c_id,
                    heading=heading,
                    text=text,
                    page_start=p_start,
                    page_end=p_end,
                    word_count=words_count,
                    char_start=getattr(clause, "char_start", None),
                    char_end=getattr(clause, "char_end", None),
                )
            )
        else:
            # Long clause: split into sliding windows
            windows = split_text_into_sentence_windows(
                text, target_words=window_size, stride=stride
            )
            for w_idx, win in enumerate(windows):
                sub_chunk_id = f"{c_id}.w{w_idx}"
                chunks.append(
                    RetrievalChunk(
                        chunk_id=sub_chunk_id,
                        clause_id=c_id,
                        heading=heading,
                        text=win["text"],
                        page_start=p_start,
                        page_end=p_end,
                        word_count=win["word_count"],
                        char_start=win["start_char"],
                        char_end=win["end_char"],
                    )
                )

    return chunks
