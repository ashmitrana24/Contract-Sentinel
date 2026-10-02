"""Train/val/test split by source contract (70/15/15).

Splits are assigned deterministically by seed. All variants of one
source contract land in the same split (no leakage). The split
distribution is balanced as closely as possible across tamper types.
"""

from __future__ import annotations

import logging
import random
from collections import defaultdict

from datagen.models import DocLabel

logger = logging.getLogger(__name__)

TRAIN_FRAC = 0.70
VAL_FRAC = 0.15
TEST_FRAC = 0.15


def assign_splits(labels: list[DocLabel], seed: int) -> list[DocLabel]:
    """Assign 'split' field to each label in-place.

    All documents sharing a source_id get the same split.
    Returns the same list (modified in-place).
    """
    # Group by source_id
    source_ids = sorted({lbl.source_id for lbl in labels})
    rng = random.Random(seed)
    rng.shuffle(source_ids)

    n = len(source_ids)
    n_train = max(1, round(n * TRAIN_FRAC))
    n_val = max(1, round(n * VAL_FRAC))
    # remainder goes to test
    n_test = n - n_train - n_val

    if n_test < 1:
        # Give test at least 1 source
        n_val -= 1
        n_test = 1

    split_map: dict[str, str] = {}
    for sid in source_ids[:n_train]:
        split_map[sid] = "train"
    for sid in source_ids[n_train : n_train + n_val]:
        split_map[sid] = "val"
    for sid in source_ids[n_train + n_val :]:
        split_map[sid] = "test"

    for lbl in labels:
        lbl.split = split_map.get(lbl.source_id, "train")

    _log_split_stats(labels)
    return labels


def _log_split_stats(labels: list[DocLabel]) -> None:
    """Log split counts and tamper type distributions."""
    split_counts: dict[str, int] = defaultdict(int)
    tamper_counts: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))

    for lbl in labels:
        split_counts[lbl.split] += 1
        for tt in lbl.tamper_types:
            tamper_counts[lbl.split][tt.value] += 1

    for split in ["train", "val", "test"]:
        logger.info(
            "Split %s: %d docs, tampers: %s",
            split,
            split_counts[split],
            dict(tamper_counts[split]),
        )


def split_stats(labels: list[DocLabel]) -> dict[str, dict]:
    """Return a structured stats dict for CLI reporting."""
    result: dict[str, dict] = {}
    for split in ["train", "val", "test"]:
        split_labels = [lbl for lbl in labels if lbl.split == split]
        sources = {lbl.source_id for lbl in split_labels}
        tamper_dist: dict[str, int] = defaultdict(int)
        source_types: dict[str, int] = defaultdict(int)
        for lbl in split_labels:
            source_types[lbl.source_type.value] += 1
            for tt in lbl.tamper_types:
                tamper_dist[tt.value] += 1
        result[split] = {
            "n_docs": len(split_labels),
            "n_sources": len(sources),
            "n_clean": sum(1 for lbl in split_labels if not lbl.is_tampered),
            "n_tampered": sum(1 for lbl in split_labels if lbl.is_tampered),
            "source_types": dict(source_types),
            "tamper_distribution": dict(tamper_dist),
        }
    return result
