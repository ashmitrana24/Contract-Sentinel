"""Unit tests for sliding window splitting and prediction aggregation."""

from clauseguard.clauses.windows import (
    aggregate_window_predictions,
    split_clause_into_windows,
    truncate_evidence,
)


def test_split_clause_under_threshold():
    text = "This is a short clause of only ten words here."
    windows = split_clause_into_windows(text, max_words_threshold=250)
    assert len(windows) == 1
    assert windows[0].window_index == 0
    assert windows[0].text == text
    assert windows[0].start_word == 0
    assert windows[0].end_word == 10


def test_split_clause_over_threshold():
    # 300 words
    words = [f"word{i}" for i in range(300)]
    text = " ".join(words)

    windows = split_clause_into_windows(
        text,
        max_words_threshold=250,
        window_size=120,
        stride=100,
    )
    # Expected:
    # w0: 0..120
    # w1: 100..220
    # w2: 200..300
    assert len(windows) == 3
    assert windows[0].start_word == 0
    assert windows[0].end_word == 120
    assert windows[1].start_word == 100
    assert windows[1].end_word == 220
    assert windows[2].start_word == 200
    assert windows[2].end_word == 300


def test_split_clause_empty():
    assert split_clause_into_windows("") == []
    assert split_clause_into_windows("   ") == []


def test_truncate_evidence():
    short = "Governing Law clause in Delaware."
    assert truncate_evidence(short, max_chars=100) == short

    long_text = "word " * 100
    res = truncate_evidence(long_text, max_chars=50)
    assert len(res) <= 50
    assert res.endswith("...")


def test_aggregate_window_predictions():
    w1_preds = [
        {"label": "governing_law", "score": 0.85, "method": "model", "evidence": "Governing Law of New York"},
        {"label": "anti_assignment", "score": 0.40, "method": "rules", "evidence": "No assignment without consent"},
    ]
    w2_preds = [
        {"label": "governing_law", "score": 0.95, "method": "rules", "evidence": "Governing Law of New York State courts"},
        {"label": "audit_rights", "score": 0.70, "method": "model", "evidence": "Right to audit books and records"},
    ]

    aggregated = aggregate_window_predictions([w1_preds, w2_preds])
    # Expect 3 labels: governing_law, audit_rights, anti_assignment
    assert len(aggregated) == 3

    gl = next(p for p in aggregated if p["label"] == "governing_law")
    assert gl["score"] == 0.95
    assert gl["method"] == "both"
    assert "New York State courts" in gl["evidence"]

    ar = next(p for p in aggregated if p["label"] == "audit_rights")
    assert ar["score"] == 0.70
    assert ar["method"] == "model"

    aa = next(p for p in aggregated if p["label"] == "anti_assignment")
    assert aa["score"] == 0.40
    assert aa["method"] == "rules"
