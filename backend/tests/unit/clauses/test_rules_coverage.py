"""Unit test suite for 17 clause rule categories (9 extra + 8 core).

Tests at least 5 positive and at least 3 negative sentences per label:
1. governing_law
2. termination_for_convenience
3. renewal_term
4. cap_on_liability
5. uncapped_liability
6. anti_assignment
7. non_compete
8. audit_rights
9. indemnification
10. confidentiality
11. payment_terms
12. unilateral_amendment
13. force_majeure
14. arbitration_or_dispute_resolution
15. waiver_of_rights
16. termination_for_cause
17. auto_renewal
"""

import pytest

from clauseguard.clauses.rules import classify_clause_rules


# -----------------------------------------------------------------------------
# 1. governing_law
# -----------------------------------------------------------------------------
@pytest.mark.parametrize(
    "text",
    [
        "This Agreement shall be governed by the laws of the State of New York.",
        "This Agreement and all acts and transactions pursuant hereto shall be construed and enforced in accordance with the laws of Delaware.",
        "The parties submit to the exclusive jurisdiction of the federal and state courts located in California.",
        "Any dispute arising under this contract shall be governed by and construed in accordance with the laws of England and Wales.",
        "The venue for any legal proceeding arising out of or relating to this Agreement shall be in the courts of Chicago, Illinois.",
    ],
)
def test_governing_law_positive(text: str):
    matches = classify_clause_rules(text)
    labels = {m["label"] for m in matches}
    assert "governing_law" in labels


@pytest.mark.parametrize(
    "text",
    [
        "The Supplier will provide law enforcement assistance if legally requested by subpoena.",
        "Both parties agree to obey all applicable local environmental and labor statutes during manufacturing.",
        "The law firm representing the client charges an hourly rate of $500 for legal advice.",
    ],
)
def test_governing_law_negative(text: str):
    matches = classify_clause_rules(text)
    labels = {m["label"] for m in matches}
    assert "governing_law" not in labels


# -----------------------------------------------------------------------------
# 2. termination_for_convenience
# -----------------------------------------------------------------------------
@pytest.mark.parametrize(
    "text",
    [
        "Either party may terminate this Agreement for convenience upon thirty (30) days written notice.",
        "Client reserves the right to terminate this contract without cause at any time upon sixty (60) days notice.",
        "The Company may terminate this Agreement at its sole option for any reason or no reason without liability.",
        "Either party may terminate this Agreement at any time without penalty by providing written notice.",
        "Upon giving ninety (90) days prior written notice without cause, either party may terminate this relationship.",
    ],
)
def test_termination_for_convenience_positive(text: str):
    matches = classify_clause_rules(text)
    labels = {m["label"] for m in matches}
    assert "termination_for_convenience" in labels


@pytest.mark.parametrize(
    "text",
    [
        "Either party may terminate this Agreement immediately for material breach upon written notice.",
        "The term of this Agreement shall expire on the third anniversary of the Effective Date.",
        "In the event of insolvency or bankruptcy, the Agreement shall terminate immediately.",
    ],
)
def test_termination_for_convenience_negative(text: str):
    matches = classify_clause_rules(text)
    labels = {m["label"] for m in matches}
    assert "termination_for_convenience" not in labels


# -----------------------------------------------------------------------------
# 3. renewal_term
# -----------------------------------------------------------------------------
@pytest.mark.parametrize(
    "text",
    [
        "This Agreement shall automatically renew for successive one-year terms.",
        "The contract shall renew for additional successive periods of twelve (12) months each.",
        "Following the initial period, this Agreement shall be extended for successive terms of two (2) years.",
        "Each such annual extension shall be deemed a renewal term under this Agreement.",
        "The Agreement shall automatically renew for successive periods of five (5) years unless notice is given.",
    ],
)
def test_renewal_term_positive(text: str):
    matches = classify_clause_rules(text)
    labels = {m["label"] for m in matches}
    assert "renewal_term" in labels


@pytest.mark.parametrize(
    "text",
    [
        "The initial term of this Agreement shall commence on January 1 and continue for three years without renewal.",
        "The employee may request a salary review upon completion of one year of continuous service.",
        "This patent license expires upon the expiration of the underlying patent rights.",
    ],
)
def test_renewal_term_negative(text: str):
    matches = classify_clause_rules(text)
    labels = {m["label"] for m in matches}
    assert "renewal_term" not in labels


