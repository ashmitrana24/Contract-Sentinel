"""Unit tests for Phase 2: BM25 retrieval engine, boosting, and question suggestions."""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock

import pytest

from clauseguard.ask.chunking import RetrievalChunk
from clauseguard.ask.retrieval import (
    BM25Index,
    expand_short_followup,
    is_overview_query,
    retrieve_evidence,
)
from clauseguard.ask.suggestions import generate_document_suggestions
from clauseguard.db.models import (
    Clause,
    Document,
    DocumentAttributeRow,
    FindingRow,
    Page,
    RiskSummaryRow,
)


def test_bm25_search_and_label_boosting() -> None:
    c1 = RetrievalChunk(
        chunk_id="1.1",
        clause_id="1.1",
        heading="Governing Law",
        text="This Agreement shall be governed by Delaware law.",
        page_start=1,
        page_end=1,
        word_count=8,
    )
    c2 = RetrievalChunk(
        chunk_id="2.1",
        clause_id="2.1",
        heading="Payment Terms",
        text="Invoices must be paid within thirty days of receipt under Delaware schedule.",
        page_start=1,
        page_end=1,
        word_count=12,
    )

    index = BM25Index([c1, c2])
    # Search without boost
    res = index.search("Delaware governing law", top_k=2)
    assert len(res) == 2
    assert res[0][0].clause_id == "1.1"

    # Search with boost favoring 2.1
    res_boosted = index.search("Delaware", top_k=2, label_boosts={"2.1": 3.0})
    assert res_boosted[0][0].clause_id == "2.1"


def test_expand_short_followup() -> None:
    # Under 6 words
    expanded = expand_short_followup(
        "What about Delaware?",
        last_user_query="What is the governing law of the contract?",
        last_assistant_heading="Governing Law",
    )
    assert "Delaware" in expanded
    assert "Governing Law" in expanded

    # 6 or more words: untouched
    unchanged = expand_short_followup("What is the governing law of Delaware?")
    assert unchanged == "What is the governing law of Delaware?"


def test_is_overview_query() -> None:
    assert is_overview_query("Summarize the risks") is True
    assert is_overview_query("What are the main risks?") is True
    assert is_overview_query("Provide a risk overview of the findings") is True
    assert is_overview_query("What is the termination notice period?") is False


def test_retrieve_evidence_overview_mode() -> None:
    session = MagicMock()
    doc_id = uuid.uuid4()

    # Mock RiskSummaryRow
    mock_risk = MagicMock(spec=RiskSummaryRow)
    mock_risk.score = 65
    mock_risk.band = "high"
    mock_risk.summary = {"headline": "High risk due to critical tampering findings."}

    # Mock FindingRow
    mock_finding = MagicMock(spec=FindingRow)
    mock_finding.severity = "critical"
    mock_finding.type = "incremental_edit_amount"
    mock_finding.explanation = "Contract amount modified after signing"
    mock_finding.evidence = "$1,000,000"

    # Mock DocumentAttributeRow
    mock_attrs = MagicMock(spec=DocumentAttributeRow)
    mock_attrs.governing_law_jurisdiction = "New York"
    mock_attrs.termination_notice_days = 30
    mock_attrs.liability_cap = {"amount": 500000}
    mock_attrs.limitation_of_liability = {"type": "monetary_cap"}

    def mock_get(model, ident):
        if model == RiskSummaryRow:
            return mock_risk
        if model == DocumentAttributeRow:
            return mock_attrs
        return None

    session.get.side_effect = mock_get

    mock_execute = MagicMock()
    mock_execute.scalars.return_value.all.side_effect = [
        [mock_finding],  # findings query
        [],              # clauses query
        [],              # pages query
    ]
    session.execute.return_value = mock_execute

    result = retrieve_evidence(doc_id, "Summarize the risks of this agreement", session=session)
    assert result.is_overview is True
    assert result.overview_block is not None
    assert "HIGH" in result.overview_block
    assert "incremental_edit_amount" in result.overview_block
    assert "New York" in result.overview_block
    assert result.has_sufficient_evidence is True


def test_generate_document_suggestions() -> None:
    session = MagicMock()
    doc_id = uuid.uuid4()

    mock_doc = MagicMock(spec=Document)
    mock_attrs = MagicMock(spec=DocumentAttributeRow)
    mock_attrs.governing_law_jurisdiction = "California"
    mock_attrs.termination_notice_days = 60
    mock_attrs.limitation_of_liability = {"type": "monetary_cap"}
    mock_attrs.auto_renews = True
    mock_attrs.non_compete_duration_months = 12
    mock_attrs.payment_terms_days = 30

    mock_risk = MagicMock(spec=RiskSummaryRow)
    mock_risk.band = "high"

    def mock_get(model, ident):
        if model == Document:
            return mock_doc
        if model == DocumentAttributeRow:
            return mock_attrs
        if model == RiskSummaryRow:
            return mock_risk
        return None

    session.get.side_effect = mock_get

    mock_finding = MagicMock(spec=FindingRow)
    mock_finding.module = "pdf_forensics"
    mock_finding.type = "white_on_white"

    mock_exec = MagicMock()
    mock_exec.scalars.return_value.all.return_value = [mock_finding]
    session.execute.return_value = mock_exec

    response = generate_document_suggestions(doc_id, session)
    assert response.document_id == doc_id
    assert 4 <= len(response.suggestions) <= 6

    questions = [s.question for s in response.suggestions]
    assert any("California" in q for q in questions)
    assert any("termination" in q.lower() or "60" in q for q in questions)
    assert any("hidden" in q.lower() for q in questions)
