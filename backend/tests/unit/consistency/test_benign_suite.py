"""Benign suite: at least 12 realistic clean contract texts (Indian and US styles).

Must produce NO finding above LOW severity (i.e. zero MEDIUM, HIGH, or CRITICAL findings).
Covers:
- Indian style & US style contracts
- Defined terms
- Statutory references (e.g., Section 138 of Negotiable Instruments Act, Companies Act)
- Matching amounts in words and figures (INR and USD, lakhs and millions)
- Correct dates and terms
- Optional [Reserved] / Intentionally Omitted clauses
- Party names with different entity suffix spellings (Pvt. Ltd. vs Private Limited)
"""

import pytest

from clauseguard.consistency.dates import detect_dates
from clauseguard.consistency.models import ConsistencySettings
from clauseguard.consistency.numbering import detect_clause_numbering
from clauseguard.consistency.pairs import detect_pairs
from clauseguard.consistency.parties import detect_party_inconsistencies
from clauseguard.consistency.references import detect_cross_references
from clauseguard.consistency.text_index import build_text_index
from clauseguard.schemas.findings import Finding, Severity
from clauseguard.schemas.parsed import ClauseModel, PageModel, ParsedDocument

pytestmark = pytest.mark.unit


def _run_all_detectors(doc: ParsedDocument) -> list[Finding]:
    """Helper to run all consistency detectors on a parsed document."""
    settings = ConsistencySettings()
    index = build_text_index(doc)

    findings: list[Finding] = []

    pairs_f, _ = detect_pairs(doc, index, settings)
    findings.extend(pairs_f)

    dates_f, _ = detect_dates(doc, index, settings)
    findings.extend(dates_f)

    parties_f, _ = detect_party_inconsistencies(doc, index, settings)
    findings.extend(parties_f)

    refs_f, refs_stats = detect_cross_references(doc, index, settings)
    findings.extend(refs_f)

    dangling_targets = refs_stats.get("dangling_targets", [])
    num_f, _ = detect_clause_numbering(doc, index, settings, dangling_targets=dangling_targets)
    findings.extend(num_f)

    return findings


def _make_doc(intro: str, clauses: list[tuple[str, str, str]]) -> ParsedDocument:
    clause_objs = [
        ClauseModel(
            order_idx=0,
            clause_id="0",
            heading="Preamble",
            text=intro,
            level=0,
            page_start=1,
            page_end=1,
            kind="preamble",
        )
    ]
    for idx, (cid, heading, text) in enumerate(clauses, start=1):
        clause_objs.append(
            ClauseModel(
                order_idx=idx,
                clause_id=cid,
                heading=heading,
                text=text,
                level=1,
                page_start=1,
                page_end=1,
                kind="clause",
            )
        )
    full_text = f"{intro}\n" + "\n".join(f"{h}\n{t}" for _, h, t in clauses)
    pages = [
        PageModel(
            page_no=1,
            width=612.0,
            height=792.0,
            text=full_text,
            char_count=len(full_text),
        )
    ]
    return ParsedDocument(page_count=1, pages=pages, clauses=clause_objs)


def _assert_no_medium_or_above(findings: list[Finding], contract_name: str) -> None:
    high_sev = [
        f for f in findings
        if f.severity in (Severity.MEDIUM, Severity.HIGH, Severity.CRITICAL)
    ]
    assert not high_sev, f"{contract_name} produced unexpected findings: {[(f.type, f.severity, f.evidence) for f in high_sev]}"


# ---------------------------------------------------------------------------
# 1. Indian Commercial Lease Agreement
# ---------------------------------------------------------------------------
def test_benign_01_indian_commercial_lease():
    intro = (
        "This Commercial Lease Agreement is entered into on 01/04/2025 by and between "
        "Apex Properties Private Limited (hereinafter 'Lessor') and "
        "Zenith Retail Pvt. Ltd. (hereinafter 'Lessee')."
    )
    clauses = [
        ("1", "Demised Premises", "The Lessor leases commercial office premises situated in Mumbai to Lessee."),
        ("2", "Term", "This lease shall commence on 01/04/2025 and shall terminate on 31/03/2026."),
        ("3", "Rent", "The Lessee shall pay a monthly rent of Rs. 2,50,000 (Rupees Two lakh fifty thousand only)."),
        ("4", "Security Deposit", "Lessee deposits Rs. 15,00,000 (Rupees Fifteen lakh) with Apex Properties Pvt. Ltd."),
        ("5", "Statutory Compliance", "Both parties shall adhere to provisions under the Transfer of Property Act, 1882."),
        ("6", "Governing Law", "This Agreement is governed by the laws of India."),
    ]
    doc = _make_doc(intro, clauses)
    findings = _run_all_detectors(doc)
    _assert_no_medium_or_above(findings, "Indian Commercial Lease")


