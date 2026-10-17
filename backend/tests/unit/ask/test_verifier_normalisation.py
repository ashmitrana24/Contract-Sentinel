"""Unit tests for grounding verifier Unicode normalisation and abstention handling."""

import pytest

from clauseguard.ask.answer import (
    is_abstention_answer,
    normalize_for_verification,
    verify_grounding,
)
from clauseguard.ask.chunking import RetrievalChunk


def test_normalize_for_verification_hyphens_and_quotes():
    # Non-breaking hyphen \u2011, en-dash \u2013, em-dash \u2014, minus \u2212
    raw = "Net\u201145 term\u2013limits liability\u2014cap \u2212500"
    norm = normalize_for_verification(raw)
    assert norm == "Net-45 term-limits liability-cap -500"

    # Curly double quotes \u201c \u201d, curly single quotes \u2018 \u2019
    raw_quotes = "“Delaware law” and ‘thirty days’"
    norm_quotes = normalize_for_verification(raw_quotes)
    assert norm_quotes == '"Delaware law" and \'thirty days\''


def test_normalize_for_verification_spaces():
    # Non-breaking space \u00a0, narrow non-breaking space \u202f, thin space \u2009
    raw = "Rs.\u202f50,00,000\u00a0(Fifty\u2009Lakhs)"
    norm = normalize_for_verification(raw)
    assert norm == "Rs. 50,00,000 (Fifty Lakhs)"


def test_exact_net_45_non_breaking_hyphen_and_curly_quotes():
    # Context in contract
    chunk = RetrievalChunk(
        chunk_id="3.1",
        clause_id="3.1",
        heading="Fees and Payment Terms",
        text="Customer shall pay all fees within forty-five (45) days of the invoice date (Net 45). Late payments incur interest at 1.5% per month.",
        page_start=1,
        page_end=1,
        word_count=25,
    )

    # Generated answer with curly quotes, non-breaking hyphen (\u2011), and narrow NBSP (\u202f)
    answer = (
        "The agreement states that “Customer shall pay all fees within forty\u2011five (45) days of the invoice date (Net\u202f45)” "
        "and “late payments incur interest at 1.5% per month” [3.1]."
    )

    result = verify_grounding(answer, [chunk])
    assert result.is_grounded is True
    assert len(result.unverified_quotes) == 0
    assert len(result.unverified_clause_ids) == 0
    assert result.kind == "answered"


def test_quote_case_insensitivity():
    chunk = RetrievalChunk(
        chunk_id="1",
        clause_id="1",
        heading="Governing Law",
        text="This Agreement shall be governed by and construed under the laws of the State of Delaware.",
        page_start=1,
        page_end=1,
        word_count=15,
    )

    # Model quotes with lowercase casing
    answer = 'The contract is governed by "the laws of the state of delaware" [1].'
    result = verify_grounding(answer, [chunk])
    assert result.is_grounded is True
    assert len(result.unverified_quotes) == 0


def test_abstention_answers_verified_without_citations():
    # Standard prefix
    ans1 = "The contract does not say what the employee 401(k) matching percentage is."
    res1 = verify_grounding(ans1, [])
    assert res1.is_grounded is True
    assert res1.kind == "abstention"
    assert len(res1.unverified_clause_ids) == 0
    assert len(res1.unverified_quotes) == 0

    # Phrase variants
    ans2 = "The provided contract excerpts do not contain sufficient information to answer this question."
    res2 = verify_grounding(ans2, [])
    assert res2.is_grounded is True
    assert res2.kind == "abstention"

    ans3 = "The agreement does not specify dental insurance coverage under Schedule D."
    res3 = verify_grounding(ans3, [])
    assert res3.is_grounded is True
    assert res3.kind == "abstention"


def test_failing_q_syn_03_shortened_quote_dropping_not_flagged():
    """Unit test for q_syn_03: A shortened quote dropping 'not' reverses meaning and must be flagged."""
    chunk = RetrievalChunk(
        chunk_id="5.1",
        clause_id="5.1",
        heading="Limitation of Liability",
        text="In no event shall either party's aggregate liability under this agreement exceed the total fees paid or payable by Customer in the twelve (12) months preceding the claim.",
        page_start=1,
        page_end=1,
        word_count=30,
    )

    # In q_syn_03, the model output an ellipsis quote that omitted 'shall not' / reversed meaning:
    # "either party's aggregate liability ... shall exceed the total fees..."
    bad_answer = (
        'The limitation of liability cap is that "either party\'s aggregate liability ... '
        'shall exceed the total fees paid or payable by Customer in the twelve (12) months preceding the claim." [5.1]'
    )

    # Wait, in the source text: "In no event shall either party's aggregate liability under this agreement exceed..."
    # The source says: "In no event shall either party's aggregate liability ... exceed"
    # The model omitted "In no event" before the quote, so the quote asserted "shall exceed", meaning the opposite!
    # Let's test both variants:
    # Variant A: Source text has 'shall not exceed', quote has '... shall exceed'
    chunk_neg = RetrievalChunk(
        chunk_id="5.1",
        clause_id="5.1",
        heading="Limitation of Liability",
        text="Supplier's aggregate liability under this Agreement shall not exceed Rs. 25,00,000.",
        page_start=1,
        page_end=1,
        word_count=10,
    )
    answer_dropped_not = 'Supplier states that "Supplier\'s aggregate liability ... shall exceed Rs. 25,00,000." [5.1]'
    res_dropped_not = verify_grounding(answer_dropped_not, [chunk_neg])
    assert res_dropped_not.is_grounded is False
    assert len(res_dropped_not.unverified_quotes) > 0
    assert any("not" in w for w in res_dropped_not.warnings)


def test_valid_ellipsis_quote_and_markdown_stripping():
    """Verifies that legitimate ellipsis quotes and markdown bold inside quotes are accepted."""
    chunk = RetrievalChunk(
        chunk_id="7.2",
        clause_id="7.2",
        heading="Non-Solicitation",
        text="Client agrees not to solicit or hire CynergisTek cybersecurity engineers for eighteen (18) months following project completion.",
        page_start=1,
        page_end=1,
        word_count=18,
    )

    # 1. Markdown bold inside quotation marks
    ans_bold = 'The clause states: "**Client agrees not to solicit or hire CynergisTek cybersecurity engineers**" [7.2].'
    res_bold = verify_grounding(ans_bold, [chunk])
    assert res_bold.is_grounded is True
    assert len(res_bold.unverified_quotes) == 0

    # 2. Legitimate ellipsis quote omitting neutral words without altering negation
    ans_ellipsis = 'Client agrees that "Client agrees not to solicit ... for eighteen (18) months following project completion." [7.2]'
    res_ellipsis = verify_grounding(ans_ellipsis, [chunk])
    assert res_ellipsis.is_grounded is True
    assert len(res_ellipsis.unverified_quotes) == 0

    # 3. Parenthetical citation mapping to heading
    ans_paren = 'Client agrees to the restriction (Non-Solicitation).'
    res_paren = verify_grounding(ans_paren, [chunk])
    assert res_paren.is_grounded is True
    assert len(res_paren.unrecognized_citations) == 0

