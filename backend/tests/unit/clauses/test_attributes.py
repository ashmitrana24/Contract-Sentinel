"""Comprehensive unit tests for key-term extractors (attributes.py).

Guarantees >= 8 positive and >= 4 negative test cases per extractor (64 pos, 32 neg).
Verifies deterministic extraction and correct None handling on ambiguous/irrelevant inputs.
"""

import pytest

from clauseguard.clauses.attributes import (
    extract_all_document_attributes,
    extract_auto_renews,
    extract_governing_law_jurisdiction,
    extract_liability_cap,
    extract_non_compete_duration_months,
    extract_non_renewal_notice_days,
    extract_payment_terms_days,
    extract_renewal_term_months,
    extract_termination_notice_days,
)


# =============================================================================
# 1. Governing Law Jurisdiction (8 Pos, 4 Neg)
# =============================================================================
@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("This Agreement shall be governed by the laws of the State of Delaware.", "Delaware"),
        ("This contract is construed in accordance with the laws of New York.", "New York"),
        ("Governed by and under the laws of California without regard to conflicts.", "California"),
        ("The parties agree to the exclusive jurisdiction of Texas courts.", "Texas"),
        ("Governed by the laws of the Commonwealth of Massachusetts.", "Massachusetts"),
        ("Construed in accordance with the laws of England and Wales.", "England and Wales"),
        ("Subject to the laws and jurisdiction of Ontario, Canada.", "Ontario"),
        ("This Agreement shall be governed by the laws of Singapore.", "Singapore"),
    ],
)
def test_governing_law_positive(text: str, expected: str):
    assert extract_governing_law_jurisdiction(text) == expected


@pytest.mark.parametrize(
    "text",
    [
        "This Agreement contains general definitions.",
        "The parties will act in good faith and fair dealing.",
        "Governed by Delaware or New York depending on which party initiates.",  # Conflicting / ambiguous
        "All notices shall be delivered in writing.",
    ],
)
def test_governing_law_negative(text: str):
    assert extract_governing_law_jurisdiction(text) is None


# =============================================================================
# 2. Termination Notice Days (8 Pos, 4 Neg)
# =============================================================================
@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Either party may terminate upon thirty (30) days prior written notice.", 30),
        ("May terminate for convenience upon giving 60 days written notice.", 60),
        ("Termination upon ninety (90) days written notice without cause.", 90),
        ("Can terminate upon 15 days prior written notice.", 15),
        ("Termination with 10 days written notice for default.", 10),
        ("Terminate upon 45 days prior written notice.", 45),
        ("May terminate this agreement upon 2 months prior written notice.", 60),
        ("Terminate for convenience upon two weeks prior written notice.", 14),
    ],
)
def test_termination_notice_days_positive(text: str, expected: int):
    assert extract_termination_notice_days(text) == expected


@pytest.mark.parametrize(
    "text",
    [
        "This Agreement shall terminate upon completion of the work.",
        "Termination immediately upon written notice.",
        "The term of this Agreement is five years.",
        "Neither party shall terminate without mutual agreement.",
    ],
)
def test_termination_notice_days_negative(text: str):
    assert extract_termination_notice_days(text) is None


# =============================================================================
# 3. Auto Renews (8 Pos, 4 Neg)
# =============================================================================
@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("This Agreement shall automatically renew for successive terms.", True),
        ("The contract will renew automatically unless terminated.", True),
        ("This is an evergreen contract that extends each year.", True),
        ("Auto-renewal applies at the end of the term.", True),
        ("Subject to automatic renewal at prevailing rates.", True),
        ("Agreement renews automatically every 12 months.", True),
        ("The agreement shall not automatically renew.", False),
        ("There is no automatic renewal of this contract.", False),
    ],
)
def test_auto_renews_positive(text: str, expected: bool):
    assert extract_auto_renews(text) is expected


@pytest.mark.parametrize(
    "text",
    [
        "The Initial Term is three years from the Effective Date.",
        "Parties may negotiate an extension prior to expiration.",
        "This Agreement will expire on December 31, 2026.",
        "Either party may terminate at any time.",
    ],
)
def test_auto_renews_negative(text: str):
    assert extract_auto_renews(text) is None


# =============================================================================
# 4. Renewal Term Months (8 Pos, 4 Neg)
# =============================================================================
@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Renew for successive periods of one (1) year.", 12),
        ("Renewal term of twelve (12) months each.", 12),
        ("Renew for additional terms of two years.", 24),
        ("Extended for successive periods of three (3) years.", 36),
        ("Renew for successive terms of 6 months.", 6),
        ("Renewal term of one month.", 1),
        ("Renewed for additional periods of 24 months.", 24),
        ("Extended for further terms of five years.", 60),
    ],
)
def test_renewal_term_months_positive(text: str, expected: int):
    assert extract_renewal_term_months(text) == expected


