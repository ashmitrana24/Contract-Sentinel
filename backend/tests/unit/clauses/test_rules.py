"""Unit tests for deterministic clause classification rules."""

from clauseguard.clauses.rules import classify_clause_rules


def test_classify_clause_rules_governing_law():
    text = "This Agreement shall be governed by and construed in accordance with the laws of Delaware."
    matches = classify_clause_rules(text, heading="Governing Law")
    labels = {m["label"] for m in matches}
    assert "governing_law" in labels
    gl = next(m for m in matches if m["label"] == "governing_law")
    assert gl["method"] == "rules"
    assert gl["score"] >= 0.85
    assert len(gl["evidence"]) <= 300


def test_classify_clause_rules_anti_assignment():
    text = "Neither party may assign its rights or obligations under this Agreement without the prior written consent of the other party."
    matches = classify_clause_rules(text, heading="Assignment")
    labels = {m["label"] for m in matches}
    assert "anti_assignment" in labels


def test_classify_clause_rules_confidentiality_extra_label():
    text = "Receiving Party shall hold in strict confidence all Confidential Information and shall not disclose it to any third party."
    matches = classify_clause_rules(text, heading="Confidentiality")
    labels = {m["label"] for m in matches}
    assert "confidentiality" in labels


def test_classify_clause_rules_indemnification():
    text = "Supplier shall defend, indemnify, and hold harmless the Company against any and all third party claims."
    matches = classify_clause_rules(text, heading="Indemnification")
    labels = {m["label"] for m in matches}
    assert "indemnification" in labels


def test_classify_clause_rules_force_majeure():
    text = "Neither party shall be liable for failure to perform due to events of force majeure or acts of God."
    matches = classify_clause_rules(text, heading="Force Majeure")
    labels = {m["label"] for m in matches}
    assert "force_majeure" in labels


def test_classify_clause_rules_heading_fallback():
    # Text itself doesn't have exact phrase, but heading matches
    text = "The parties agree to the terms set forth herein regarding books and records."
    matches = classify_clause_rules(text, heading="Audit Rights")
    labels = {m["label"] for m in matches}
    assert "audit_rights" in labels


def test_classify_clause_rules_negative():
    text = "The meeting was held at 10:00 AM in the morning."
    matches = classify_clause_rules(text, heading="Meeting Notes")
    assert matches == []