# ---------------------------------------------------------------------------
# 2. US SaaS Subscription Agreement
# ---------------------------------------------------------------------------
def test_benign_02_us_saas_agreement():
    intro = (
        "This Master SaaS Subscription Agreement is entered into as of January 15, 2025 "
        "between CloudScale Solutions, Inc. ('Provider') and Global Logistics LLC ('Customer')."
    )
    clauses = [
        ("1", "Subscription Services", "Provider grants Customer a non-exclusive license pursuant to Section 2."),
        ("2", "Service Levels", "Provider guarantees ninety-nine percent (99%) uptime availability."),
        ("3", "Fees and Payment", "Customer shall pay an annual fee of $120,000 (One hundred twenty thousand Dollars)."),
        ("4", "Term", "This Agreement shall be effective on January 15, 2025 and shall expire on January 15, 2027."),
        ("5", "Confidentiality", "Each party maintains non-disclosure obligations for three (3) years."),
        ("6", "Governing Law", "Governed by Delaware law without regard to Delaware General Corporation Law conflicts."),
    ]
    doc = _make_doc(intro, clauses)
    findings = _run_all_detectors(doc)
    _assert_no_medium_or_above(findings, "US SaaS Agreement")


# ---------------------------------------------------------------------------
# 3. Indian IT Master Services Agreement
# ---------------------------------------------------------------------------
def test_benign_03_indian_it_services():
    intro = (
        "Between: Infosys Tech Consulting Pvt. Ltd. (Service Provider) and "
        "Bharat Financial Services Limited (Client)"
    )
    clauses = [
        ("1", "Scope of Services", "Detailed in Statements of Work subject to Clause 2."),
        ("2", "Invoicing and Payment", "Invoices shall be settled within thirty (30) days of receipt."),
        ("3", "Compensation", "Total project fee shall be Rs. 1,50,00,000 (Rupees One crore fifty lakh only)."),
        ("4", "Statutory Disputes", "Neither party waives remedies under Section 138 of the Negotiable Instruments Act, 1881."),
        ("5", "Corporate Governance", "Compliant with Section 135 of the Companies Act, 2013 relating to CSR."),
        ("6", "Term and Termination", "Effective as of 01/01/2025 and ends on 31/12/2026."),
    ]
    doc = _make_doc(intro, clauses)
    findings = _run_all_detectors(doc)
    _assert_no_medium_or_above(findings, "Indian IT Services")


# ---------------------------------------------------------------------------
# 4. US Mutual Non-Disclosure Agreement
# ---------------------------------------------------------------------------
def test_benign_04_us_mutual_nda():
    intro = (
        "This Mutual Non-Disclosure Agreement dated March 1, 2025 is between "
        "Vanguard Robotics Corp. ('Vanguard') and Horizon Medical Devices Inc. ('Horizon')."
    )
    clauses = [
        ("1", "Confidential Information", "Defined to encompass proprietary trade secrets and technical specifications."),
        ("2", "Exclusions", "Excludes information publicly known or independently developed without reference to Clause 1."),
        ("3", "Standard of Care", "Recipient shall exercise the same degree of care as for its own information."),
        ("4", "Term", "Effective from March 1, 2025 and shall terminate on March 1, 2028."),
        ("5", "Remedies", "Injunctive relief may be sought in the courts of New York."),
    ]
    doc = _make_doc(intro, clauses)
    findings = _run_all_detectors(doc)
    _assert_no_medium_or_above(findings, "US Mutual NDA")


