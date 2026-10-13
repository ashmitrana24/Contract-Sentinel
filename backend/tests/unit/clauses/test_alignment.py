"""Unit tests for CUAD character-offset clause alignment."""

from clauseguard.clauses.training.cuad_data import extract_contract_clauses


def test_alignment_span_inside_one_clause():
    """A span completely within a single clause should align to that clause."""
    context = (
        "1. Governing Law\n"
        "This Agreement shall be governed by the laws of the State of Delaware.\n\n"
        "2. Termination\n"
        "Either party may terminate this Agreement upon thirty (30) days notice.\n"
    )
    span_text = "laws of the State of Delaware"
    ans_start = context.index(span_text)

    contract_data = {
        "title": "Test Contract",
        "paragraphs": [
            {
                "context": context,
                "qas": [
                    {
                        "id": "test__Governing Law",
                        "answers": [{"text": span_text, "answer_start": ans_start}],
                    }
                ],
            }
        ],
    }

    clauses, total_ans, aligned_ans = extract_contract_clauses(contract_data)
    assert total_ans == 1
    assert aligned_ans == 1

    # Clause 1 should have governing_law, clause 2 should not
    gov_clauses = [c for c in clauses if "governing_law" in c.labels]
    assert len(gov_clauses) == 1
    assert "Delaware" in gov_clauses[0].text
    assert gov_clauses[0].clause_id == "1"


def test_alignment_span_across_two_clauses_majority():
    """Span crosses two clauses, with >= 50% in the second clause."""
    c1 = "1. Section One.\nThe seller warrants that goods are free of defects. Notice of claim "
    c2 = "2. Section Two.\nmust be given within thirty days of delivery in writing to the seller."
    context = c1 + "\n\n" + c2
    # Span starts at end of c1 and extends into c2
    span_text = "Notice of claim \n\n2. Section Two.\nmust be given within thirty days of delivery in writing to the seller."
    ans_start = context.index("Notice of claim ")

    contract_data = {
        "title": "Cross Clause Majority",
        "paragraphs": [
            {
                "context": context,
                "qas": [
                    {
                        "id": "test__Notice Period To Terminate Renewal",
                        "answers": [{"text": span_text, "answer_start": ans_start}],
                    }
                ],
            }
        ],
    }

    clauses, total_ans, aligned_ans = extract_contract_clauses(contract_data)
    assert total_ans == 1
    assert aligned_ans == 1

    # The clause with >= 50% must be labeled (clause 2)
    labeled = [c for c in clauses if "notice_period_to_terminate_renewal" in c.labels]
    assert len(labeled) >= 1
    assert any(c.clause_id == "2" for c in labeled)


def test_alignment_span_across_clauses_no_majority():
    """Span crosses multiple clauses, none reaching 50%; largest overlap gets label."""
    c1 = "1. First clause with some text: " + ("A" * 45)
    c2 = "2. Second clause: " + ("B" * 35)
    c3 = "3. Third clause: " + ("C" * 20)
    context = f"{c1}\n\n{c2}\n\n{c3}\n"
    span_text = ("A" * 45) + "\n\n2. Second clause: " + ("B" * 35)
    ans_start = context.index("A" * 45)

    contract_data = {
        "title": "No Majority Span",
        "paragraphs": [
            {
                "context": context,
                "qas": [
                    {
                        "id": "test__Anti-Assignment",
                        "answers": [{"text": span_text, "answer_start": ans_start}],
                    }
                ],
            }
        ],
    }

    clauses, total_ans, aligned_ans = extract_contract_clauses(contract_data)
    assert total_ans == 1
    assert aligned_ans == 1

    labeled = [c for c in clauses if "anti_assignment" in c.labels]
    # Clause with largest overlap gets the label (exactly 1 clause)
    assert len(labeled) == 1


def test_alignment_repeated_text_offset_disambiguation():
    """When the same exact phrase appears in multiple clauses, answer_start resolves the correct one."""
    context = (
        "1. First Section\n"
        "Either party may terminate for convenience upon 30 days notice.\n\n"
        "2. Second Section\n"
        "Neither party may assign this agreement without consent.\n\n"
        "3. Third Section\n"
        "Either party may terminate for convenience upon 30 days notice.\n"
    )
    # Target the second instance in Section 3
    first_idx = context.index("terminate for convenience")
    second_idx = context.index("terminate for convenience", first_idx + 1)
    span_text = "terminate for convenience"

    contract_data = {
        "title": "Repeated Text",
        "paragraphs": [
            {
                "context": context,
                "qas": [
                    {
                        "id": "test__Termination For Convenience",
                        "answers": [{"text": span_text, "answer_start": second_idx}],
                    }
                ],
            }
        ],
    }

    clauses, total_ans, aligned_ans = extract_contract_clauses(contract_data)
    assert total_ans == 1
    assert aligned_ans == 1

    # Only the third section clause should have termination_for_convenience
    labeled = [c for c in clauses if "termination_for_convenience" in c.labels]
    assert len(labeled) == 1
    assert labeled[0].clause_id == "3"
    assert labeled[0].heading == "Third Section"


def test_alignment_offset_mismatch_fallback():
    """When answer_start has an offset mismatch, normalized exact search locates and aligns the span."""
    context = (
        "1. Confidentiality\n"
        "The recipient agrees not to disclose proprietary information.\n\n"
        "2. Exclusivity Clause\n"
        "Distributor shall have the exclusive right to market the products in the territory.\n"
    )
    span_text = "exclusive right to market the products"
    # Provide an intentionally incorrect answer_start (0 instead of ~100)
    contract_data = {
        "title": "Offset Mismatch",
        "paragraphs": [
            {
                "context": context,
                "qas": [
                    {
                        "id": "test__Exclusivity",
                        "answers": [{"text": span_text, "answer_start": 0}],
                    }
                ],
            }
        ],
    }

    clauses, total_ans, aligned_ans = extract_contract_clauses(contract_data)
    assert total_ans == 1
    assert aligned_ans == 1

    labeled = [c for c in clauses if "exclusivity" in c.labels]
    assert len(labeled) == 1
    assert labeled[0].clause_id == "2"
    assert labeled[0].heading == "Exclusivity Clause"
