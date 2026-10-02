"""End-to-end pipeline + determinism tests."""

from __future__ import annotations

import json
from pathlib import Path

from datagen.pipeline import run_pipeline
from datagen.split import assign_splits


def test_pipeline_small(tmp_path: Path) -> None:
    """Generate 6 source contracts; check we get at least 6 docs."""
    labels = run_pipeline(seed=42, n_sources=6, out_dir=tmp_path)
    assert len(labels) >= 6  # at least 1 clean per source


def test_pipeline_labels_jsonl_exists(tmp_path: Path) -> None:
    run_pipeline(seed=42, n_sources=6, out_dir=tmp_path)
    assert (tmp_path / "labels.jsonl").exists()
    assert (tmp_path / "labels.json").exists()


def test_pipeline_pdfs_exist(tmp_path: Path) -> None:
    labels = run_pipeline(seed=42, n_sources=6, out_dir=tmp_path)
    for lbl in labels:
        assert (tmp_path / f"{lbl.doc_id}.pdf").exists()


def test_pipeline_sha256_matches(tmp_path: Path) -> None:
    import hashlib

    labels = run_pipeline(seed=42, n_sources=6, out_dir=tmp_path)
    for lbl in labels:
        pdf_path = tmp_path / f"{lbl.doc_id}.pdf"
        actual = hashlib.sha256(pdf_path.read_bytes()).hexdigest()
        assert actual == lbl.sha256, f"SHA256 mismatch for {lbl.doc_id}"


def test_pipeline_deterministic_labels(tmp_path: Path) -> None:
    """Two runs with same seed produce identical structural labels.

    Note: file-level tampers (hidden_text, incremental_edit) use PyMuPDF
    which may embed non-deterministic internal timestamps, causing different
    sha256 values across separate Python processes. We therefore compare the
    structural fields (doc_id, source_id, tamper_types) rather than sha256.
    See DECISIONS.md D-01.
    """

    out1 = tmp_path / "run1"
    out2 = tmp_path / "run2"
    run_pipeline(seed=42, n_sources=6, out_dir=out1)
    run_pipeline(seed=42, n_sources=6, out_dir=out2)

    lines1 = (out1 / "labels.jsonl").read_text().splitlines()
    lines2 = (out2 / "labels.jsonl").read_text().splitlines()
    assert len(lines1) == len(lines2), "Different number of labels produced"

    for l1_str, l2_str in zip(lines1, lines2, strict=True):
        d1 = json.loads(l1_str)
        d2 = json.loads(l2_str)
        assert d1["doc_id"] == d2["doc_id"]
        assert d1["source_id"] == d2["source_id"]
        assert d1["tamper_types"] == d2["tamper_types"]
        assert d1["is_tampered"] == d2["is_tampered"]
        assert d1["source_type"] == d2["source_type"]


def test_pipeline_deterministic_pdf_text(tmp_path: Path) -> None:
    """Same seed → same extracted text per doc_id."""
    import pymupdf as fitz

    out1 = tmp_path / "run1"
    out2 = tmp_path / "run2"
    labels1 = run_pipeline(seed=42, n_sources=4, out_dir=out1)
    labels2 = run_pipeline(seed=42, n_sources=4, out_dir=out2)

    for l1, l2 in zip(labels1, labels2, strict=True):
        assert l1.doc_id == l2.doc_id
        p1 = out1 / f"{l1.doc_id}.pdf"
        p2 = out2 / f"{l2.doc_id}.pdf"
        doc1 = fitz.open(str(p1))
        doc2 = fitz.open(str(p2))
        try:
            t1 = "".join(pg.get_text() for pg in doc1)
            t2 = "".join(pg.get_text() for pg in doc2)
        finally:
            doc1.close()
            doc2.close()
        assert t1 == t2, f"Text differs for {l1.doc_id}"


def test_pipeline_different_seeds_differ(tmp_path: Path) -> None:
    out1 = tmp_path / "s1"
    out2 = tmp_path / "s2"
    l1 = run_pipeline(seed=1, n_sources=6, out_dir=out1)
    l2 = run_pipeline(seed=2, n_sources=6, out_dir=out2)
    sha_set1 = {lbl.sha256 for lbl in l1}
    sha_set2 = {lbl.sha256 for lbl in l2}
    # Different seeds should produce at least some different PDFs
    assert sha_set1 != sha_set2


def test_pipeline_split_no_leakage(tmp_path: Path) -> None:
    from collections import defaultdict

    labels = run_pipeline(seed=42, n_sources=10, out_dir=tmp_path)
    assign_splits(labels, seed=42)
    source_splits: dict[str, set[str]] = defaultdict(set)
    for lbl in labels:
        source_splits[lbl.source_id].add(lbl.split)
    for src, splits in source_splits.items():
        assert len(splits) == 1, f"Leakage: source {src!r} in {splits}"


def test_pipeline_verify(tmp_path: Path) -> None:
    """Full end-to-end: generate small dataset, then run verifier."""
    from datagen.pipeline import _write_labels
    from datagen.split import assign_splits
    from datagen.verify import verify_dataset

    labels = run_pipeline(seed=42, n_sources=6, out_dir=tmp_path)
    assign_splits(labels, seed=42)
    _write_labels(labels, tmp_path)
    result = verify_dataset(tmp_path)
    assert result, "Verifier failed on freshly generated dataset."