# ---------------------------------------------------------------------------
# 5. Indian Employment Contract
# ---------------------------------------------------------------------------
def test_benign_05_indian_employment():
    intro = (
        "This Employment Agreement is made on 01/07/2025 between "
        "Stellar Innovations Private Limited ('Employer') and Rahul Sharma ('Employee')."
    )
    clauses = [
        ("1", "Appointment", "Employee is appointed as Senior Architect under Stellar Innovations Pvt. Ltd."),
        ("2", "Remuneration", "Annual CTC shall be Rs. 36,00,000 (Rupees Thirty-six lakh only) payable monthly."),
        ("3", "Probation", "The Employee shall serve a probation period of ninety (90) days."),
        ("4", "Statutory Benefits", "Governed by the Employees Provident Funds and Miscellaneous Provisions Act, 1952."),
        ("5", "Termination", "Either party may terminate by giving sixty (60) days written notice."),
    ]
    doc = _make_doc(intro, clauses)
    findings = _run_all_detectors(doc)
    _assert_no_medium_or_above(findings, "Indian Employment")


# ---------------------------------------------------------------------------
# 6. UK Consultancy Agreement
# ---------------------------------------------------------------------------
def test_benign_06_uk_consultancy():
    intro = (
        "This Consultancy Agreement is entered into on 10/05/2025 between "
        "Meridian Advisory Limited ('Consultant') and Delta Capital Partners LLP ('Client')."
    )
    clauses = [
        ("1", "Services", "Consultant shall provide strategic advisory services described in Clause 2."),
        ("2", "Fees", "Client shall pay a retainer of GBP 50,000 (Fifty thousand Pounds) per quarter."),
        ("3", "Term", "Commencing on 10/05/2025 and shall expire on 10/05/2026."),
        ("4", "Statutory Compliance", "All corporate filings comply with the Companies Act 2006."),
        ("5", "Notices", "Written notices delivered to registered office of Meridian Advisory Ltd."),
    ]
    doc = _make_doc(intro, clauses)
    findings = _run_all_detectors(doc)
    _assert_no_medium_or_above(findings, "UK Consultancy")


# ---------------------------------------------------------------------------
# 7. Distribution Agreement with [Reserved] Clause
# ---------------------------------------------------------------------------
def test_benign_07_distribution_with_reserved_clause():
    intro = (
        "Between: Alpha Consumer Goods Ltd. (Manufacturer) and "
        "Omega Logistics Private Limited (Distributor)"
    )
    clauses = [
        ("1", "Territory", "Exclusive distribution rights granted in Northern Territory."),
        ("2", "Minimum Orders", "Distributor commits to 500 (five hundred) units monthly."),
        ("3", "Pricing", "Discount rate of fifteen percent (15%) off catalog list."),
        ("4", "Reserved Territory [Reserved]", "Intentionally omitted by agreement of the parties."),
        ("5", "Term", "Effective as of 01/01/2025 and terminating on 31/12/2027."),
        ("6", "Governing Law", "Governed by Indian Law."),
    ]
    doc = _make_doc(intro, clauses)
    findings = _run_all_detectors(doc)
    _assert_no_medium_or_above(findings, "Distribution with Reserved Clause")


# ---------------------------------------------------------------------------
# 8. Intellectual Property Assignment Agreement
# ---------------------------------------------------------------------------
def test_benign_08_ip_assignment():
    intro = (
        "This IP Assignment Agreement is made on August 20, 2025 between "
        "Inventive Labs Inc. ('Assignor') and Pioneer Holdings Corp. ('Assignee')."
    )
    clauses = [
        ("1", "Assignment of Patents", "Assignor transfers all worldwide patent rights under Section 2."),
        ("2", "Consideration", "Assignee shall pay $750,000 (Seven hundred fifty thousand Dollars) at closing."),
        ("3", "Warranties", "Assignor warrants sole ownership free of third-party liens."),
        ("4", "Statutory Provisions", "Compliant with provisions of the Copyright Act of 1976."),
        ("5", "Further Assurances", "Assignor executes additional documentation within ten (10) business days."),
    ]
    doc = _make_doc(intro, clauses)
    findings = _run_all_detectors(doc)
    _assert_no_medium_or_above(findings, "IP Assignment")


