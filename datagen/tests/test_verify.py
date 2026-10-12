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


def test_verifier_fails_on_wrong_clause_id(tmp_path: Path) -> None:
    labels = run_pipeline(seed=42, n_sources=4, out_dir=tmp_path)
    assign_splits(labels, seed=42)
    # Find a tampered document with a clause_id
    tampered = [lbl for lbl in labels if lbl.is_tampered and lbl.tamper_details]
    assert tampered, "Should have tampered documents"
    target_lbl = None
    target_detail = None
    for lbl in tampered:
        for d in lbl.tamper_details:
            if d.clause_id and d.tampered_value:
                target_lbl = lbl
                target_detail = d
                break
        if target_lbl:
            break
    assert target_lbl and target_detail, "Should have a detail with clause_id"

    # Corrupt clause_id to a non-matching clause
    target_detail.clause_id = "99"
    _write_labels(labels, tmp_path)
    ok = verify_dataset(tmp_path)
    assert not ok, "Verifier must fail when label clause_id does not match actual clause in PDF"


def test_verifier_fails_on_wrong_page(tmp_path: Path) -> None:
    labels = run_pipeline(seed=42, n_sources=4, out_dir=tmp_path)
    assign_splits(labels, seed=42)
    tampered = [lbl for lbl in labels if lbl.is_tampered and lbl.tamper_details]
    assert tampered, "Should have tampered documents"
    target_lbl = None
    target_detail = None
    for lbl in tampered:
        for d in lbl.tamper_details:
            if d.tampered_value:
                target_lbl = lbl
                target_detail = d
                break
        if target_lbl:
            break
    assert target_lbl and target_detail

    # Corrupt page to an out-of-bounds or wrong page
    target_detail.page = 99
    _write_labels(labels, tmp_path)
    ok = verify_dataset(tmp_path)
    assert not ok, "Verifier must fail when label page does not match where text appears"

