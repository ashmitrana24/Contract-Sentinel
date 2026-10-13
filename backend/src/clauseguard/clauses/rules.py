"""Rule-based pattern matcher for clause classification.

Provides deterministic keyword and regex detection across all 45 taxonomy labels
(36 CUAD contractual categories + 9 extra rule-only risk categories).
Extracts localized evidence snippets (<=300 chars) and flags matches with method='rules'.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from clauseguard.clauses.windows import truncate_evidence


@dataclass(frozen=True)
class RulePattern:
    """Compiled rule definition for a clause label."""

    label: str
    patterns: tuple[re.Pattern[str], ...]
    negative_patterns: tuple[re.Pattern[str], ...] = ()
    heading_patterns: tuple[re.Pattern[str], ...] = ()
    confidence: float = 0.90


def _c(pattern: str, flags: int = re.IGNORECASE) -> re.Pattern[str]:
    return re.compile(pattern, flags)


# Pattern catalog for all 45 categories
_RULES: list[RulePattern] = [
    # -------------------------------------------------------------------------
    # 36 CORE CUAD LABELS
    # -------------------------------------------------------------------------
    RulePattern(
        label="governing_law",
        patterns=(
            _c(r"governed\s+by\s+(?:and\s+construed\s+in\s+accordance\s+with\s+)?the\s+laws\s+of"),
            _c(r"construed\s+(?:and\s+enforced\s+)?in\s+accordance\s+with\s+the\s+laws\s+of"),
            _c(r"exclusive\s+jurisdiction\s+(?:of\s+the\s+courts\s+of|in)"),
            _c(r"submit\s+to\s+the\s+(?:non-)?exclusive\s+jurisdiction\s+of"),
            _c(r"venue\s+[^.\n]{0,100}?shall\s+be\s+(?:in\s+)?(?:the\s+courts\s+of|in)"),
            _c(r"courts\s+of\s+[A-Za-z\s,]+\s+shall\s+have\s+(?:exclusive\s+)?jurisdiction"),
        ),
        heading_patterns=(_c(r"governing\s+law|applicable\s+law|jurisdiction\s+and\s+venue"),),
    ),
    RulePattern(
        label="renewal_term",
        patterns=(
            _c(r"(?:automatically\s+)?renew(?:ed|s)?\s+for\s+(?:(?:additional|successive)\s+)?(?:successive\s+)?(?:periods?\s+of|terms?\s+of|[\w-]+\s+terms?|\d+|one|two|three|five|twelve)"),
            _c(r"renewal\s+term\s+of\s+(?:\d+|one|two|three|twelve|[\w-]+)"),
            _c(r"extended\s+for\s+(?:an\s+additional|successive)\s+(?:period|term)\s+of"),
            _c(r"(?:extended|renewed)\s+for\s+successive\s+terms?\s+of"),
            _c(r"(?:each\s+such\s+(?:annual\s+)?extension\s+)?shall\s+be\s+deemed\s+a\s+renewal\s+term"),
        ),
        heading_patterns=(_c(r"renewal(?:\s+term)?|extension\s+of\s+term"),),
    ),
    RulePattern(
        label="notice_period_to_terminate_renewal",
        patterns=(
            _c(r"notice\s+(?:of\s+non-renewal|not\s+to\s+renew)"),
            _c(r"at\s+least\s+\d+\s+days?\s+(?:prior|written\s+notice)\s+(?:to\s+the\s+end\s+of|before\s+expiration)"),
            _c(r"written\s+notice\s+of\s+its\s+intention\s+not\s+to\s+renew\s+(?:at\s+least\s+)?\d+\s+days"),
            _c(r"terminate\s+(?:this\s+agreement\s+at\s+the\s+end\s+of\s+the\s+initial\s+term|renewal)\s+upon\s+\d+\s+days"),
        ),
    ),
    RulePattern(
        label="most_favored_nation",
        patterns=(
            _c(r"most\s+favou?red\s+(?:nation|customer|licensee|client)"),
            _c(r"terms?\s+no\s+less\s+favou?rable\s+than"),
            _c(r"prices?\s+no\s+higher\s+than\s+(?:the\s+lowest\s+price\s+offered|those\s+charged)"),
            _c(r"more\s+favou?rable\s+(?:terms?|pricing)\s+to\s+any\s+third\s+party"),
        ),
        heading_patterns=(_c(r"most\s+favou?red"),),
    ),
    RulePattern(
        label="non_compete",
        patterns=(
            _c(r"covenant\s+not\s+to\s+compete"),
            _c(r"shall\s+not\s+(?:directly\s+or\s+indirectly\s+)?(?:engage\s+in(?:\s+or\s+carry\s+on)?|carry\s+on)\s+(?:any\s+)?competing\s+business"),
            _c(r"non-competition\s+covenant"),
            _c(r"refrain\s+from\s+competing\s+with"),
            _c(r"(?:shall\s+not|neither\s+party\s+shall)\s+compete\s+with\s+(?:the\s+company|the\s+firm|either\s+party)"),
        ),
        heading_patterns=(_c(r"non-compete|non-competition|restrictive\s+covenants?"),),
    ),
    RulePattern(
        label="exclusivity",
        patterns=(
            _c(r"exclusive\s+(?:distributor|licensee|agent|supplier|rights?|basis)"),
            _c(r"sole\s+and\s+exclusive\s+right"),
            _c(r"exclusively\s+to\s+(?:the\s+distributor|the\s+company|licensee)"),
            _c(r"shall\s+not\s+appoint\s+any\s+other\s+(?:distributor|agent|reseller)"),
        ),
        heading_patterns=(_c(r"exclusivity|exclusive\s+appointment"),),
    ),
    RulePattern(
        label="no_solicit_of_customers",
        patterns=(
            _c(r"shall\s+not\s+(?:directly\s+or\s+indirectly\s+)?solicit\s+(?:any\s+)?customers?"),
            _c(r"non-solicitation\s+of\s+customers"),
            _c(r"solicit\s+or\s+divert\s+(?:business\s+from\s+)?any\s+client\s+or\s+customer"),
            _c(r"induce\s+any\s+customer\s+to\s+(?:cease\s+doing\s+business|terminate)"),
        ),
        heading_patterns=(_c(r"customer\s+non-solicitation|solicitation\s+of\s+customers"),),
    ),
    RulePattern(
        label="competitive_restriction_exception",
        patterns=(
            _c(r"notwithstanding\s+(?:anything\s+to\s+the\s+contrary\s+in\s+)?(?:the\s+foregoing|this\s+section),\s+nothing\s+shall\s+(?:prohibit|prevent|restrict)"),
            _c(r"exception\s+to\s+(?:non-compete|competitive\s+restrictions?)"),
            _c(r"shall\s+not\s+be\s+deemed\s+a\s+breach\s+of\s+the\s+non-competition"),
            _c(r"passive\s+investment\s+of\s+less\s+than\s+\d+%\s+shall\s+be\s+permitted"),
        ),
    ),
    RulePattern(
        label="no_solicit_of_employees",
        patterns=(
            _c(r"shall\s+not\s+(?:directly\s+or\s+indirectly\s+)?(?:solicit|hire|recruit|induce)\s+(?:any\s+)?employees?"),
            _c(r"non-solicitation\s+of\s+employees"),
            _c(r"solicit\s+for\s+employment\s+any\s+person\s+employed\s+by"),
            _c(r"induce\s+any\s+employee\s+to\s+leave\s+(?:their\s+employment|the\s+company)"),
        ),
        heading_patterns=(_c(r"employee\s+non-solicitation|solicitation\s+of\s+employees"),),
    ),
    RulePattern(
        label="non_disparagement",
        patterns=(
            _c(r"non-disparagement"),
            _c(r"shall\s+not\s+(?:make\s+any\s+)?disparag(?:ing|e)\s+(?:statements?|remarks?|comments?)"),
            _c(r"refrain\s+from\s+making\s+(?:derogatory|defamatory|negative)\s+statements"),
        ),
        heading_patterns=(_c(r"non-disparagement"),),
    ),
    RulePattern(
        label="termination_for_convenience",
        patterns=(
            _c(r"terminate\s+(?:this\s+(?:agreement|contract|relationship)\s+)?(?:for\s+(?:its\s+|their\s+)?convenience|without\s+cause)"),
            _c(r"terminate\s+(?:this\s+(?:agreement|contract)\s+)?at\s+(?:any\s+time|its\s+(?:sole\s+)?option|will)\s+(?:for\s+any\s+reason\s+or\s+no\s+reason|without\s+cause|without\s+(?:the\s+payment\s+of\s+)?(?:any\s+)?penalty|without\s+liability)"),
            _c(r"upon\s+(?:giving\s+)?\d+\s+days(?:\'\s+|\s+)prior\s+written\s+notice\s+without\s+cause"),
            _c(r"(?:written\s+)?notice\s+without\s+cause,\s+either\s+party\s+may\s+terminate"),
            _c(r"terminate\s+this\s+agreement\s+at\s+any\s+time\s+without\s+(?:the\s+payment\s+of\s+)?(?:any\s+)?penalty"),
            _c(r"unilaterally\s+terminate\s+this\s+agreement"),
            _c(r"terminate\s+(?:this\s+agreement\s+)?for\s+convenience"),
            _c(r"right\s+to\s+terminate\s+(?:this\s+agreement\s+)?before\s+the\s+end\s+of\s+the\s+term\s+for\s+(?:its\s+|their\s+)?convenience"),
        ),
        heading_patterns=(_c(r"termination\s+for\s+convenience|termination\s+without\s+cause"),),
    ),
    RulePattern(
        label="rofr_rofo_rofn",
        patterns=(
            _c(r"right\s+of\s+first\s+refusal"),
            _c(r"right\s+of\s+first\s+offer"),
            _c(r"right\s+of\s+first\s+negotiation"),
            _c(r"\b(?:rofr|rofo|rofn)\b"),
            _c(r"first\s+option\s+to\s+(?:purchase|license|acquire)"),
        ),
        heading_patterns=(_c(r"first\s+refusal|first\s+offer|rofr|rofo"),),
    ),
    RulePattern(
        label="change_of_control",
        patterns=(
            _c(r"change\s+of\s+control"),
            _c(r"change\s+in\s+control"),
            _c(r"merger,\s+consolidation\s+or\s+sale\s+of\s+all\s+or\s+substantially\s+all"),
            _c(r"acquisition\s+of\s+(?:more\s+than\s+)?50%\s+of\s+the\s+voting\s+(?:shares|stock)"),
        ),
        heading_patterns=(_c(r"change\s+of\s+control|change\s+in\s+control"),),
    ),
    RulePattern(
        label="anti_assignment",
        patterns=(
            _c(r"shall\s+not\s+assign\s+(?:or\s+transfer\s+)?this\s+agreement\s+without\s+(?:the\s+)?prior\s+written\s+consent"),
            _c(r"neither\s+party\s+may\s+assign\s+(?:its\s+rights\s+or\s+obligations\s+under\s+)?this\s+agreement"),
            _c(r"(?:any\s+)?(?:attempted\s+)?assignment\s+(?:or\s+delegation\s+)?without\s+(?:such\s+)?consent\s+shall\s+be\s+null\s+and\s+void"),
            _c(r"anti-assignment"),
            _c(r"shall\s+not\s+be\s+assignable\s+by\s+either\s+party\s+without"),
            _c(r"no\s+assignment\s+of\s+this\s+agreement\s+or\s+any\s+right\s+accruing\s+hereunder"),
        ),
        heading_patterns=(_c(r"assignment|anti-assignment"),),
    ),
    RulePattern(
        label="revenue_profit_sharing",
        patterns=(
            _c(r"revenue\s+shar(?:ing|e)"),
            _c(r"profit\s+shar(?:ing|e)"),
            _c(r"royalty\s+(?:rate|payment|fee)\s+of\s+\d+%\s+of\s+net\s+(?:sales|revenue)"),
            _c(r"share\s+in\s+the\s+(?:net\s+)?profits\s+derived\s+from"),
        ),
        heading_patterns=(_c(r"revenue\s+share|profit\s+share|royalties"),),
    ),
    RulePattern(
        label="price_restrictions",
        patterns=(
            _c(r"price\s+(?:increases?|adjustments?)\s+shall\s+not\s+exceed"),
            _c(r"prices?\s+shall\s+remain\s+fixed\s+for\s+(?:a\s+period\s+of|\d+)"),
            _c(r"price\s+(?:restrictions?|ceiling|cap)"),
            _c(r"not\s+increase\s+(?:its\s+)?prices\s+more\s+than\s+once\s+per"),
        ),
    ),
    RulePattern(
        label="minimum_commitment",
        patterns=(
            _c(r"minimum\s+(?:purchase|annual|quarterly|monthly)\s+(?:commitment|requirement|volume|order)"),
            _c(r"guaranteed\s+minimum\s+(?:revenue|amount|payment)"),
            _c(r"take-or-pay"),
            _c(r"shall\s+purchase\s+not\s+less\s+than\s+\$?[\d,]+\s+of"),
        ),
        heading_patterns=(_c(r"minimum\s+commitment|minimum\s+purchase|minimum\s+orders?"),),
    ),
    RulePattern(
        label="volume_restriction",
        patterns=(
            _c(r"volume\s+(?:restriction|limit|cap)"),
            _c(r"maximum\s+(?:usage|volume|number\s+of\s+units)"),
            _c(r"shall\s+not\s+exceed\s+a\s+total\s+of\s+\d+\s+(?:units|transactions|calls)"),
        ),
    ),
    RulePattern(
        label="ip_ownership_assignment",
        patterns=(
            _c(r"(?:hereby\s+)?assigns?\s+(?:to\s+[A-Za-z\s]+)?all\s+(?:right,\s+title\s+and\s+interest\s+in|intellectual\s+property)"),
            _c(r"work\s+(?:made\s+)?for\s+hire"),
            _c(r"assignment\s+of\s+(?:inventions|intellectual\s+property|developments)"),
            _c(r"shall\s+be\s+the\s+sole\s+and\s+exclusive\s+property\s+of"),
        ),
        heading_patterns=(_c(r"intellectual\s+property\s+ownership|assignment\s+of\s+ip|inventions"),),
    ),
    RulePattern(
        label="joint_ip_ownership",
        patterns=(
            _c(r"jointly\s+own\s+(?:all\s+right,\s+title\s+and\s+interest|any\s+intellectual\s+property)"),
            _c(r"joint\s+ownership\s+of\s+(?:intellectual\s+property|developments|ip)"),
            _c(r"co-ownership\s+of\s+inventions"),
            _c(r"undivided\s+(?:one-half\s+)?interest\s+in\s+and\s+to"),
        ),
        heading_patterns=(_c(r"joint\s+(?:ip|intellectual\s+property)\s+ownership"),),
    ),
    RulePattern(
        label="license_grant",
        patterns=(
            _c(r"(?:hereby\s+)?grants?\s+(?:to\s+[A-Za-z\s]+)?a\s+(?:non-exclusive|exclusive|personal)?\s+license\s+to"),
            _c(r"license\s+grant"),
            _c(r"grants?\s+a\s+worldwide,\s+royalty-free,\s+non-exclusive\s+license"),
            _c(r"subject\s+to\s+the\s+terms\s+of\s+this\s+agreement,\s+licensor\s+grants"),
        ),
        heading_patterns=(_c(r"grant\s+of\s+license|license\s+grant"),),
    ),
    RulePattern(
        label="non_transferable_license",
        patterns=(
            _c(r"non-transferable\s+(?:and\s+non-assignable\s+)?license"),
            _c(r"license\s+is\s+non-transferable"),
            _c(r"without\s+the\s+right\s+to\s+(?:sublicense\s+or\s+)?transfer"),
            _c(r"nontransferable,\s+non-exclusive"),
        ),
    ),
    RulePattern(
        label="affiliate_license_licensor",
        patterns=(
            _c(r"licensor\s+(?:and|or)\s+its\s+affiliates\s+(?:grant|shall\s+have\s+the\s+right)"),
            _c(r"license\s+granted\s+by\s+licensor\'?s?\s+affiliates"),
        ),
    ),
    RulePattern(
        label="affiliate_license_licensee",
        patterns=(
            _c(r"licensee\s+and\s+its\s+affiliates\s+(?:may\s+use|shall\s+have\s+the\s+right)"),
            _c(r"extended\s+to\s+licensee\'?s?\s+affiliates"),
            _c(r"affiliates\s+of\s+licensee\s+shall\s+be\s+entitled\s+to\s+exercise"),
        ),
    ),
    RulePattern(
        label="unlimited_all_you_can_eat_license",
        patterns=(
            _c(r"unlimited\s+(?:enterprise|user|site)\s+license"),
            _c(r"unlimited\s+number\s+of\s+(?:users|copies|servers|installations)"),
            _c(r"all-you-can-eat\s+license"),
            _c(r"enterprise-wide\s+license\s+without\s+(?:seat|user)\s+limitations?"),
        ),
    ),
    RulePattern(
        label="irrevocable_or_perpetual_license",
        patterns=(
            _c(r"perpetual\s+and\s+irrevocable\s+license"),
            _c(r"irrevocable,\s+perpetual"),
            _c(r"perpetual,\s+fully\s+paid-up,\s+royalty-free"),
            _c(r"license\s+shall\s+continue\s+in\s+perpetuity"),
        ),
    ),
    RulePattern(
        label="source_code_escrow",
        patterns=(
            _c(r"source\s+code\s+escrow"),
            _c(r"deposit\s+(?:of\s+)?the\s+source\s+code\s+with\s+(?:an\s+)?escrow\s+agent"),
            _c(r"release\s+of\s+source\s+code\s+from\s+escrow"),
            _c(r"escrow\s+agreement\s+for\s+source\s+code"),
        ),
        heading_patterns=(_c(r"source\s+code\s+escrow|escrow"),),
    ),
    RulePattern(
        label="post_termination_services",
        patterns=(
            _c(r"post-termination\s+(?:services|assistance|obligations)"),
            _c(r"transition\s+services\s+(?:following|upon)\s+termination"),
            _c(r"disengagement\s+assistance"),
            _c(r"continue\s+to\s+provide\s+services\s+for\s+a\s+period\s+of\s+\d+\s+days\s+following\s+termination"),
        ),
        heading_patterns=(_c(r"transition\s+services|post-termination\s+services"),),
    ),
    RulePattern(
        label="audit_rights",
        patterns=(
            _c(r"right\s+to\s+audit"),
            _c(r"inspect\s+(?:and\s+audit\s+)?(?:the\s+)?books\s+and\s+records"),
            _c(r"upon\s+reasonable\s+(?:prior\s+)?notice,\s+(?:audit|examine|inspect)"),
            _c(r"(?:audit,\s+examine,\s+or\s+inspect|examine\s+or\s+inspect)\s+(?:the\s+)?(?:facilities|records|books)"),
            _c(r"examination\s+of\s+accounting\s+records"),
            _c(r"(?:permit|allow)\s+[^.\n]{0,50}(?:accountants|auditors)\s+to\s+examine\s+accounting\s+records"),
            _c(r"inspection\s+of\s+the\s+books,\s+accounts"),
        ),
        heading_patterns=(_c(r"audit\s+rights?|books\s+and\s+records|inspection\s+rights?"),),
    ),
    RulePattern(
        label="uncapped_liability",
        patterns=(
            _c(r"shall\s+not\s+apply\s+to\s+(?:or\s+limit\s+)?liability\s+(?:for|arising\s+from)"),
            _c(r"nothing\s+in\s+this\s+agreement\s+shall\s+(?:exclude\s+or\s+limit|apply\s+to\s+limit|limit)\s+(?:either\s+party\'?s?\s+)?liability"),
            _c(r"(?:shall|will)\s+not\s+(?:apply\s+to\s+)?limit\s+(?:the\s+)?(?:liability|licensor|licensee|either\s+party)"),
            _c(r"such\s+limitation\s+(?:shall|will)\s+not\s+apply"),
            _c(r"(?:provisions?\s+of\s+section\s+[0-9.]+\s+)?(?:will|shall)\s+not\s+apply\s+to\s+limit"),
            _c(r"except\s+(?:for\s+liability|for\s+claims|in\s+connection\s+with\s+a\s+breach|in\s+the\s+event\s+of\s+\(?[a-z0-9ivx]+\)?\s+third\s+party|for\s+amounts\s+payable|for\s+breach\s+of\s+confidentiality)"),
            _c(r"excluding\s+liability\s+for"),
            _c(r"liability\s+(?:for\s+gross\s+negligence|willful\s+misconduct)\s+shall\s+not\s+be\s+(?:limited|capped)"),
            _c(r"liability\s+for\s+[^.\n]{0,80}\s+shall\s+be\s+uncapped"),
            _c(r"liability\s+cap\s+(?:under\s+Section\s+\d+\s+)?shall\s+not\s+apply"),
            _c(r"exclusions?\s+from\s+(?:the\s+)?limitation\s+of\s+liability"),
            _c(r"uncapped\s+liability"),
        ),
        heading_patterns=(_c(r"exceptions?\s+to\s+(?:the\s+)?limitation\s+of\s+liability"),),
    ),
    RulePattern(
        label="cap_on_liability",
        patterns=(
            _c(r"(?:total\s+)?(?:aggregate|total|cumulative)\s+liability\s+(?:of\s+either\s+party\s+)?(?:under\s+this\s+agreement\s+)?shall\s+(?:in\s+no\s+event|not)\s+exceed"),
            _c(r"(?:maximum\s+)?liability\s+(?:is|shall\s+be)\s+capped\s+at"),
            _c(r"limitation\s+of\s+liability"),
            _c(r"in\s+no\s+event\s+shall\s+(?:either\s+party\'?s?\s+)?(?:total\s+(?:cumulative\s+)?)?liability\s+(?:under\s+this\s+agreement\s+)?exceed"),
            _c(r"liability\s+[^.\n]{0,60}?\s+is\s+limited\s+to"),
            _c(r"shall\s+not\s+exceed\s+(?:the\s+total\s+)?(?:fees?|amounts?|payments?)\s+(?:paid|payable)"),
            _c(r"(?:sole\s+and\s+exclusive\s+remedy|exclusive\s+remedy\s+for)"),
        ),
        heading_patterns=(_c(r"limitation\s+of\s+liability|liability\s+cap"),),
    ),
    RulePattern(
        label="liquidated_damages",
        patterns=(
            _c(r"liquidated\s+damages"),
            _c(r"parties\s+agree\s+that\s+actual\s+damages\s+would\s+be\s+difficult\s+to\s+ascertain"),
            _c(r"pre-agreed\s+sum\s+as\s+liquidated\s+damages"),
        ),
        heading_patterns=(_c(r"liquidated\s+damages"),),
    ),
    RulePattern(
        label="warranty_duration",
        patterns=(
            _c(r"warranty\s+period\s+of\s+\d+\s+(?:days|months|years)"),
            _c(r"warrant(?:s|y)\s+for\s+(?:a\s+period\s+of\s+)?\d+\s+(?:days|months|years)"),
            _c(r"duration\s+of\s+the\s+warranty\s+shall\s+be"),
        ),
        heading_patterns=(_c(r"warranty\s+duration|warranty\s+period"),),
    ),
    RulePattern(
        label="insurance",
        patterns=(
            _c(r"(?:maintain|procure)\s+(?:commercial\s+general\s+liability|comprehensive)\s+insurance"),
            _c(r"insurance\s+coverage\s+in\s+an\s+amount\s+not\s+less\s+than"),
            _c(r"certificate\s+of\s+insurance"),
            _c(r"workers\'?\s+compensation\s+insurance"),
        ),
        heading_patterns=(_c(r"insurance(?:\s+requirements)?|coverage"),),
    ),
    RulePattern(
        label="covenant_not_to_sue",
        patterns=(
            _c(r"covenant\s+not\s+to\s+sue"),
            _c(r"agrees\s+not\s+to\s+(?:institute|assert|commence)\s+any\s+(?:suit|claim|action)\s+against"),
            _c(r"covenants?\s+that\s+it\s+shall\s+not\s+sue"),
        ),
        heading_patterns=(_c(r"covenant\s+not\s+to\s+sue"),),
    ),
    RulePattern(
        label="third_party_beneficiary",
        patterns=(
            _c(r"no\s+third\s+party\s+beneficiar(?:y|ies)"),
            _c(r"shall\s+not\s+confer\s+any\s+rights\s+or\s+remedies\s+upon\s+any\s+person\s+other\s+than\s+the\s+parties"),
            _c(r"intended\s+third\s+party\s+beneficiar"),
            _c(r"nothing\s+in\s+this\s+agreement\s+is\s+intended\s+to\s+confer\s+any\s+benefit\s+on\s+any\s+third\s+party"),
        ),
        heading_patterns=(_c(r"third\s+party\s+beneficiaries|no\s+third-party\s+rights"),),
    ),
    # -------------------------------------------------------------------------
    # 9 EXTRA RULE-ONLY LABELS
    # -------------------------------------------------------------------------
    RulePattern(
        label="indemnification",
        patterns=(
            _c(r"(?:shall\s+|agrees\s+to\s+)?(?:indemnify,\s+defend\s+and\s+hold\s+harmless|defend,\s+indemnify,\s+and\s+hold\s+harmless|indemnify\s+and\s+hold\s+harmless)"),
            _c(r"shall\s+indemnify\s+and\s+hold\s+harmless"),
            _c(r"indemnification\s+obligations?"),
            _c(r"defend\s+against\s+any\s+third[- ]party\s+claims"),
        ),
        heading_patterns=(_c(r"indemnification|indemnity"),),
    ),
    RulePattern(
        label="confidentiality",
        patterns=(
            _c(r"confidential\s+information"),
            _c(r"non-disclosure\s+of\s+proprietary\s+information"),
            _c(r"shall\s+maintain\s+in\s+strict\s+confidence"),
            _c(r"duty\s+of\s+confidentiality"),
        ),
        heading_patterns=(_c(r"confidentiality|non-disclosure|proprietary\s+information"),),
    ),
    RulePattern(
        label="payment_terms",
        patterns=(
            _c(r"payment\s+shall\s+be\s+due\s+(?:within|in)\s+(?:\d+|thirty|forty-five|sixty|ninety|fifteen)"),
            _c(r"payable\s+(?:Net\s+\d+|within\s+\d+\s+(?:business\s+)?days)"),
            _c(r"net\s+\d+\s+days"),
            _c(r"invoiced\s+(?:monthly|quarterly|annually)"),
            _c(r"billed\s+(?:monthly|quarterly|annually)"),
            _c(r"late\s+payment\s+interest\s+(?:charge|rate)"),
        ),
        heading_patterns=(_c(r"payment\s+terms|invoicing\s+and\s+payment|fees\s+and\s+payment"),),
    ),
    RulePattern(
        label="unilateral_amendment",
        patterns=(
            _c(r"(?:may|reserves?\s+the\s+right\s+to)\s+(?:amend|modify|update|change)\s+(?:these\s+terms|this\s+agreement|these\s+conditions)\s+at\s+any\s+time"),
            _c(r"modify\s+(?:or\s+amend\s+)?these\s+terms\s+at\s+any\s+time\s+(?:in\s+its\s+sole\s+discretion|without\s+notice)"),
            _c(r"reserves\s+the\s+right\s+to\s+update\s+or\s+modify\s+this\s+agreement\s+unilaterally"),
            _c(r"(?:update|modify|change)\s+this\s+agreement\s+unilaterally"),
            _c(r"sole\s+discretion\s+to\s+change\s+any\s+terms"),
        ),
        heading_patterns=(_c(r"unilateral\s+amendment|changes\s+to\s+terms"),),
    ),
    RulePattern(
        label="force_majeure",
        patterns=(
            _c(r"force\s+majeure"),
            _c(r"acts\s+of\s+god,\s+(?:war,\s+terrorism|floods,\s+earthquakes)"),
            _c(r"causes\s+beyond\s+(?:the\s+)?reasonable\s+control\s+of\s+such\s+party"),
            _c(r"delays\s+caused\s+by\s+circumstances\s+beyond\s+(?:the\s+)?reasonable\s+control"),
            _c(r"excused\s+from\s+performance\s+due\s+to\s+events\s+beyond"),
            _c(r"(?:failure\s+or\s+delay\s+in\s+delivery|delay\s+or\s+failure)\s+shall\s+be\s+excused\s+if\s+resulting\s+from"),
        ),
        heading_patterns=(_c(r"force\s+majeure"),),
    ),
    RulePattern(
        label="arbitration_or_dispute_resolution",
        patterns=(
            _c(r"binding\s+arbitration"),
            _c(r"american\s+arbitration\s+association"),
            _c(r"jams\s+arbitration\s+rules"),
            _c(r"dispute\s+resolution\s+by\s+arbitration"),
            _c(r"arbitrated\s+in\s+accordance\s+with"),
        ),
        heading_patterns=(_c(r"arbitration|dispute\s+resolution"),),
    ),
    RulePattern(
        label="waiver_of_rights",
        patterns=(
            _c(r"waiver\s+of\s+jury\s+trial"),
            _c(r"waives\s+any\s+right\s+to\s+a\s+trial\s+by\s+jury"),
            _c(r"waiver\s+of\s+class\s+action"),
            _c(r"failure\s+(?:of\s+either\s+party\s+)?to\s+enforce\s+(?:any\s+provision\s+)?shall\s+not\s+(?:operate\s+as|constitute)\s+a\s+waiver"),
            _c(r"no\s+waiver\s+of\s+any\s+breach\s+shall\s+constitute\s+a\s+continuing\s+waiver"),
        ),
        heading_patterns=(_c(r"waiver(?:\s+of\s+jury\s+trial)?|no\s+waiver"),),
    ),
    RulePattern(
        label="termination_for_cause",
        patterns=(
            _c(r"terminate\s+(?:this\s+agreement\s+)?for\s+cause"),
            _c(r"material\s+breach\s+and\s+fail(?:ure|s)\s+to\s+cure\s+within\s+\d+\s+days"),
            _c(r"immediate\s+termination\s+upon\s+(?:written\s+notice\s+if|bankruptcy\s+or\s+insolvency)"),
            _c(r"terminate\s+immediately\s+upon\s+material\s+default"),
            _c(r"terminate\s+for\s+default\s+if\s+the\s+other\s+party\s+fails\s+to\s+remedy"),
        ),
        heading_patterns=(_c(r"termination\s+for\s+cause|termination\s+for\s+breach|default\s+and\s+termination"),),
    ),
    RulePattern(
        label="auto_renewal",
        patterns=(
            _c(r"automatically\s+renew(?:s|ed)?"),
            _c(r"auto-renew(?:al)?"),
            _c(r"evergreen\s+(?:contract|clause|provision)"),
            _c(r"renew\s+automatically\s+unless\s+either\s+party\s+gives\s+written\s+notice"),
        ),
        heading_patterns=(_c(r"auto-renewal|automatic\s+renewal"),),
    ),
]


def classify_clause_rules(
    clause_text: str,
    heading: str = "",
    min_confidence: float = 0.85,
) -> list[dict[str, Any]]:
    """Match a clause against the rules catalog.

    Returns a list of match dicts:
      [{'label': str, 'score': float, 'method': 'rules', 'evidence': str}]
    """
    matches: list[dict[str, Any]] = []
    heading_lower = heading.lower().strip()
    full_text = f"{heading}\n{clause_text}" if heading else clause_text
    clause_normalized = re.sub(r"\s+", " ", clause_text).strip()
    full_normalized = re.sub(r"\s+", " ", full_text).strip()

    for rule in _RULES:
        # Check negative patterns first (if any match, skip rule)
        if any(neg.search(full_text) or neg.search(full_normalized) for neg in rule.negative_patterns):
            continue

        matched_span_text = ""
        matched = False

        # 1. Check body and full text patterns
        for pat in rule.patterns:
            m = pat.search(clause_text) or pat.search(clause_normalized) or pat.search(full_text) or pat.search(full_normalized)
            if m:
                matched = True
                # Extract sentence around match for evidence
                matched_source = clause_text if pat.search(clause_text) else full_text
                start = max(0, m.start() - 50)
                end = min(len(matched_source), m.end() + 100)
                matched_span_text = matched_source[start:end]
                break

        # 2. Check heading patterns if body didn't match
        if not matched and heading_lower and rule.heading_patterns:
            for hpat in rule.heading_patterns:
                if hpat.search(heading_lower):
                    matched = True
                    matched_span_text = f"Heading: {heading}. {clause_text[:150]}"
                    break

        if matched:
            evidence = truncate_evidence(matched_span_text, max_chars=300)
            matches.append({
                "label": rule.label,
                "score": rule.confidence,
                "method": "rules",
                "evidence": evidence,
            })

    # Sort deterministically
    matches.sort(key=lambda x: (-x["score"], x["label"]))
    return matches
