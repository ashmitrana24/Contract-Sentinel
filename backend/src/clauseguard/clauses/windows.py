"""Clause windowing and prediction aggregation.

Handles sliding windows for long clauses (>250 words) to ensure accurate classification
and localized evidence snippets without exceeding model capacity.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

WORD_RE = re.compile(r"\S+")
SENTENCE_END_RE = re.compile(r"[.!?]\s+")


@dataclass(frozen=True)
class ClauseWindow:
    """A sliding window of text from a clause."""

    window_index: int
    text: str
    start_word: int
    end_word: int
    start_char: int
    end_char: int


def split_clause_into_windows(
    clause_text: str,
    max_words_threshold: int = 250,
    window_size: int = 120,
    stride: int = 100,
) -> list[ClauseWindow]:
    """Split a clause into sliding windows.

    - If text has <= max_words_threshold words, returns a single window.
    - If > max_words_threshold, generates sliding windows of window_size words
      with the given stride (overlap = window_size - stride).
    """
    cleaned = clause_text.strip()
    if not cleaned:
        return []

    # Find word token spans
    matches = list(WORD_RE.finditer(cleaned))
    total_words = len(matches)

    if total_words == 0:
        return []

    if total_words <= max_words_threshold:
        return [
            ClauseWindow(
                window_index=0,
                text=cleaned,
                start_word=0,
                end_word=total_words,
                start_char=0,
                end_char=len(cleaned),
            )
        ]

    windows: list[ClauseWindow] = []
    idx = 0
    w_start = 0

    while w_start < total_words:
        w_end = min(w_start + window_size, total_words)

        start_char = matches[w_start].start()
        end_char = matches[w_end - 1].end()
        window_text = cleaned[start_char:end_char]

        windows.append(
            ClauseWindow(
                window_index=idx,
                text=window_text,
                start_word=w_start,
                end_word=w_end,
                start_char=start_char,
                end_char=end_char,
            )
        )
        idx += 1

        if w_end >= total_words:
            break
        w_start += stride

    return windows


def truncate_evidence(text: str, max_chars: int = 300) -> str:
    """Normalize whitespace and truncate evidence snippet to at most max_chars."""
    collapsed = " ".join(text.split()).strip()
    if len(collapsed) <= max_chars:
        return collapsed
    # Cut at last word boundary before max_chars - 3
    truncated = collapsed[: max_chars - 3]
    last_space = truncated.rfind(" ")
    if last_space > max_chars // 2:
        truncated = truncated[:last_space]
    return truncated + "..."


def aggregate_window_predictions(
    window_predictions: list[list[dict[str, Any]]],
    max_evidence_chars: int = 300,
) -> list[dict[str, Any]]:
    """Aggregate predictions across windows for a single clause.

    Takes a list of window predictions, where each item is a list of prediction dicts:
      {'label': str, 'score': float, 'method': str, 'evidence': str}

    Returns a deduplicated list of clause-level label dicts:
      - Score is max across windows.
      - Evidence is selected from the highest-scoring window for that label, truncated <= 300 chars.
      - Method combines methods ('rules', 'model', or 'both').
    """
    by_label: dict[str, dict[str, Any]] = {}

    for w_preds in window_predictions:
        for p in w_preds:
            label = p["label"]
            score = float(p.get("score", 0.0))
            method = p.get("method", "rules")
            evidence = p.get("evidence", "")

            if label not in by_label:
                by_label[label] = {
                    "label": label,
                    "score": score,
                    "method": method,
                    "evidence": evidence,
                }
            else:
                existing = by_label[label]
                # Merge methods
                methods = set()
                for m in (existing["method"], method):
                    if m == "both":
                        methods.update(["rules", "model"])
                    else:
                        methods.add(m)
                merged_method = "both" if ("rules" in methods and "model" in methods) else next(iter(methods))
                existing["method"] = merged_method

                # Update score and evidence if higher score
                if score > existing["score"]:
                    existing["score"] = score
                    existing["evidence"] = evidence

    # Format output
    results: list[dict[str, Any]] = []
    for item in by_label.values():
        results.append({
            "label": item["label"],
            "score": round(item["score"], 4),
            "method": item["method"],
            "evidence": truncate_evidence(item["evidence"], max_evidence_chars),
        })

    # Sort deterministically by descending score, then label name
    results.sort(key=lambda x: (-x["score"], x["label"]))
    return results
