"""Unit tests for retrieval unit chunking and needle recall on unsegmented contracts."""

from __future__ import annotations

import math
import re
from typing import Any

import pytest

from clauseguard.ask.chunking import (
    RetrievalChunk,
    build_retrieval_chunks,
    split_text_into_sentence_windows,
)


class SimpleBM25:
    """Standard BM25Okapi for testing retrieval recall."""

    def __init__(self, chunks: list[RetrievalChunk], k1: float = 1.5, b: float = 0.75):
        self.chunks = chunks
        self.k1 = k1
        self.b = b
        self.doc_tokens = [self._tokenize(c.text) for c in chunks]
        self.doc_lens = [len(toks) for toks in self.doc_tokens]
        self.avgdl = sum(self.doc_lens) / max(1, len(self.doc_lens))
        self.N = len(chunks)

        # Inverted index: term -> list of (doc_idx, freq)
        self.df: dict[str, int] = {}
        self.tf: list[dict[str, int]] = []
        for toks in self.doc_tokens:
            counts: dict[str, int] = {}
            for t in toks:
                counts[t] = counts.get(t, 0) + 1
            self.tf.append(counts)
            for t in counts:
                self.df[t] = self.df.get(t, 0) + 1

        self.idf: dict[str, float] = {}
        for term, freq in self.df.items():
            self.idf[term] = math.log((self.N - freq + 0.5) / (freq + 0.5) + 1.0)

    @staticmethod
    def _tokenize(text: str) -> list[str]:
        return re.findall(r"\w+", text.lower())

    def search(self, query: str, top_k: int = 3) -> list[tuple[RetrievalChunk, float]]:
        q_tokens = self._tokenize(query)
        scores: list[float] = [0.0] * self.N

        for q in q_tokens:
            if q not in self.idf:
                continue
            idf_val = self.idf[q]
            for i in range(self.N):
                freq = self.tf[i].get(q, 0)
                if freq > 0:
                    numerator = freq * (self.k1 + 1.0)
                    denominator = freq + self.k1 * (1.0 - self.b + self.b * (self.doc_lens[i] / self.avgdl))
                    scores[i] += idf_val * (numerator / denominator)

        ranked = sorted(enumerate(scores), key=lambda x: x[1], reverse=True)
        return [(self.chunks[idx], score) for idx, score in ranked[:top_k] if score > 0]


class DummyClause:
    def __init__(
        self,
        clause_id: str,
        text: str,
        heading: str | None = None,
        page_start: int = 1,
        page_end: int = 1,
        kind: str = "clause",
    ):
        self.clause_id = clause_id
        self.text = text
        self.heading = heading
        self.page_start = page_start
        self.page_end = page_end
        self.kind = kind


class DummyPage:
    def __init__(self, page_no: int, text: str):
        self.page_no = page_no
        self.text = text


def test_short_clause_not_split() -> None:
    clause = DummyClause("1.1", "This is a short clause of thirty words. " * 3, heading="Short")
    chunks = build_retrieval_chunks([clause])
    assert len(chunks) == 1
    assert chunks[0].chunk_id == "1.1"
    assert chunks[0].clause_id == "1.1"
    assert chunks[0].heading == "Short"


def test_long_clause_split_into_windows_with_overlap() -> None:
    # 350 words across 10 distinct sentences
    sentences = [
        f"This is sentence number {i} detailing certain responsibilities and legal obligations of the parties."
        for i in range(1, 28)
    ]
    long_text = " ".join(sentences)
    words_count = len(re.findall(r"\S+", long_text))
    assert words_count > 250

    clause = DummyClause("4.2", long_text, heading="Long Obligations", page_start=2, page_end=3)
    chunks = build_retrieval_chunks([clause])

    assert len(chunks) > 1
    for idx, c in enumerate(chunks):
        assert c.chunk_id == f"4.2.w{idx}"
        assert c.clause_id == "4.2"
        assert c.heading == "Long Obligations"
        assert c.page_start == 2
        assert c.page_end == 3
        assert c.word_count <= 160


