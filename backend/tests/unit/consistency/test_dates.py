"""Unit tests for date parser and date consistency detectors."""

import datetime

import pytest

from clauseguard.consistency.dates import detect_dates, parse_date
from clauseguard.consistency.models import ConsistencySettings
from clauseguard.consistency.text_index import build_text_index
from clauseguard.schemas.findings import Severity
from clauseguard.schemas.parsed import ClauseModel, PageModel, ParsedDocument

pytestmark = pytest.mark.unit


def _make_doc(text: str, clause_id: str = "2.1") -> ParsedDocument:
    return ParsedDocument(
        page_count=1,
        pages=[PageModel(page_no=1, width=612.0, height=792.0, text=text, char_count=len(text))],
        clauses=[
            ClauseModel(
                order_idx=0,
                clause_id=clause_id,
                heading="Term and Termination",
                text=text,
                level=1,
                page_start=1,
                page_end=1,
                kind="clause",
            )
        ],
    )


def test_parse_date_formats():
    # 1. ISO
    d1 = parse_date("2026-01-01")
    assert d1.date == datetime.date(2026, 1, 1)
    assert d1.is_ambiguous is False

    # 2. Ordinal day of month
    d2 = parse_date("1st day of January, 2026")
    assert d2.date == datetime.date(2026, 1, 1)

    # 3. Month day, year
    d3 = parse_date("January 1, 2026")
    assert d3.date == datetime.date(2026, 1, 1)

    # 4. Day Month Year
    d4 = parse_date("1 Jan 2026")
    assert d4.date == datetime.date(2026, 1, 1)

    # 5. Numeric DMY
    d5 = parse_date("01/01/2026", "DMY")
    assert d5.date == datetime.date(2026, 1, 1)
    assert d5.is_ambiguous is False

    # 6. Numeric dotted
    d6 = parse_date("01.01.2026", "DMY")
    assert d6.date == datetime.date(2026, 1, 1)


def test_parse_date_rejects_impossible_dates():
    assert parse_date("31 February 2026") is None
    assert parse_date("2026-02-30") is None
    assert parse_date("32/01/2026") is None
    assert parse_date("not a date") is None
    assert parse_date("") is None
    assert parse_date(None) is None


def test_ambiguous_numeric_date_flag():
    d_amb = parse_date("05/06/2026", "DMY")
    assert d_amb.date == datetime.date(2026, 6, 5)
    assert d_amb.is_ambiguous is True

    d_unamb = parse_date("15/06/2026", "DMY")
    assert d_unamb.is_ambiguous is False


def test_end_before_start_date_flagged_high():
    text = (
        "This Agreement is effective as of 2024-06-01 and shall terminate on 2023-01-15 "
        "unless extended by mutual written agreement."
    )
    doc = _make_doc(text)
    index = build_text_index(doc)
    findings, stats = detect_dates(index, ConsistencySettings())
    assert len(findings) == 1
    f = findings[0]
    assert f.type == "date_order_conflict"
    assert f.severity == Severity.HIGH
    assert "2023-01-15" in f.evidence
    assert stats["date_order_conflicts"] == 1


def test_ambiguous_numeric_end_before_start_reduces_severity_to_medium():
    text = (
        "This Agreement is effective from 2024-06-01 and expires on 05/04/2024."
    )  # 05/04/2024 DMY is 5 April 2024 (before 1 June 2024), ambiguous
    doc = _make_doc(text)
    index = build_text_index(doc)
    findings, _stats = detect_dates(index, ConsistencySettings())
    assert len(findings) == 1
    f = findings[0]
    assert f.type == "date_order_conflict"
    assert f.severity == Severity.MEDIUM
    assert "ambiguous" in f.explanation.lower()


def test_conflicting_effective_date_definitions_flagged_medium():
    text = (
        "'Effective Date' means 2024-01-01. The 'Effective Date' is 2024-06-01 for all operational provisions."
    )
    doc = _make_doc(text)
    index = build_text_index(doc)
    findings, stats = detect_dates(index, ConsistencySettings())
    assert any(f.type == "effective_date_conflict" for f in findings)
    f = next(f for f in findings if f.type == "effective_date_conflict")
    assert f.severity == Severity.MEDIUM
    assert stats["effective_date_conflicts"] == 1


def test_term_length_mismatch_flagged_medium():
    text = (
        "This Agreement is effective on 2024-01-01 and terminates on 2026-01-01, "
        "for a period of 5 years unless terminated earlier."
    )  # 2 years span between 2024 and 2026, but states 5 years
    doc = _make_doc(text)
    index = build_text_index(doc)
    findings, stats = detect_dates(index, ConsistencySettings())
    assert any(f.type == "term_length_conflict" for f in findings)
    f = next(f for f in findings if f.type == "term_length_conflict")
    assert f.severity == Severity.MEDIUM
    assert stats["term_conflicts"] == 1


def test_matching_term_length_not_flagged():
    text = (
        "This Agreement is effective on 2024-01-01 and terminates on 2025-01-01, "
        "for a period of 1 year unless terminated earlier."
    )
    doc = _make_doc(text)
    index = build_text_index(doc)
    findings, _stats = detect_dates(index, ConsistencySettings())
    term_findings = [f for f in findings if f.type == "term_length_conflict"]
    assert len(term_findings) == 0


def test_different_events_with_different_dates_not_flagged():
    text = (
        "Party A was incorporated on 2015-03-12. Party B signed the MoU on 2021-08-10. "
        "The first milestone review occurred on 2022-11-05."
    )
    doc = _make_doc(text)
    index = build_text_index(doc)
    findings, _stats = detect_dates(index, ConsistencySettings())
    assert len(findings) == 0