# ---------------------------------------------------------------------------
# 9. Equipment Lease Agreement
# ---------------------------------------------------------------------------
def test_benign_09_equipment_lease():
    intro = (
        "Between: HeavyMach Leasing Corp. (Lessor) and "
        "BuildWell Construction LLC (Lessee)"
    )
    clauses = [
        ("1", "Equipment Schedule", "Lessor leases heavy earthmoving equipment as detailed in Clause 2."),
        ("2", "Monthly Rent", "Lessee shall pay $15,000 (Fifteen thousand Dollars) per month."),
        ("3", "Maintenance", "Routine maintenance performed every thirty (30) days."),
        ("4", "Statutory Rights", "Lease is governed under Article 2A of the Uniform Commercial Code."),
        ("5", "Term", "Effective on 01/06/2025 and ends on 01/06/2027."),
        ("6", "Return of Equipment", "Returned in good working order."),
    ]
    doc = _make_doc(intro, clauses)
    findings = _run_all_detectors(doc)
    _assert_no_medium_or_above(findings, "Equipment Lease")


# ---------------------------------------------------------------------------
# 10. Tripartite Escrow Agreement
# ---------------------------------------------------------------------------
def test_benign_10_tripartite_escrow():
    intro = (
        "This Escrow Agreement is entered into by and among "
        "Acme Realty Private Limited (Seller), "
        "Premier Buyer Corp. (Buyer), and "
        "HDFC Bank Ltd. (Escrow Agent)."
    )
    clauses = [
        ("1", "Escrow Account", "Escrow Agent opens designated escrow account pursuant to Clause 2."),
        ("2", "Deposit Amount", "Buyer deposits Rs. 5,00,00,000 (Rupees Five crore only) upon signing."),
        ("3", "Release Conditions", "Escrow funds released upon mutual instructions under Clause 1."),
        ("4", "Term", "Effective from 01/09/2025 until 01/09/2026."),
        ("5", "Banking Regulations", "Subject to the Banking Regulation Act, 1949 and RBI circulars."),
    ]
    doc = _make_doc(intro, clauses)
    findings = _run_all_detectors(doc)
    _assert_no_medium_or_above(findings, "Tripartite Escrow")


# ---------------------------------------------------------------------------
# 11. Indian Loan and Security Agreement
# ---------------------------------------------------------------------------
def test_benign_11_loan_and_security():
    intro = (
        "This Facility Agreement dated 15/03/2025 is between "
        "Capital Finance NBFC Ltd. ('Lender') and "
        "Sunrise Enterprises Pvt. Ltd. ('Borrower')."
    )
    clauses = [
        ("1", "Facility Amount", "Lender sanctions term loan of Rs. 80,00,000 (Rupees Eighty lakh only)."),
        ("2", "Interest Rate", "Interest rate shall be ten percent (10%) per annum."),
        ("3", "Repayment", "Repayable in twenty-four (24) equal monthly installments."),
        ("4", "Security Enforcement", "Enforceable under the SARFAESI Act, 2002 upon event of default."),
        ("5", "Term", "Effective on 15/03/2025 and shall expire on 15/03/2027."),
    ]
    doc = _make_doc(intro, clauses)
    findings = _run_all_detectors(doc)
    _assert_no_medium_or_above(findings, "Loan and Security")


# ---------------------------------------------------------------------------
# 12. Share Purchase Agreement
# ---------------------------------------------------------------------------
def test_benign_12_share_purchase():
    intro = (
        "This Share Purchase Agreement is made on 10/10/2025 between "
        "Prime Equity Partners Ltd. (Purchaser) and "
        "Founders Holdings Private Limited (Seller)."
    )
    clauses = [
        ("1", "Purchased Shares", "Purchaser acquires 10,000 (ten thousand) equity shares."),
        ("2", "Consideration", "Purchase price is Rs. 10,00,00,000 (Rupees Ten crore only)."),
        ("3", "Conditions Precedent", "All regulatory approvals obtained in accordance with Clause 4."),
        ("4", "FEMA Compliance", "Complies with Foreign Exchange Management Act, 1999 regulations."),
        ("5", "Closing Date", "Effective as of 10/10/2025 and transaction terminates on 10/10/2026."),
    ]
    doc = _make_doc(intro, clauses)
    findings = _run_all_detectors(doc)
    _assert_no_medium_or_above(findings, "Share Purchase")