def test_unsegmented_30000_char_contract_chunking_and_needle_recall() -> None:
    # Build realistic legal boilerplate sentences
    boilerplate = [
        "The Vendor agrees to provide continuous maintenance and support for all licensed products.",
        "Either party may terminate this agreement upon sixty days prior written notice to the other party.",
        "All confidential information disclosed under this agreement shall remain strictly protected for five years.",
        "The receiving party shall not disclose proprietary technical data without prior authorization.",
        "Payment for all authorized deliverables shall be made within thirty days of invoice presentation.",
        "Except as otherwise provided herein, each party shall bear its own expenses in connection with performance.",
        "No failure or delay by either party in exercising any right or power hereunder shall operate as a waiver.",
        "This contract represents the entire agreement between the parties and supersedes all prior negotiations.",
    ]

    target_chars = 30000
    doc_sentences: list[str] = []
    current_len = 0
    i = 0
    while current_len < target_chars:
        sent = boilerplate[i % len(boilerplate)] + f" (Reference section counter {i})."
        doc_sentences.append(sent)
        current_len += len(sent) + 1
        i += 1

    # Place synthetic needles
    needle_50_idx = len(doc_sentences) // 2
    needle_50_text = (
        "The maximum allowable penalty for late delivery under Exhibit B shall strictly "
        "not exceed twenty thousand dollars ($20,000)."
    )
    doc_sentences.insert(needle_50_idx, needle_50_text)

    needle_95_idx = int(len(doc_sentences) * 0.95)
    needle_95_text = (
        "Any disputes arising under Section 19 shall be subject to binding arbitration "
        "administered in Singapore under SIAC Rules."
    )
    doc_sentences.insert(needle_95_idx, needle_95_text)

    full_contract_text = " ".join(doc_sentences)
    assert len(full_contract_text) >= 30000

    # Build 3 pages of ~10,000 chars each
    p1_len = len(full_contract_text) // 3
    p2_len = (len(full_contract_text) * 2) // 3
    pages = [
        DummyPage(1, full_contract_text[:p1_len]),
        DummyPage(2, full_contract_text[p1_len:p2_len]),
        DummyPage(3, full_contract_text[p2_len:]),
    ]

    # Feed unsegmented contract
    unsegmented_clause = DummyClause("U", full_contract_text, kind="unsegmented")
    chunks = build_retrieval_chunks([unsegmented_clause], pages=pages)

    # 1. Verify chunk formatting and properties
    assert len(chunks) > 10
    for idx, chunk in enumerate(chunks):
        assert chunk.clause_id == "c1"
        assert chunk.chunk_id == f"c1.w{idx}"
        assert 1 <= chunk.page_start <= 3
        assert 1 <= chunk.page_end <= 3
        assert chunk.word_count > 0

    # 2. Verify window overlap and sentence boundaries
    for i in range(len(chunks) - 1):
        c1 = chunks[i]
        c2 = chunks[i + 1]
        c1_words = c1.text.split()
        c2_words = c2.text.split()
        # Overlap check
        overlap_words = len(set(c1_words[-30:]).intersection(set(c2_words[:30])))
        assert overlap_words >= 5, f"Expected overlap between window {i} and {i+1}, got {overlap_words}"
        # Sentence boundary check: verify chunk ends cleanly with sentence punctuation
        assert c1.text.rstrip()[-1] in ".!?", f"Chunk {i} does not end with sentence punctuation: ...{c1.text[-30:]}"

    # 3. Measure top-3 BM25 recall for needles
    bm25 = SimpleBM25(chunks)

    # Query 50% needle
    q50 = "What is the maximum allowable penalty for late delivery under Exhibit B?"
    top_q50 = bm25.search(q50, top_k=3)
    found_50 = any("twenty thousand dollars" in c.text for c, _score in top_q50)
    assert found_50, "Needle at 50% not found in top-3 BM25 results!"

    # Query 95% needle
    q95 = "Where is binding arbitration administered for Section 19 disputes under SIAC Rules?"
    top_q95 = bm25.search(q95, top_k=3)
    found_95 = any("Singapore under SIAC Rules" in c.text for c, _score in top_q95)
    assert found_95, "Needle at 95% not found in top-3 BM25 results!"

    recall = (int(found_50) + int(found_95)) / 2.0
    assert recall == 1.0, f"Recall was {recall}, expected 1.0"
    print(f"\n[A4 Measure] Unsegmented 30,000-char contract chunks: {len(chunks)}, Recall@3: {recall:.1%}")