@pytest.mark.parametrize(
    "text",
    [
        "The initial term is three years.",
        "Renewal terms shall be negotiated between the parties.",
        "Agreement may be renewed upon terms mutually agreeable.",
        "No renewal permitted.",
    ],
)
def test_renewal_term_months_negative(text: str):
    assert extract_renewal_term_months(text) is None


# =============================================================================
# 5. Non-Renewal Notice Days (8 Pos, 4 Neg)
# =============================================================================
@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Unless either party provides notice of non-renewal at least 30 days prior.", 30),
        ("Notice of non-renewal at least 60 days prior to the expiration of the term.", 60),
        ("Notice not to renew at least ninety (90) days prior to the end of the initial term.", 90),
        ("Written notice not to extend at least 45 days before the end of the current term.", 45),
        ("At least 60 days written notice prior to the end of the initial term of non-renewal.", 60),
        ("At least thirty days prior written notice of non-renewal.", 30),
        ("Notice of non-renewal at least 2 months prior to the expiration.", 60),
        ("At least 120 days prior written notice not to renew.", 120),
    ],
)
def test_non_renewal_notice_days_positive(text: str, expected: int):
    assert extract_non_renewal_notice_days(text) == expected


@pytest.mark.parametrize(
    "text",
    [
        "Either party may terminate with 30 days notice for breach.",
        "The contract expires on December 31.",
        "Non-renewal is at the sole discretion of the buyer.",
        "Notice of termination shall be sent by certified mail.",
    ],
)
def test_non_renewal_notice_days_negative(text: str):
    assert extract_non_renewal_notice_days(text) is None


# =============================================================================
# 6. Liability Cap (8 Pos, 4 Neg)
# =============================================================================
@pytest.mark.parametrize(
    ("text", "expected_type", "expected_key", "expected_val"),
    [
        ("Total liability shall not exceed $1,000,000.", "fixed_amount", "amount", 1000000.0),
        ("Liability is capped at $500,000 USD.", "fixed_amount", "amount", 500000.0),
        ("In no event shall aggregate liability exceed 2,500,000.", "fixed_amount", "amount", 2500000.0),
        ("Total liability shall not exceed EUR 100,000.", "fixed_amount", "currency", "EUR"),
        ("Aggregate liability limited to £50,000.", "fixed_amount", "currency", "GBP"),
        ("Liability capped at $250,000.50.", "fixed_amount", "amount", 250000.50),
        ("Total liability equal to the total fees paid in the preceding 12 months.", "fee_multiplier", "months", 12),
        ("Shall not exceed total amounts paid in the preceding 6 months.", "fee_multiplier", "months", 6),
    ],
)
def test_liability_cap_positive(text: str, expected_type: str, expected_key: str, expected_val):
    res = extract_liability_cap(text)
    assert res is not None
    assert res["type"] == expected_type
    assert res[expected_key] == expected_val


@pytest.mark.parametrize(
    "text",
    [
        "Neither party shall be liable for indirect or consequential damages.",
        "Each party shall maintain adequate insurance.",
        "Liability shall be unlimited for willful misconduct.",
        "Payment is due in full within 30 days.",
    ],
)
def test_liability_cap_negative(text: str):
    assert extract_liability_cap(text) is None


# =============================================================================
# 7. Non-Compete Duration Months (8 Pos, 4 Neg)
# =============================================================================
@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Shall not compete directly or indirectly for a period of one (1) year following termination.", 12),
        ("Non-compete covenant shall continue for a period of 2 years post-employment.", 24),
        ("Shall not engage in any competing business for a period of three (3) years.", 36),
        ("Non-competition obligations remain in effect for 6 months.", 6),
        ("Refrain from competing for a period of 18 months following expiration.", 18),
        ("Non-compete duration of four years.", 48),
        ("Shall not compete for a period of five years following closing.", 60),
        ("Non-competition period of 24 months post termination.", 24),
    ],
)
def test_non_compete_duration_positive(text: str, expected: int):
    assert extract_non_compete_duration_months(text) == expected


@pytest.mark.parametrize(
    "text",
    [
        "Employee agrees not to disclose confidential information.",
        "Employee will devote full business time to the company.",
        "Non-compete applies nationwide during employment.",
        "All inventions belong to the company.",
    ],
)
def test_non_compete_duration_negative(text: str):
    assert extract_non_compete_duration_months(text) is None


