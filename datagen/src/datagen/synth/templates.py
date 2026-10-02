"""Static template data for the synthetic contract builder.

Each contract type has:
  - title_template: str with {party_a} and {party_b} placeholders
  - clause_bank: list of (heading_template, body_template) tuples
  - min_clauses, max_clauses: how many clauses to pick (8-20)

Templates use simple {key} substitution via str.format_map().
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Party name pools (first/last names; combined as "Firstname Lastname Pvt Ltd")
# ---------------------------------------------------------------------------

COMPANY_PREFIXES = [
    "Apex",
    "Indra",
    "Bharat",
    "Nova",
    "Delta",
    "Synergy",
    "Horizon",
    "Pinnacle",
    "Summit",
    "Vanguard",
    "Nexus",
    "Stellar",
    "Prime",
    "Meridian",
    "Catalyst",
]

COMPANY_SUFFIXES = [
    "Technologies",
    "Solutions",
    "Consulting",
    "Services",
    "Industries",
    "Ventures",
    "Enterprises",
    "Systems",
    "Group",
    "Associates",
    "Partners",
    "Global",
    "Innovations",
    "Dynamics",
    "Networks",
]

COMPANY_TYPES = ["Pvt. Ltd.", "LLP", "Ltd.", "Inc.", "Corp."]

GOVERNING_LAWS = [
    "the laws of India",
    "the laws of England and Wales",
    "the laws of the State of New York",
    "the laws of Singapore",
    "the laws of the State of Delaware",
]

CITIES = [
    "Mumbai",
    "Bengaluru",
    "Delhi",
    "Hyderabad",
    "Pune",
    "Chennai",
    "Kolkata",
    "Ahmedabad",
    "Noida",
    "Gurugram",
]

# ---------------------------------------------------------------------------
# Clause banks (shared across contract types; each builder selects a subset)
# ---------------------------------------------------------------------------

# Format placeholders available in bodies:
#   {party_a}   first party name
#   {party_b}   second party name
#   {eff_date}  effective date
#   {term_date} termination date
#   {amount}    primary monetary amount (figure + words)
#   {notice}    notice period in days
#   {city}      governing city
#   {law}       governing law
#   {xref_N}    cross-reference to clause N (filled at build time)

COMMON_CLAUSES: list[tuple[str, str]] = [
    (
        "Definitions",
        "In this Agreement, the following terms shall have the meanings ascribed to them herein. "
        '"Agreement" means this {contract_type} Agreement dated {eff_date} between {party_a} and {party_b}. '
        '"Services" means the services described in {xref_services}. '
        '"Confidential Information" means any information disclosed by either Party that is designated as confidential '
        "or that reasonably should be understood to be confidential given the nature of the information.",
    ),
    (
        "Term",
        "This Agreement shall commence on the Effective Date, {eff_date}, and shall continue until {term_date}, "
        "unless earlier terminated in accordance with {xref_termination}. "
        "Upon expiry, both Parties shall fulfil all outstanding obligations within fifteen (15) days.",
    ),
    (
        "Payment Terms",
        "{party_b} shall pay {party_a} a fee of {amount} for the Services rendered under this Agreement. "
        "Payment shall be made within thirty (30) days of receipt of an invoice. "
        "All amounts are exclusive of applicable taxes, which shall be borne by {party_b}. "
        "Late payments shall attract interest at the rate of eighteen percent (18%) per annum.",
    ),
    (
        "Scope of Services",
        "{party_a} shall provide to {party_b} the following services as detailed in Schedule A attached hereto: "
        "project management, technical implementation, quality assurance, documentation, and post-deployment support. "
        "Any modification to the scope of services must be agreed in writing by both Parties.",
    ),
    (
        "Confidentiality",
        "Each Party agrees to keep confidential all Confidential Information received from the other Party. "
        "This obligation shall survive termination of this Agreement for a period of three (3) years. "
        "Disclosure is permitted only to employees or advisors who have a need to know and are bound by "
        "obligations at least as restrictive as those set forth herein.",
    ),
    (
        "Intellectual Property",
        "All intellectual property rights in deliverables created specifically for {party_b} under this Agreement "
        "shall vest in {party_b} upon full payment. Pre-existing intellectual property of each Party shall remain "
        "with that Party. {party_a} grants {party_b} a non-exclusive, royalty-free licence to use any pre-existing "
        "intellectual property embedded in the deliverables solely for {party_b}'s internal business purposes.",
    ),
    (
        "Representations and Warranties",
        "Each Party represents and warrants that: (a) it has full power and authority to enter into this Agreement; "
        "(b) this Agreement has been duly authorised and constitutes a valid, binding obligation; "
        "(c) the execution, delivery, and performance of this Agreement do not violate any applicable law, "
        "regulation, or third-party agreement.",
    ),
    (
        "Indemnification",
        "{party_a} shall indemnify, defend, and hold harmless {party_b} and its officers, directors, employees, "
        "and agents from and against any claims, losses, damages, liabilities, and expenses (including reasonable "
        "legal fees) arising out of {party_a}'s breach of this Agreement or gross negligence or wilful misconduct. "
        "The indemnifying Party shall have the right to control the defence of any such claim.",
    ),
    (
        "Limitation of Liability",
        "In no event shall either Party be liable to the other for any indirect, incidental, special, consequential, "
        "or punitive damages, including loss of profits or data, even if advised of the possibility thereof. "
        "The aggregate liability of either Party under this Agreement shall not exceed {amount}. "
        "This limitation does not apply to obligations arising from {xref_conf} or indemnification obligations.",
    ),
    (
        "Termination",
        "Either Party may terminate this Agreement by giving {notice} days' written notice to the other Party. "
        "Either Party may terminate immediately upon written notice if the other Party commits a material breach "
        "that is not cured within thirty (30) days of receipt of written notice of such breach. "
        "Upon termination, {party_b} shall pay for all Services rendered up to the date of termination.",
    ),
    (
        "Dispute Resolution",
        "Any dispute arising out of or in connection with this Agreement shall first be submitted to senior "
        "management of both Parties for resolution within thirty (30) days. "
        "If unresolved, disputes shall be referred to binding arbitration under the Arbitration and Conciliation "
        "Act, 1996. The seat of arbitration shall be {city}. The award shall be final and binding.",
    ),
    (
        "Governing Law and Jurisdiction",
        "This Agreement shall be governed by and construed in accordance with {law}. "
        "Subject to {xref_dispute}, the courts of {city} shall have exclusive jurisdiction over any dispute "
        "arising out of or relating to this Agreement.",
    ),
    (
        "Force Majeure",
        "Neither Party shall be liable for any failure or delay in performance under this Agreement (other than "
        "payment obligations) to the extent caused by circumstances beyond the reasonable control of the affected "
        "Party, including but not limited to acts of God, war, terrorism, riots, epidemics, government actions, "
        "or internet or telecommunications failures. The affected Party shall promptly notify the other.",
    ),
    (
        "Notices",
        "All notices under this Agreement shall be in writing and delivered to the addresses set out in Schedule B "
        "by registered post, courier, or email with read receipt. Notices shall be deemed received: "
        "(a) if by registered post, five (5) days after posting; "
        "(b) if by courier, one (1) business day after delivery; "
        "(c) if by email, on the day sent, provided no delivery failure notice is received.",
    ),
    (
        "Assignment",
        "Neither Party may assign or transfer any of its rights or obligations under this Agreement without the "
        "prior written consent of the other Party. Any purported assignment in violation of this clause shall be "
        "null and void. Notwithstanding the foregoing, either Party may assign this Agreement to an affiliate "
        "without consent, provided it gives thirty (30) days' prior written notice.",
    ),
    (
        "Entire Agreement",
        "This Agreement, together with all Schedules and Exhibits attached hereto, constitutes the entire agreement "
        "between the Parties with respect to its subject matter and supersedes all prior negotiations, "
        "representations, warranties, and understandings of any kind, whether written or oral.",
    ),
    (
        "Amendments",
        "No amendment to this Agreement shall be valid unless made in writing and duly signed by authorised "
        "representatives of both Parties. Any waiver of any provision of this Agreement shall be effective "
        "only if in writing and shall not be deemed a waiver of any other provision.",
    ),
    (
        "Severability",
        "If any provision of this Agreement is held to be invalid, illegal, or unenforceable, such provision "
        "shall be modified to the minimum extent necessary to make it valid, legal, and enforceable. "
        "The validity and enforceability of the remaining provisions shall not be affected.",
    ),
    (
        "Non-Solicitation",
        "During the term of this Agreement and for a period of twelve (12) months after its termination, "
        "neither Party shall directly or indirectly solicit or recruit any employee or contractor of the other "
        "Party who was involved in the performance of this Agreement, without prior written consent.",
    ),
    (
        "Data Protection",
        "Each Party shall comply with all applicable data protection laws and regulations. "
        "{party_a} shall process personal data of {party_b}'s employees or customers only as necessary to "
        "perform the Services and strictly in accordance with {party_b}'s written instructions. "
        "{party_a} shall implement appropriate technical and organisational measures to protect such data.",
    ),
    (
        "Insurance",
        "{party_a} shall, throughout the term of this Agreement, maintain at its own cost: "
        "(a) professional indemnity insurance of not less than {amount} per occurrence; "
        "(b) public liability insurance of not less than {amount} per occurrence; "
        "(c) employers' liability insurance as required by applicable law. "
        "{party_a} shall provide evidence of such insurance upon request.",
    ),
    (
        "Subcontracting",
        "{party_a} shall not subcontract any material part of the Services without the prior written consent "
        "of {party_b}. Where subcontracting is permitted, {party_a} shall remain fully responsible for the "
        "performance of the subcontractor and shall ensure the subcontractor is bound by obligations equivalent "
        "to those in {xref_conf} and {xref_ip}.",
    ),
    (
        "Audit Rights",
        "{party_b} or its authorised representative shall have the right, upon giving fifteen (15) days' written "
        "notice, to audit {party_a}'s records relating to the Services and payments under this Agreement. "
        "Such audit shall be conducted during normal business hours and shall not unreasonably disrupt "
        "{party_a}'s operations. The cost of the audit shall be borne by {party_b}, unless the audit reveals "
        "an overcharge of more than five percent (5%), in which case {party_a} shall bear the cost.",
    ),
]

# Type-specific templates
CONTRACT_TYPES: dict[str, dict] = {
    "service_agreement": {
        "title": "MASTER SERVICE AGREEMENT",
        "party_a_role": "Service Provider",
        "party_b_role": "Client",
        "min_clauses": 10,
        "max_clauses": 18,
    },
    "nda": {
        "title": "NON-DISCLOSURE AND CONFIDENTIALITY AGREEMENT",
        "party_a_role": "Disclosing Party",
        "party_b_role": "Receiving Party",
        "min_clauses": 8,
        "max_clauses": 14,
    },
    "lease": {
        "title": "COMMERCIAL LEASE AGREEMENT",
        "party_a_role": "Lessor",
        "party_b_role": "Lessee",
        "min_clauses": 10,
        "max_clauses": 18,
    },
    "employment": {
        "title": "EMPLOYMENT AGREEMENT",
        "party_a_role": "Employer",
        "party_b_role": "Employee",
        "min_clauses": 10,
        "max_clauses": 20,
    },
    "software_license": {
        "title": "SOFTWARE LICENSE AGREEMENT",
        "party_a_role": "Licensor",
        "party_b_role": "Licensee",
        "min_clauses": 10,
        "max_clauses": 18,
    },
    "terms_of_service": {
        "title": "TERMS OF SERVICE AGREEMENT",
        "party_a_role": "Provider",
        "party_b_role": "User",
        "min_clauses": 10,
        "max_clauses": 18,
    },
}

# Risky clauses for clause_insert tamper (at least 8)
RISKY_CLAUSES: list[tuple[str, str]] = [
    (
        "Unilateral Termination",
        "{party_a} reserves the right to terminate this Agreement at any time and for any reason by giving "
        "one (1) hour's written notice to {party_b}, without any liability whatsoever, including without "
        "limitation liability for loss of profits, anticipated savings, or any other consequential loss.",
    ),
    (
        "Unlimited Liability",
        "Notwithstanding any other provision of this Agreement, {party_b} shall be liable to {party_a} for "
        "any and all losses, damages, costs, and expenses of whatsoever nature arising out of or in connection "
        "with this Agreement, without any limitation or cap on such liability.",
    ),
    (
        "Auto-Renewal with Long Notice",
        "This Agreement shall automatically renew for successive periods of five (5) years each unless either "
        "Party provides written notice of non-renewal at least three hundred and sixty (360) days prior to the "
        "expiry of the then-current term. Failure to provide timely notice shall obligate {party_b} to pay "
        "all fees for the renewed term.",
    ),
    (
        "Unilateral Amendment",
        "{party_a} reserves the right to amend any term or condition of this Agreement at any time by posting "
        "a notice on its website or sending an email to {party_b}. Such amendments shall be binding on {party_b} "
        "unless {party_b} terminates this Agreement within seven (7) days of notice.",
    ),
    (
        "Waiver of Rights",
        "{party_b} hereby irrevocably waives any and all rights it may have under applicable consumer protection "
        "laws, data protection laws, and any other statutory rights to the fullest extent permitted by law. "
        "{party_b} further waives the right to participate in any class action or collective proceeding "
        "against {party_a}.",
    ),
    (
        "Perpetual and Irrevocable Licence",
        "{party_b} hereby grants to {party_a} a perpetual, irrevocable, worldwide, royalty-free, fully paid-up "
        "licence to use, reproduce, modify, distribute, sublicense, and exploit all content, data, and materials "
        "provided by {party_b} in connection with this Agreement, for any purpose whatsoever.",
    ),
    (
        "Indemnity Without Cap",
        "{party_b} shall indemnify and hold harmless {party_a} from and against any and all claims, demands, "
        "actions, losses, damages, liabilities, costs, charges, and expenses (including legal fees on a full "
        "indemnity basis) without any limitation or cap, arising out of or related to {party_b}'s use of the "
        "Services, whether or not {party_a} was advised of the possibility of such claims.",
    ),
    (
        "Governing Law Overriding Clause",
        "Notwithstanding the governing law provisions in {xref_governing}, this Agreement shall be interpreted "
        "and enforced exclusively in accordance with the internal laws of the jurisdiction chosen by {party_a} "
        "at the time of any dispute, which {party_a} may change at its sole discretion.",
    ),
    (
        "Non-Compete with No Geographic Limit",
        "{party_b} agrees that during the term of this Agreement and for a period of ten (10) years thereafter, "
        "{party_b} shall not, directly or indirectly, engage in any business activity anywhere in the world "
        "that competes in any manner with the business of {party_a} as conducted at any time during the term.",
    ),
    (
        "Penalty Clause",
        "In the event of any breach of this Agreement by {party_b}, {party_b} shall pay to {party_a} as "
        "liquidated damages (and not as a penalty) a sum equal to three times the total fees payable under "
        "this Agreement, which the Parties agree is a genuine pre-estimate of {party_a}'s loss.",
    ),
]
