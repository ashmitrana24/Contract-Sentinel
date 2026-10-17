"""Unit tests for the reprocess CLI and pipeline."""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock, patch

import pytest

from clauseguard.config import get_settings
from clauseguard.worker.reprocess import ALL_STAGES, parse_stages_arg, reprocess_document


def test_parse_stages_arg_valid() -> None:
    assert parse_stages_arg("parse,forensics") == {"parse", "forensics"}
    assert parse_stages_arg("  clauses , summary ") == {"clauses", "summary"}
    assert parse_stages_arg("CONSISTENCY") == {"consistency"}
    assert parse_stages_arg(",".join(ALL_STAGES)) == ALL_STAGES


def test_parse_stages_arg_invalid() -> None:
    with pytest.raises(ValueError, match="Invalid stage"):
        parse_stages_arg("parse,unknown_stage")

    with pytest.raises(ValueError, match="At least one stage"):
        parse_stages_arg("   ")


def test_reprocess_document_not_found() -> None:
    session = MagicMock()
    session.get.return_value = None
    store = MagicMock()
    cfg = get_settings()

    with pytest.raises(ValueError, match="not found in database"):
        reprocess_document(uuid.uuid4(), {"clauses"}, session=session, store=store, cfg=cfg)


def test_reprocess_document_file_not_found() -> None:
    session = MagicMock()
    doc_mock = MagicMock()
    doc_mock.storage_key = "dummy_key"
    session.get.return_value = doc_mock
    store = MagicMock()
    store.read.side_effect = FileNotFoundError("Missing")
    cfg = get_settings()

    with pytest.raises(RuntimeError, match="File not found in storage"):
        reprocess_document(uuid.uuid4(), {"clauses"}, session=session, store=store, cfg=cfg)


def test_reprocess_document_replace_clauses_stage() -> None:
    session = MagicMock()
    doc_mock = MagicMock()
    doc_mock.storage_key = "key123"
    session.get.return_value = doc_mock

    store = MagicMock()
    store.read.return_value = b"%PDF-dummy"

    cfg = get_settings()
    doc_id = uuid.uuid4()

    dummy_parsed = MagicMock()
    dummy_clause = MagicMock()
    dummy_clause.clause_id = "c1"
    dummy_clause.heading = "Heading 1"
    dummy_clause.text = "This is clause text."
    dummy_parsed.clauses = [dummy_clause]
    dummy_parsed.pages = []

    with patch("clauseguard.worker.reprocess.parse_document", return_value=dummy_parsed):
        with patch("clauseguard.worker.reprocess.classify_clause", return_value=[{"label": "general", "score": 0.9, "method": "test", "evidence": "text"}]):
            with patch("clauseguard.worker.reprocess.extract_all_document_attributes") as mock_attr:
                mock_attr.return_value = MagicMock(
                    governing_law_jurisdiction="Delaware",
                    termination_notice_days=30,
                    auto_renews=True,
                    renewal_term_months=12,
                    non_renewal_notice_days=60,
                    liability_cap={"type": "fixed_amount", "amount": 100000, "currency": "USD"},
                    limitation_of_liability={"type": "monetary_cap", "amount": 100000, "currency": "USD", "evidence": "evidence"},
                    non_compete_duration_months=12,
                    payment_terms_days=30,
                )
                result = reprocess_document(
                    doc_id,
                    {"clauses"},
                    session=session,
                    store=store,
                    cfg=cfg,
                )

    assert result["document_id"] == str(doc_id)
    assert result["stages"] == ["clauses"]
    assert "total_clauses" in result
    assert "total_labels" in result
    # Ensure delete queries were executed (replace semantics)
    assert session.execute.call_count >= 3
    # Ensure session.add / session.add_all was called
    assert session.add_all.call_count >= 1
    assert session.add.call_count >= 2