# =============================================================================
# 8. Payment Terms Days (8 Pos, 4 Neg)
# =============================================================================
@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("All invoices are due Net 30 days.", 30),
        ("Payment terms: Net 60.", 60),
        ("Invoices payable Net 45.", 45),
        ("Net 15 upon receipt of invoice.", 15),
        ("Payment shall be due within 30 days of invoice receipt.", 30),
        ("Payable within sixty days of delivery.", 60),
        ("Payment is due within 45 days.", 45),
        ("Payment shall be due within 90 days from the invoice date.", 90),
    ],
)
def test_payment_terms_days_positive(text: str, expected: int):
    assert extract_payment_terms_days(text) == expected


@pytest.mark.parametrize(
    "text",
    [
        "Fees shall be paid in advance annually.",
        "All payments are non-refundable.",
        "Customer shall pay applicable taxes.",
        "Interest accrues at 1.5% per month on past due amounts.",
    ],
)
def test_payment_terms_days_negative(text: str):
    assert extract_payment_terms_days(text) is None


# =============================================================================
# Aggregate Document Attributes Test
# =============================================================================
def test_extract_all_document_attributes():
    clauses = [
        "1. GOVERNING LAW. This Agreement is governed by the laws of Delaware.",
        "2. TERM. Automatically renews for successive periods of 1 year unless 60 days notice of non-renewal.",
        "3. TERMINATION. Either party may terminate for convenience upon 30 days prior written notice.",
        "4. LIABILITY. In no event shall total liability exceed $500,000.",
        "5. PAYMENT. Invoices are payable Net 30.",
        "6. COVENANTS. Shall not compete for a period of 2 years post-termination.",
    ]
    attrs = extract_all_document_attributes(clauses)
    assert attrs.governing_law_jurisdiction == "Delaware"
    assert attrs.auto_renews is True
    assert attrs.renewal_term_months == 12
    assert attrs.non_renewal_notice_days == 60
    assert attrs.termination_notice_days == 30
    assert attrs.liability_cap == {"type": "fixed_amount", "amount": 500000.0, "currency": "USD"}
    assert attrs.payment_terms_days == 30
    assert attrs.non_compete_duration_months == 24


def test_addendum_a_exact_sentence_attribute_bug():
    sentence = (
        "This Agreement shall automatically renew for successive one-year terms "
        "unless either party gives sixty (60) days notice."
    )
    assert extract_auto_renews(sentence) is True
    assert extract_renewal_term_months(sentence) == 12
    assert extract_non_renewal_notice_days(sentence) == 60

    attrs = extract_all_document_attributes(sentence)
    assert attrs.auto_renews is True
    assert attrs.renewal_term_months == 12
    assert attrs.non_renewal_notice_days == 60


def test_addendum_a_additional_renewal_variations():
    # twelve (12) months and sixty (60) days' prior written notice
    t1 = (
        "This Agreement shall renew for twelve (12) months unless either party "
        "provides sixty (60) days' prior written notice."
    )
    assert extract_renewal_term_months(t1) == 12
    assert extract_non_renewal_notice_days(t1) == 60

    # two (2) years
    t2 = "This Agreement shall automatically renew for successive periods of two (2) years."
    assert extract_renewal_term_months(t2) == 24

    # Negative test: termination for convenience should not extract non_renewal_notice_days
    neg_term = "Either party may terminate this Agreement for convenience upon thirty (30) days notice."
    assert extract_non_renewal_notice_days(neg_term) is None
    assert extract_termination_notice_days(neg_term) == 30

    # Negative test: static term without renewal
    neg_static = "The term of this Agreement shall be three (3) years expiring December 31, 2025."
    assert extract_auto_renews(neg_static) is None
    assert extract_renewal_term_months(neg_static) is None
    assert extract_non_renewal_notice_days(neg_static) is None


