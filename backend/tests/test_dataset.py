"""Dataset validation tests against generated contract PDFs.

Marked 'dataset'. Skipped with explicit reason if data/generated is absent.
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

import pytest

from clauseguard.parsing.parse_document import parse_document


def _find_dataset_dir() -> Path | None:
    candidates = [
        Path("data/generated"),
        Path("../data/generated"),
        Path("datagen/data/generated"),
        Path("../datagen/data/generated"),
    ]
    for c in candidates:
        if c.exists() and (c / "labels.jsonl").exists():
            return c.resolve()
    return None


DATASET_DIR = _find_dataset_dir()


@pytest.mark.dataset
@pytest.mark.skipif(DATASET_DIR is None, reason="data/generated dataset not present")
def test_dataset_clean_clause_recovery() -> None:
    """Test clause-id recovery >= 95% on clean synthetic documents."""
    assert DATASET_DIR is not None
    labels_file = DATASET_DIR / "labels.jsonl"
    labels = [json.loads(line) for line in labels_file.read_text(encoding="utf-8").splitlines() if line.strip()]

    # Load expected clauses if sidecar exists
    expected_clauses_file = DATASET_DIR / "expected_clauses.json"
    expected_clauses_map: dict[str, list[dict]] = {}
    if expected_clauses_file.exists():
        expected_clauses_map = json.loads(expected_clauses_file.read_text(encoding="utf-8"))

    clean_labels = [lbl for lbl in labels if not lbl.get("is_tampered", False)]
    assert len(clean_labels) > 0, "No clean documents found in dataset"

    source_recovery: dict[str, list[float]] = defaultdict(list)

    for lbl in clean_labels:
        doc_id = lbl["doc_id"]
        source_type = lbl.get("source_type", "synthetic")
        pdf_path = DATASET_DIR / f"{doc_id}.pdf"
        assert pdf_path.exists(), f"PDF missing: {pdf_path}"

        pdf_bytes = pdf_path.read_bytes()
        parsed = parse_document(pdf_bytes)

        # Assert document parses and has text
        assert parsed.page_count > 0
        total_text = "".join(p.text for p in parsed.pages)
        assert len(total_text.strip()) > 50

        # Compute clause recovery if ground-truth is available
        expected = expected_clauses_map.get(doc_id)
        if expected:
            expected_ids = {c["id"] for c in expected}
            parsed_ids = {c.clause_id for c in parsed.clauses}
            recovered = len(expected_ids & parsed_ids)
            rate = recovered / len(expected_ids) if expected_ids else 1.0
            source_recovery[source_type].append(rate)

    # Print breakdown
    print("\n=== Dataset Clean Clause Recovery Results ===")
    for stype, rates in source_recovery.items():
        avg_rate = sum(rates) / len(rates) if rates else 0.0
        print(f"Source: {stype} | Documents: {len(rates)} | Avg Recovery: {avg_rate * 100:.1f}%")
        if stype == "synthetic":
            assert avg_rate >= 0.95, f"Synthetic recovery {avg_rate * 100:.1f}% < 95% threshold"


@pytest.mark.dataset
@pytest.mark.skipif(DATASET_DIR is None, reason="data/generated dataset not present")
def test_dataset_tampered_samples_parse() -> None:
    """Parse a sample of every tamper type and verify they parse without error."""
    assert DATASET_DIR is not None
    labels_file = DATASET_DIR / "labels.jsonl"
    labels = [json.loads(line) for line in labels_file.read_text(encoding="utf-8").splitlines() if line.strip()]

    tampered_by_type: dict[str, list[dict]] = defaultdict(list)
    for lbl in labels:
        if lbl.get("is_tampered"):
            for tt in lbl.get("tamper_types", []):
                tampered_by_type[tt].append(lbl)

    print(f"\nTesting {len(tampered_by_type)} tamper types...")
    for ttype, doc_list in tampered_by_type.items():
        sample = doc_list[:2]
        for lbl in sample:
            doc_id = lbl["doc_id"]
            pdf_path = DATASET_DIR / f"{doc_id}.pdf"
            assert pdf_path.exists()
            parsed = parse_document(pdf_path.read_bytes())
            assert parsed.page_count > 0
            assert len(parsed.pages) > 0
        print(f"  - {ttype}: {len(sample)} sample(s) parsed successfully")