# -----------------------------------------------------------------------------
# 4. cap_on_liability
# -----------------------------------------------------------------------------
@pytest.mark.parametrize(
    "text",
    [
        "In no event shall liability exceed the fees paid by customer under this agreement.",
        "The total aggregate liability of either party under this agreement shall not exceed $1,000,000.",
        "Each party's maximum liability is capped at the total amounts received during the preceding twelve months.",
        "In no event shall either party's total cumulative liability under this agreement exceed $500,000.",
        "The aggregate liability under this agreement shall in no event exceed the purchase price.",
    ],
)
def test_cap_on_liability_positive(text: str):
    matches = classify_clause_rules(text)
    labels = {m["label"] for m in matches}
    assert "cap_on_liability" in labels


@pytest.mark.parametrize(
    "text",
    [
        "Neither party shall be liable for special, incidental, punitive, or consequential damages.",
        "Customer shall maintain commercial liability insurance in an amount of at least $2,000,000.",
        "The Supplier represents that all products delivered will be free from physical defects.",
    ],
)
def test_cap_on_liability_negative(text: str):
    matches = classify_clause_rules(text)
    labels = {m["label"] for m in matches}
    assert "cap_on_liability" not in labels


# -----------------------------------------------------------------------------
# 5. uncapped_liability
# -----------------------------------------------------------------------------
@pytest.mark.parametrize(
    "text",
    [
        "The limitation of liability shall not apply to or limit liability for gross negligence or willful misconduct.",
        "Nothing in this Agreement shall exclude or limit either party's liability for fraud or breach of confidentiality.",
        "Exclusions from the limitation of liability include indemnification obligations and intentional breach.",
        "Liability for bodily injury, death, and infringement of intellectual property shall be uncapped.",
        "The liability cap under Section 9 shall not apply to damages arising from breach of Section 4.",
    ],
)
def test_uncapped_liability_positive(text: str):
    matches = classify_clause_rules(text)
    labels = {m["label"] for m in matches}
    assert "uncapped_liability" in labels


@pytest.mark.parametrize(
    "text",
    [
        "In no event shall total liability exceed the amounts paid in the last six months.",
        "Liability is strictly capped at one hundred thousand dollars ($100,000).",
        "Neither party makes any warranties regarding merchantability or fitness for purpose.",
    ],
)
def test_uncapped_liability_negative(text: str):
    matches = classify_clause_rules(text)
    labels = {m["label"] for m in matches}
    assert "uncapped_liability" not in labels


# -----------------------------------------------------------------------------
# 6. anti_assignment
# -----------------------------------------------------------------------------
@pytest.mark.parametrize(
    "text",
    [
        "Neither party may assign its rights or obligations under this Agreement without prior written consent.",
        "Neither party may assign this Agreement without the prior written consent of the other party.",
        "Any attempted assignment or delegation without such consent shall be null and void.",
        "This Agreement shall not be assignable by either party without the express written approval of the other.",
        "No assignment of this Agreement or any right accruing hereunder shall be made without prior written notice and consent.",
    ],
)
def test_anti_assignment_positive(text: str):
    matches = classify_clause_rules(text)
    labels = {m["label"] for m in matches}
    assert "anti_assignment" in labels


@pytest.mark.parametrize(
    "text",
    [
        "The Company assigns all rights, title, and interest in and to the developed software code to Client.",
        "The contractor shall perform the specific tasks assigned by the project director.",
        "The assignee shall assume all obligations set forth in the underlying instrument.",
    ],
)
def test_anti_assignment_negative(text: str):
    matches = classify_clause_rules(text)
    labels = {m["label"] for m in matches}
    assert "anti_assignment" not in labels


# -----------------------------------------------------------------------------
# 7. non_compete
# -----------------------------------------------------------------------------
@pytest.mark.parametrize(
    "text",
    [
        "Employee agrees to a covenant not to compete with the Company for a period of two years.",
        "Recipient shall not directly or indirectly engage in or carry on any competing business.",
        "The non-competition covenant shall survive termination of this contract for twenty-four months.",
        "Partner agrees to refrain from competing with the Firm in the designated geographical territory.",
        "Neither party shall compete with the Company in the sale of similar commercial equipment.",
    ],
)
def test_non_compete_positive(text: str):
    matches = classify_clause_rules(text)
    labels = {m["label"] for m in matches}
    assert "non_compete" in labels


