"""CUAD data loader and clause alignment for Module 5 training/eval.

Loads CUAD v1 SQuAD-formatted dataset, segments contract texts into clauses
using Module 2's segment_clauses parser, and aligns expert ground-truth answer spans
to individual clauses using token overlap (>= 30% overlap threshold).
"""

from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from clauseguard.clauses.taxonomy import normalize_category_to_label
from clauseguard.clauses.training.split import DatasetSplit
from clauseguard.parsing.clauses import segment_clauses
from clauseguard.schemas.parsed import PageModel

logger = logging.getLogger(__name__)

WORD_RE = re.compile(r"\w+")

# Default cache paths
_HF_CACHE_ROOT = Path(os.path.expanduser("~")) / ".cache" / "huggingface" / "hub"
_SNAPSHOT_GLOB = "datasets--TheAtticusProject--cuad/snapshots/*/CUAD_v1/CUAD_v1.json"


@dataclass
class LabeledClause:
    """A segmented clause with aligned ground-truth labels."""

    contract_title: str
    clause_id: str
    heading: str
    text: str
    labels: set[str] = field(default_factory=set)
    answer_spans: list[dict[str, Any]] = field(default_factory=list)
    char_start: int = 0
    char_end: int = 0

    @property
    def is_positive(self) -> bool:
        return len(self.labels) > 0


def find_cuad_json_path(explicit_path: str | Path | None = None) -> Path:
    """Locate CUAD_v1.json on disk."""
    if explicit_path:
        p = Path(explicit_path)
        if p.exists():
            return p
        raise FileNotFoundError(f"CUAD file not found at: {explicit_path}")

    # Check local data dir
    local = Path("data/raw/cuad/CUAD_v1.json")
    if local.exists():
        return local

    # Check HuggingFace hub cache
    matches = list(_HF_CACHE_ROOT.glob(_SNAPSHOT_GLOB))
    if matches and matches[0].exists():
        return matches[0]

    # Check case-insensitive variant on Windows
    matches_ci = list(_HF_CACHE_ROOT.glob("datasets--theatticusproject--cuad/snapshots/*/CUAD_v1/CUAD_v1.json"))
    if matches_ci and matches_ci[0].exists():
        return matches_ci[0]

    raise FileNotFoundError(
        "Could not find CUAD_v1.json. Please ensure it is present in the HuggingFace cache or data/raw/cuad."
    )


def _chunk_raw_into_pages(raw: str, max_chars_per_page: int = 3000) -> list[PageModel]:
    """Chunk raw text into PageModels for segment_clauses."""
    pages: list[PageModel] = []
    lines: list[str] = []
    current_chars = 0

    for line in raw.splitlines(keepends=True):
        lines.append(line)
        current_chars += len(line)
        if current_chars >= max_chars_per_page:
            chunk = "".join(lines)
            pages.append(
                PageModel(
                    page_no=len(pages) + 1,
                    width=612.0,
                    height=792.0,
                    text=chunk,
                    char_count=len(chunk),
                )
            )
            lines = []
            current_chars = 0

    if lines:
        chunk = "".join(lines)
        pages.append(
            PageModel(
                page_no=len(pages) + 1,
                width=612.0,
                height=792.0,
                text=chunk,
                char_count=len(chunk),
            )
        )

    return pages


def load_cuad_raw(cuad_path: str | Path | None = None) -> list[dict[str, Any]]:
    """Load raw CUAD contracts list from JSON."""
    resolved_path = find_cuad_json_path(cuad_path)
    logger.info("Loading CUAD from: %s", resolved_path)
    with open(resolved_path, encoding="utf-8") as f:
        data = json.load(f)
    return data.get("data", [])


