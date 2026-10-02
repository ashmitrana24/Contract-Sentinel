"""Tests for the verifier."""

from __future__ import annotations

from pathlib import Path

from datagen.pipeline import _write_labels, run_pipeline
from datagen.split import assign_splits
from datagen.verify import verify_dataset


def test_verifier_passes_clean_dataset(tmp_path: Path) -> None:
    labels = run_pipeline(seed=42, n_sources=4, out_dir=tmp_path)
    assign_splits(labels, seed=42)
    _write_labels(labels, tmp_path)
    ok = verify_dataset(tmp_path)
    assert ok


def test_verifier_fails_on_missing_pdf(tmp_path: Path) -> None:
    labels = run_pipeline(seed=42, n_sources=4, out_dir=tmp_path)
    assign_splits(labels, seed=42)
    _write_labels(labels, tmp_path)
    # Delete one clean PDF
    clean_labels = [lbl for lbl in labels if not lbl.is_tampered]
    pdf_to_delete = tmp_path / f"{clean_labels[0].doc_id}.pdf"
    pdf_to_delete.unlink()
    ok = verify_dataset(tmp_path)
    assert not ok


def test_verifier_fails_on_bad_sha256(tmp_path: Path) -> None:
    labels = run_pipeline(seed=42, n_sources=4, out_dir=tmp_path)
    assign_splits(labels, seed=42)
    # Corrupt the sha256 of one label
    labels[0].sha256 = "0" * 64
    _write_labels(labels, tmp_path)
    ok = verify_dataset(tmp_path)
    assert not ok


def test_verifier_no_labels_file(tmp_path: Path) -> None:
    ok = verify_dataset(tmp_path)
    assert not ok