@pytest.mark.parametrize(
    "text",
    [
        "All employees must participate in the annual skills and software development competition.",
        "The market for commercial mobile services is highly competitive and rapidly evolving.",
        "Employee shall devote their full productive business time and efforts to the employer.",
    ],
)
def test_non_compete_negative(text: str):
    matches = classify_clause_rules(text)
    labels = {m["label"] for m in matches}
    assert "non_compete" not in labels


# -----------------------------------------------------------------------------
# 8. audit_rights
# -----------------------------------------------------------------------------
@pytest.mark.parametrize(
    "text",
    [
        "Customer shall have the right to audit Supplier's security controls and compliance records once per year.",
        "Licensor may inspect and audit the books and records of Licensee upon reasonable prior written notice.",
        "The Company shall permit independent certified public accountants to examine accounting records.",
        "Upon reasonable prior notice, Client may audit, examine, or inspect the facilities and records.",
        "The auditor may conduct an inspection of the books, accounts, and financial statements of the distributor.",
    ],
)
def test_audit_rights_positive(text: str):
    matches = classify_clause_rules(text)
    labels = {m["label"] for m in matches}
    assert "audit_rights" in labels


@pytest.mark.parametrize(
    "text",
    [
        "The auditor issued an unqualified opinion on the corporation's consolidated financial statements.",
        "All software code must pass rigorous automated quality audits before continuous integration deployment.",
        "The internal audit department reported directly to the corporate board of directors.",
    ],
)
def test_audit_rights_negative(text: str):
    matches = classify_clause_rules(text)
    labels = {m["label"] for m in matches}
    assert "audit_rights" not in labels


# -----------------------------------------------------------------------------
# 9. indemnification (Extra label)
# -----------------------------------------------------------------------------
@pytest.mark.parametrize(
    "text",
    [
        "The Supplier shall indemnify, defend and hold harmless the Customer against all claims.",
        "Vendor agrees to defend, indemnify, and hold harmless Buyer from and against third-party liabilities.",
        "Each party's indemnification obligations under this Section shall survive the expiration of this agreement.",
        "Supplier shall defend against any third-party claims alleging patent or copyright infringement.",
        "Customer shall indemnify and hold harmless the service provider from losses arising out of unauthorized access.",
    ],
)
def test_indemnification_positive(text: str):
    matches = classify_clause_rules(text)
    labels = {m["label"] for m in matches}
    assert "indemnification" in labels


@pytest.mark.parametrize(
    "text",
    [
        "The contractor will hold a weekly project status meeting every Monday at 9:00 AM.",
        "Buyer agrees to pay the agreed purchase price upon delivery of the clean title documentation.",
        "All proprietary materials will be returned to the owner immediately upon project completion.",
    ],
)
def test_indemnification_negative(text: str):
    matches = classify_clause_rules(text)
    labels = {m["label"] for m in matches}
    assert "indemnification" not in labels


# -----------------------------------------------------------------------------
# 10. confidentiality (Extra label)
# -----------------------------------------------------------------------------
@pytest.mark.parametrize(
    "text",
    [
        "The Receiving Party shall treat all Confidential Information as strictly confidential.",
        "Each party shall maintain in strict confidence any trade secrets and proprietary data disclosed.",
        "The non-disclosure of proprietary information obligations shall continue for five years.",
        "Recipient owes a strict duty of confidentiality regarding the technical documentation and customer lists.",
        "Confidential information means all non-public information disclosed by either party.",
    ],
)
def test_confidentiality_positive(text: str):
    matches = classify_clause_rules(text)
    labels = {m["label"] for m in matches}
    assert "confidentiality" in labels


@pytest.mark.parametrize(
    "text",
    [
        "The marketing team will distribute public press releases to media outlets nationwide.",
        "All terms and conditions of this public offering are published on the corporate website.",
        "The parties have executed this Agreement on the date set forth above.",
    ],
)
def test_confidentiality_negative(text: str):
    matches = classify_clause_rules(text)
    labels = {m["label"] for m in matches}
    assert "confidentiality" not in labels