def extract_contract_clauses(
    contract_data: dict[str, Any],
) -> tuple[list[LabeledClause], int, int]:
    """Segment a CUAD contract and align expert annotations to clauses via character offsets.

    Returns:
      (labeled_clauses, total_answers_processed, aligned_answers_count)
    """
    title = contract_data.get("title", "")
    paragraphs = contract_data.get("paragraphs", [])
    if not paragraphs:
        return [], 0, 0

    context = paragraphs[0].get("context", "")
    pages = _chunk_raw_into_pages(context)
    raw_clauses = segment_clauses(pages)

    # Initialize LabeledClause objects with char_start and char_end
    clause_objs: list[LabeledClause] = []
    for c in raw_clauses:
        lc = LabeledClause(
            contract_title=title,
            clause_id=c.clause_id,
            heading=c.heading,
            text=c.text,
            char_start=c.char_start if c.char_start is not None else 0,
            char_end=c.char_end if c.char_end is not None else len(context),
        )
        clause_objs.append(lc)

    total_answers = 0
    aligned_answers = 0

    qas = paragraphs[0].get("qas", [])
    for qa in qas:
        qa_id = qa.get("id", "")
        category = qa_id.split("__")[-1] if "__" in qa_id else ""
        label = normalize_category_to_label(category)
        if label is None:
            # Metadata category (Party, Effective Date, etc.) or unrecognized
            continue

        for ans in qa.get("answers", []):
            ans_text = ans.get("text", "").strip()
            ans_start = ans.get("answer_start")
            if not ans_text or ans_start is None:
                continue

            total_answers += 1
            span_len = len(ans_text)

            # Verify the offset: context[ans_start:ans_start+len(ans_text)] == ans_text
            if context[ans_start : ans_start + span_len] != ans_text:
                found_idx = context.find(ans_text)
                if found_idx == -1:
                    norm_ans = " ".join(ans_text.split())
                    m = re.search(re.escape(norm_ans), context)
                    if m:
                        ans_start = m.start()
                        span_len = m.end() - m.start()
                    else:
                        continue
                else:
                    ans_start = found_idx

            ans_end = ans_start + span_len

            # Compute overlap of [ans_start, ans_end) with each clause [c.char_start, c.char_end)
            overlaps: list[tuple[int, int]] = []
            for i, c in enumerate(clause_objs):
                ov = max(0, min(ans_end, c.char_end) - max(ans_start, c.char_start))
                overlaps.append((ov, i))

            max_ov, best_idx = max(overlaps, key=lambda x: x[0])
            if max_ov == 0:
                continue

            aligned_answers += 1
            # Condition: at least 50% of the span's characters
            assigned = False
            for ov, idx in overlaps:
                if (ov / span_len) >= 0.50:
                    clause_objs[idx].labels.add(label)
                    clause_objs[idx].answer_spans.append({
                        "label": label,
                        "text": ans_text,
                        "answer_start": ans_start,
                        "overlap_chars": ov,
                        "span_len": span_len,
                    })
                    assigned = True

            # If a span crosses clauses and none reaches 50 percent, give it to the clause with the largest overlap
            if not assigned:
                clause_objs[best_idx].labels.add(label)
                clause_objs[best_idx].answer_spans.append({
                    "label": label,
                    "text": ans_text,
                    "answer_start": ans_start,
                    "overlap_chars": max_ov,
                    "span_len": span_len,
                })

    return clause_objs, total_answers, aligned_answers


def load_dataset_by_split(
    split: DatasetSplit,
    cuad_path: str | Path | None = None,
) -> tuple[list[LabeledClause], list[LabeledClause], list[LabeledClause]]:
    """Load and align clauses partitioned into (train_clauses, val_clauses, test_clauses).

    Test clauses should only be used during final benchmark evaluation!
    """
    raw_contracts = load_cuad_raw(cuad_path)

    train_clauses: list[LabeledClause] = []
    val_clauses: list[LabeledClause] = []
    test_clauses: list[LabeledClause] = []

    total_ans = 0
    aligned_ans = 0

    for doc in raw_contracts:
        title = doc.get("title", "")
        split_name = split.get_split(title)
        if split_name == "unknown":
            continue

        clauses, t_ans, a_ans = extract_contract_clauses(doc)
        total_ans += t_ans
        aligned_ans += a_ans

        if split_name == "train":
            train_clauses.extend(clauses)
        elif split_name == "val":
            val_clauses.extend(clauses)
        elif split_name == "test":
            test_clauses.extend(clauses)

    align_rate = (aligned_ans / total_ans * 100.0) if total_ans > 0 else 0.0
    logger.info(
        "CUAD alignment complete: %d/%d (%.2f%%) answer spans aligned to clauses.",
        aligned_ans,
        total_ans,
        align_rate,
    )
    logger.info(
        "Clauses: train=%d, val=%d, test=%d",
        len(train_clauses),
        len(val_clauses),
        len(test_clauses),
    )

    return train_clauses, val_clauses, test_clauses
