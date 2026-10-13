"""Unit tests for runtime clause classifier (model.py)."""

from clauseguard.clauses.model import ClauseClassifier, classify_clause


def test_runtime_classifier_loads():
    clf = ClauseClassifier()
    # It either loads the model or gracefully runs in rules-only mode
    assert clf is not None


def test_classify_clause_positive():
    text = "This Agreement shall be governed by and construed in accordance with the laws of Delaware."
    results = classify_clause(text, heading="Governing Law")
    labels = {r["label"] for r in results}
    assert "governing_law" in labels

    gl = next(r for r in results if r["label"] == "governing_law")
    assert gl["score"] > 0
    assert gl["method"] in ("rules", "model", "both")
    assert len(gl["evidence"]) <= 300


def test_classify_clause_long_text_windowing():
    # Long text (> 250 words) with a non-compete clause in the middle
    prefix = "General operational provisions and background clauses. " * 30  # ~180 words
    compete = "Employee shall not engage in any competing business for a period of two (2) years following termination. "
    suffix = "Miscellaneous administrative boilerplate provisions and contact information. " * 30  # ~180 words
    full = prefix + compete + suffix

    results = classify_clause(full, heading="Covenants")
    labels = {r["label"] for r in results}
    assert "non_compete" in labels

    nc = next(r for r in results if r["label"] == "non_compete")
    assert len(nc["evidence"]) <= 300


def test_classify_clause_fallback_on_missing_model(tmp_path):
    # Point classifier to empty directory; must not raise and must use rules
    clf = ClauseClassifier(model_dir=tmp_path)
    assert clf.is_model_loaded is False

    text = "This Agreement shall be governed by the laws of Delaware."
    res = clf.classify_clause(text, heading="Governing Law")
    assert any(r["label"] == "governing_law" for r in res)
    assert all(r["method"] == "rules" for r in res)