# -----------------------------------------------------------------------------
# 11. payment_terms (Extra label)
# -----------------------------------------------------------------------------
@pytest.mark.parametrize(
    "text",
    [
        "Payment shall be due within thirty (30) days following receipt of an undisputed invoice.",
        "All approved invoices are payable Net 30 days from invoice date.",
        "Services shall be invoiced monthly in arrears and paid electronically.",
        "Customer shall pay within 45 days of delivery, subject to late payment interest charges.",
        "All fees are billed quarterly in advance and payable within 15 business days.",
    ],
)
def test_payment_terms_positive(text: str):
    matches = classify_clause_rules(text)
    labels = {m["label"] for m in matches}
    assert "payment_terms" in labels


@pytest.mark.parametrize(
    "text",
    [
        "The employee shall perform their duties with due care, diligence, and professional skill.",
        "The software includes a perpetual license to use the accompanying user manuals.",
        "Notices shall be sent by registered mail to the address specified on page one.",
    ],
)
def test_payment_terms_negative(text: str):
    matches = classify_clause_rules(text)
    labels = {m["label"] for m in matches}
    assert "payment_terms" not in labels


# -----------------------------------------------------------------------------
# 12. unilateral_amendment (Extra label)
# -----------------------------------------------------------------------------
@pytest.mark.parametrize(
    "text",
    [
        "The Company may amend these terms at any time upon notice posted to its portal.",
        "Provider reserves the right to modify or amend these terms at any time in its sole discretion.",
        "We reserve the right to update or modify this agreement unilaterally by providing email notice.",
        "The service provider has sole discretion to change any terms and pricing upon 30 days notice.",
        "Platform may modify these conditions at any time without prior individual notice.",
    ],
)
def test_unilateral_amendment_positive(text: str):
    matches = classify_clause_rules(text)
    labels = {m["label"] for m in matches}
    assert "unilateral_amendment" in labels


@pytest.mark.parametrize(
    "text",
    [
        "No amendment to this Agreement shall be effective unless made in writing and signed by both parties.",
        "This Agreement may only be amended by a written instrument executed by authorized representatives.",
        "This Agreement constitutes the entire understanding between the parties.",
    ],
)
def test_unilateral_amendment_negative(text: str):
    matches = classify_clause_rules(text)
    labels = {m["label"] for m in matches}
    assert "unilateral_amendment" not in labels


# -----------------------------------------------------------------------------
# 13. force_majeure (Extra label)
# -----------------------------------------------------------------------------
@pytest.mark.parametrize(
    "text",
    [
        "Neither party shall be liable for failure to perform due to events of force majeure.",
        "Performance will be excused in the event of acts of God, war, terrorism, or natural disasters.",
        "Neither party is responsible for delays caused by circumstances beyond the reasonable control of such party.",
        "A party shall be excused from performance due to events beyond its reasonable contemplation.",
        "Failure or delay in delivery shall be excused if resulting from fire, flood, strike, or epidemic.",
    ],
)
def test_force_majeure_positive(text: str):
    matches = classify_clause_rules(text)
    labels = {m["label"] for m in matches}
    assert "force_majeure" in labels


@pytest.mark.parametrize(
    "text",
    [
        "The sales force achieved all quarterly revenue targets established by executive leadership.",
        "The police force inspected the building following a false security alarm.",
        "Each party will devote adequate resources and personnel to the implementation project.",
    ],
)
def test_force_majeure_negative(text: str):
    matches = classify_clause_rules(text)
    labels = {m["label"] for m in matches}
    assert "force_majeure" not in labels


# -----------------------------------------------------------------------------
# 14. arbitration_or_dispute_resolution (Extra label)
# -----------------------------------------------------------------------------
@pytest.mark.parametrize(
    "text",
    [
        "Any controversy or claim arising out of this contract shall be settled by binding arbitration.",
        "Disputes shall be submitted to the American Arbitration Association in accordance with its Commercial Rules.",
        "All claims shall be resolved under JAMS arbitration rules by a single neutral arbitrator.",
        "The parties agree that dispute resolution by arbitration shall be the exclusive remedy.",
        "Any disagreement shall be arbitrated in accordance with the International Chamber of Commerce rules.",
    ],
)
def test_arbitration_or_dispute_resolution_positive(text: str):
    matches = classify_clause_rules(text)
    labels = {m["label"] for m in matches}
    assert "arbitration_or_dispute_resolution" in labels


