"""Tests for the split module."""

from __future__ import annotations

from collections import defaultdict

from datagen.models import DocLabel, SourceType
from datagen.split import assign_splits


def _make_labels(n_sources: int, seed: int = 42) -> list[DocLabel]:
    """Create a synthetic set of labels for testing splits."""
    labels: list[DocLabel] = []
    for i in range(n_sources):
        source_id = f"src_{i:04d}"
        # 1 clean + 2 tampered per source
        for j in range(3):
            labels.append(
                DocLabel(
                    doc_id=f"{source_id}_v{j}",
                    source_id=source_id,
                    source_type=SourceType.SYNTHETIC,
                    is_tampered=(j > 0),
                    seed=seed,
                    generator_version="datagen-0.1.0",
                )
            )
    return labels


def test_split_assigns_all(tmp_path) -> None:
    labels = _make_labels(30)
    assign_splits(labels, seed=42)
    assert all(lbl.split in {"train", "val", "test"} for lbl in labels)


def test_split_no_source_leakage() -> None:
    """No source_id should appear in more than one split."""
    labels = _make_labels(50)
    assign_splits(labels, seed=42)
    source_splits: dict[str, set[str]] = defaultdict(set)
    for lbl in labels:
        source_splits[lbl.source_id].add(lbl.split)
    for src, splits in source_splits.items():
        assert len(splits) == 1, f"Source {src!r} leaks across splits: {splits}"


def test_split_proportions() -> None:
    labels = _make_labels(100)
    assign_splits(labels, seed=42)
    split_counts = defaultdict(int)
    for lbl in labels:
        split_counts[lbl.split] += 1
    total = len(labels)
    # train should be ~70%, val ~15%, test ~15%
    assert 0.60 <= split_counts["train"] / total <= 0.80
    assert 0.08 <= split_counts["val"] / total <= 0.25
    assert 0.08 <= split_counts["test"] / total <= 0.25


def test_split_deterministic() -> None:
    labels1 = _make_labels(40)
    labels2 = _make_labels(40)
    assign_splits(labels1, seed=99)
    assign_splits(labels2, seed=99)
    for l1, l2 in zip(labels1, labels2, strict=True):
        assert l1.split == l2.split


def test_split_different_seeds_differ() -> None:
    labels1 = _make_labels(40)
    labels2 = _make_labels(40)
    assign_splits(labels1, seed=1)
    assign_splits(labels2, seed=2)
    # With 40 sources and different seeds, at least some assignments will differ
    diffs = sum(l1.split != l2.split for l1, l2 in zip(labels1, labels2, strict=True))
    assert diffs > 0


def test_split_all_splits_non_empty() -> None:
    labels = _make_labels(10)  # small dataset - still needs 3 splits
    assign_splits(labels, seed=42)
    splits = {lbl.split for lbl in labels}
    assert "train" in splits
    assert "val" in splits
    assert "test" in splits