# =============================================================================
# Regression Tests: Module 5 Sanity Check Misses (Governing Law & Liability Cap)
# =============================================================================
def test_governing_law_regression_misses():
    # Miss 1: Heading-only New York (MetLife)
    h1 = (
        "GOVERNING LAW. THIS REMARKETING AGREEMENT AND THE PRICING AGREEMENT "
        "SHALL BE GOVERNED BY AND CONSTRUED IN ACCORDANCE WITH THE LAWS OF THE STATE OF NEW YORK."
    )
    assert extract_governing_law_jurisdiction("", heading=h1) == "New York"

    # Miss 2: Heading-only Delaware (Cerence)
    h2 = (
        "Governing Law; Jurisdiction. Any disputes relating to, arising out of or resulting "
        "from this Agreement shall be governed by Delaware."
    )
    assert extract_governing_law_jurisdiction("", heading=h2) == "Delaware"

    # Miss 3: Heading-only Commonwealth of Pennsylvania (Premier Biomedical)
    h3 = (
        "VENUE. This Agreement and the rights of the Parties hereunder shall be "
        "governed by and construed in accordance with the laws of the Commonwealth of Pennsylvania."
    )
    assert extract_governing_law_jurisdiction("", heading=h3) == "Pennsylvania"

    # Miss 4: International - India (Opera Ltd)
    t4 = (
        "This Agreement (and any question about its subsistence, effect or termination) "
        "is to be interpreted in accordance with the laws of India, save for that body of law "
        "which governs the conflict of laws."
    )
    assert extract_governing_law_jurisdiction(t4) == "India"

    # Miss 5: English law phrasing
    t5 = (
        "This Agreement and any dispute or claim arising out of or in connection with it "
        "shall be governed by and construed in accordance with English law."
    )
    assert extract_governing_law_jurisdiction(t5) == "England and Wales"


def test_liability_cap_regression_misses():
    # Miss 1: Heading-only fees and expenses cap (Opera Ltd)
    h1 = (
        "10.2 NEITHER PARTIES' TOTAL CUMULATIVE LIABILITY IN CONNECTION WITH THIS AGREEMENT, "
        "WHETHER IN AGREEMENT OR TORT OR OTHERWISE, WILL NOT EXCEED THE AGGREGATE AMOUNT OF "
        "FEES AND EXPENSES OWED BY PC FINANCIAL TO MOBIMAGIC FOR SERVICES PERFORMED UNDER THIS AGREEMENT."
    )
    res1 = extract_liability_cap("", heading=h1)
    assert res1 == {"type": "fee_multiplier", "months": 12, "basis": "fees_paid"}

    # Miss 2: Direct damages cap
    t2 = "Total liability for direct damages shall not exceed $100,000."
    res2 = extract_liability_cap(t2)
    assert res2 == {"type": "fixed_amount", "amount": 100000.0, "currency": "USD"}

    # Miss 3: Written monetary cap (fifteen million)
    t3 = "In no event shall aggregate liability exceed fifteen million dollars."
    res3 = extract_liability_cap(t3)
    assert res3 == {"type": "fixed_amount", "amount": 15000000.0, "currency": "USD"}

    # Miss 4: Written number fifty dollars ($50)
    t4 = "Each party's maximum liability shall not exceed fifty dollars ($50)."
    res4 = extract_liability_cap(t4)
    assert res4 == {"type": "fixed_amount", "amount": 50.0, "currency": "USD"}

    # Miss 5: Consequential damages disclaimer (Must be None under contract!)
    t5 = (
        "Limitation of Liability. In no event will either party be liable to the other "
        "for lost revenue, lost profits, or any indirect, special, or consequential damages."
    )
    assert extract_liability_cap(t5) is None


def test_limitation_of_liability_types_and_evidence():
    from clauseguard.clauses.attributes import extract_limitation_of_liability

    # 1. Monetary cap
    t1 = "In no event shall aggregate liability exceed $500,000 USD."
    res1 = extract_limitation_of_liability(t1)
    assert res1["type"] == "monetary_cap"
    assert res1["amount"] == 500000.0
    assert res1["currency"] == "USD"
    assert "liability exceed $500,000 USD" in res1["evidence"]

    # 2. Fee based cap
    t2 = "Total liability shall not exceed the aggregate amount of fees paid in the preceding 12 months."
    res2 = extract_limitation_of_liability(t2)
    assert res2["type"] == "fee_based_cap"
    assert res2["months"] == 12
    assert "fees paid in the preceding 12 months" in res2["evidence"]

    # 3. Excludes indirect or consequential
    t3 = (
        "Section 11. Limitation of Liability. Neither party shall be liable to the other "
        "for any indirect, incidental, special, punitive, or consequential damages."
    )
    res3 = extract_limitation_of_liability(t3)
    assert res3["type"] == "excludes_indirect_or_consequential"
    assert "consequential damages" in res3["evidence"]

    # 4. Unlimited stated
    t4 = "Liability under this Section 8 shall be unlimited."
    res4 = extract_limitation_of_liability(t4)
    assert res4["type"] == "unlimited_stated"
    assert "unlimited" in res4["evidence"]

    # 5. None found
    t5 = "This Agreement may be executed in counterparts, each of which shall be deemed an original."
    res5 = extract_limitation_of_liability(t5)
    assert res5["type"] == "none_found"
    assert res5["evidence"] is None