@pytest.mark.parametrize(
    "text",
    [
        "The financial trader executed an arbitrage transaction between New York and London exchanges.",
        "Disputes shall be settled in the state courts of Delaware through standard trial proceedings.",
        "The parties will attempt amicable negotiations before seeking injunctive judicial relief.",
    ],
)
def test_arbitration_or_dispute_resolution_negative(text: str):
    matches = classify_clause_rules(text)
    labels = {m["label"] for m in matches}
    assert "arbitration_or_dispute_resolution" not in labels


# -----------------------------------------------------------------------------
# 15. waiver_of_rights (Extra label)
# -----------------------------------------------------------------------------
@pytest.mark.parametrize(
    "text",
    [
        "Each party hereby irrevocably agrees to a waiver of jury trial in any proceeding arising hereunder.",
        "The Customer expressly waives any right to a trial by jury in connection with this dispute.",
        "Customer agrees to a waiver of class action proceedings and shall assert claims solely individually.",
        "The failure of either party to enforce any provision shall not operate as a waiver of such right.",
        "No waiver of any breach shall constitute a continuing waiver of any subsequent default.",
    ],
)
def test_waiver_of_rights_positive(text: str):
    matches = classify_clause_rules(text)
    labels = {m["label"] for m in matches}
    assert "waiver_of_rights" in labels


@pytest.mark.parametrize(
    "text",
    [
        "The applicant waved hello to the interviewing committee upon entering the conference room.",
        "The copyright owner retains all moral and statutory rights under federal copyright legislation.",
        "All intellectual property rights created under this agreement shall vest solely in client.",
    ],
)
def test_waiver_of_rights_negative(text: str):
    matches = classify_clause_rules(text)
    labels = {m["label"] for m in matches}
    assert "waiver_of_rights" not in labels


# -----------------------------------------------------------------------------
# 16. termination_for_cause (Extra label)
# -----------------------------------------------------------------------------
@pytest.mark.parametrize(
    "text",
    [
        "Either party may terminate this agreement for cause upon written notice.",
        "Either party may terminate in the event of material breach and failure to cure within 30 days.",
        "Immediate termination upon written notice if either party enters bankruptcy or insolvency proceedings.",
        "Licensor may terminate immediately upon material default by licensee of payment obligations.",
        "Either party may terminate for default if the other party fails to remedy a substantial deficiency.",
    ],
)
def test_termination_for_cause_positive(text: str):
    matches = classify_clause_rules(text)
    labels = {m["label"] for m in matches}
    assert "termination_for_cause" in labels


@pytest.mark.parametrize(
    "text",
    [
        "Either party may terminate this agreement for convenience upon thirty days written notice.",
        "The initial term shall expire without penalty on the second anniversary of execution.",
        "The parties will maintain accurate accounting records throughout the contract duration.",
    ],
)
def test_termination_for_cause_negative(text: str):
    matches = classify_clause_rules(text)
    labels = {m["label"] for m in matches}
    assert "termination_for_cause" not in labels


# -----------------------------------------------------------------------------
# 17. auto_renewal (Extra label)
# -----------------------------------------------------------------------------
@pytest.mark.parametrize(
    "text",
    [
        "This Agreement shall automatically renew for successive terms of one year each.",
        "The contract is an auto-renewal agreement that extends annually without further signature.",
        "This is an evergreen contract that remains in full force and effect from year to year.",
        "The subscription will renew automatically unless either party gives written notice of termination.",
        "This Agreement shall automatically renew for successive periods unless sixty days notice is provided.",
    ],
)
def test_auto_renewal_positive(text: str):
    matches = classify_clause_rules(text)
    labels = {m["label"] for m in matches}
    assert "auto_renewal" in labels


@pytest.mark.parametrize(
    "text",
    [
        "This Agreement shall expire at the end of the initial term and shall not renew automatically.",
        "Any contract renewal shall require the mutual written agreement and signatures of both parties.",
        "The employee's term of employment is strictly fixed at twelve months with no renewal.",
    ],
)
def test_auto_renewal_negative(text: str):
    matches = classify_clause_rules(text)
    labels = {m["label"] for m in matches}
    assert "auto_renewal" not in labels
