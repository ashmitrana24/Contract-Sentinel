"""Words-and-figure pairing engine and consistency detector.

Detects mismatches between written words and figures:
- "WORDS (FIGURE)" and "FIGURE (WORDS)" adjacent pairs inside one sentence.
- Monetary amounts ("Rupees Ten Lakh (Rs. 28,00,000)") -> HIGH.
- Percentages ("five percent (10%)") -> HIGH.
- Date pairs ("1st January 2026 (02/01/2026)") -> HIGH.
- Bare quantities ("thirty (20) days") -> MEDIUM.
- If both sides parse and values differ: Finding(type="figure_words_mismatch").
- If either side cannot be parsed: do not report finding, increment unparseable count.
"""

from __future__ import annotations

import re
from decimal import Decimal

from clauseguard.consistency.dates import parse_date
from clauseguard.consistency.models import (
    CONSISTENCY_MODULE,
    MAX_EVIDENCE_CHARS,
    ConsistencySettings,
)
from clauseguard.consistency.numbers import ParsedNumber, parse_figure, words_to_decimal
from clauseguard.consistency.text_index import TextIndex, split_sentences
from clauseguard.schemas.findings import Finding, Severity
from clauseguard.schemas.parsed import ParsedDocument

# Safe regex matching parenthetical groups within a sentence
_PAREN_RE = re.compile(r"\(([^)\n]{1,80})\)")

_NUMBER_WORD_TOKENS = {
    "zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten",
    "eleven", "twelve", "thirteen", "fourteen", "fifteen", "sixteen", "seventeen", "eighteen", "nineteen",
    "twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety",
    "hundred", "thousand", "lakh", "lakhs", "lac", "crore", "crores", "million", "billion",
    "point", "half", "halves", "quarter", "quarters", "fourth", "fourths", "third", "thirds",
    "and", "a", "an", "only", "rs", "inr", "rupees", "rupee", "usd", "dollars", "dollar", "eur", "euros", "euro",
    "gbp", "pounds", "pound", "percent", "percentage",
}


def _is_number_token(tok: str) -> bool:
    clean = tok.lower().strip(",.-/\"'")
    if "-" in clean:
        parts = clean.split("-")
        return any(p in _NUMBER_WORD_TOKENS for p in parts)
    return clean in _NUMBER_WORD_TOKENS


def detect_pairs(
    doc_or_index: ParsedDocument | TextIndex,
    index_or_settings: TextIndex | ConsistencySettings,
    settings: ConsistencySettings | None = None,
) -> tuple[list[Finding], dict[str, int]]:
    """Detect words-and-figure mismatches in adjacent sentence pairs.

    Returns (findings, stats_dict).
    """
    if isinstance(doc_or_index, TextIndex):
        text_index = doc_or_index
        resolved_settings = index_or_settings if isinstance(index_or_settings, ConsistencySettings) else ConsistencySettings()
    else:
        text_index = index_or_settings  # type: ignore[assignment]
        resolved_settings = settings or ConsistencySettings()
    settings = resolved_settings

    findings: list[Finding] = []
    stats: dict[str, int] = {
        "pairs_found": 0,
        "pairs_verified": 0,
        "pairs_mismatched": 0,
        "pairs_unparseable": 0,
    }

    for segment in text_index.segments:
        if "(" not in segment.text:
            continue
        sentences = split_sentences(segment.text)

        for sentence in sentences:
            if "(" not in sentence:
                continue
            # Find parenthetical groups in sentence
            for m in _PAREN_RE.finditer(sentence):
                inside_raw = m.group(1).strip()
                before_raw = sentence[: m.start()].rstrip()
                before_clean = before_raw.rstrip(",:- ").strip()
                tokens = before_clean.split()
                if not tokens:
                    continue

                # Fast pre-filter for dates
                looks_like_date = (
                    any(c in inside_raw for c in "/.-")
                    or any(
                        m_str in inside_raw.lower()
                        for m_str in ("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec")
                    )
                )
                if looks_like_date and parse_date is not None:
                    d_inside = parse_date(inside_raw, settings.date_format_order)
                    if d_inside is not None:
                        d_before = None
                        d_before_raw = None
                        for k in range(min(len(tokens), 8), 0, -1):
                            cand_d = " ".join(tokens[-k:])
                            parsed_d = parse_date(cand_d, settings.date_format_order)
                            if parsed_d is not None:
                                d_before = parsed_d
                                d_before_raw = cand_d
                                break

                        if d_before is not None:
                            stats["pairs_found"] += 1
                            if d_before.date != d_inside.date:
                                stats["pairs_mismatched"] += 1
                                match_span_end = min(len(sentence), m.end() + 20)
                                snippet = sentence[
                                    max(0, m.start() - len(d_before_raw) - 10) : match_span_end
                                ].strip()
                                evidence = f"{d_before_raw} ({inside_raw}) in snippet: '{snippet}'"[:MAX_EVIDENCE_CHARS]
                                c_info = f" in clause {segment.clause_ref}" if segment.clause_ref else ""
                                explanation = (
                                    f"The date ({d_before.date.isoformat()}) does not match the parenthetical "
                                    f"date ({d_inside.date.isoformat()}){c_info}."
                                )
                                findings.append(
                                    Finding(
                                        module=CONSISTENCY_MODULE,
                                        type="figure_words_mismatch",
                                        severity=Severity.HIGH,
                                        page=segment.page,
                                        clause_ref=segment.clause_ref,
                                        evidence=evidence,
                                        explanation=explanation,
                                        details={
                                            "rule_id": "CONSISTENCY_DATE_PAIR_MISMATCH",
                                            "date_1": d_before.date.isoformat(),
                                            "date_2": d_inside.date.isoformat(),
                                            "raw_1": d_before_raw,
                                            "raw_2": inside_raw,
                                        },
                                    )
                                )
                            else:
                                stats["pairs_verified"] += 1
                            continue

                # Pattern A: WORDS (FIGURE)
                fig_inside = parse_figure(inside_raw)
                if fig_inside is not None:
                    # Skip if the token immediately preceding the parenthetical figure is a conjunction or preposition
                    # e.g. "lesser of (1) zero and (2)" -> (2) is a list item preceded by "and"
                    last_tok = tokens[-1].lower().strip(",.-/\"'")
                    if last_tok in ("and", "or", "to"):
                        continue

                    words_before: ParsedNumber | None = None
                    words_candidate_str = ""
                    if _is_number_token(tokens[-1]):
                        max_k = 0
                        for i in range(1, min(len(tokens) + 1, 15)):
                            if _is_number_token(tokens[-i]):
                                max_k = i
                            else:
                                break

                        for k in range(max_k, 0, -1):
                            cand = " ".join(tokens[-k:])
                            parsed_w = words_to_decimal(cand)
                            if parsed_w is not None:
                                words_before = parsed_w
                                words_candidate_str = cand
                                break

                    if words_before is not None:
                        # Guard: skip if words are a fragment of compound fractional expression
                        # e.g. '1/100th of one percent (0.001%)' should not trigger.
                        _ws_idx = before_raw.rfind(words_candidate_str)
                        _pre_frag = before_raw[max(0, _ws_idx - 35) : _ws_idx].lower() if _ws_idx >= 0 else ""
                        if "/" in _pre_frag or re.search(r"(?:hundredths?|tenths?|thousandths?|half|halves|quarters?|fraction|\d+(?:st|nd|rd|th)s?)\s+of\s*$", _pre_frag):
                            stats["pairs_unparseable"] += 1
                            continue
                        # Check for OCR artifact / glued neighbouring number (e.g. "thirty percent (3016)" where % was read as 16, or footnote 16 glued to 30)
                        m_glue = re.match(r"^(\d+)(?:16|l6|0/0)$", inside_raw)
                        if m_glue and Decimal(m_glue.group(1)) == words_before.value:
                            stats["pairs_verified"] += 1
                            continue

                        stats["pairs_found"] += 1
                        wb_val = words_before.value
                        if fig_inside.is_percentage and not words_before.is_percentage and wb_val <= 1:
                            wb_val = wb_val * 100
                        diff_a = abs(wb_val - fig_inside.value)
                        # Allow slight rounding tolerance (<= 0.01) for fractional percentages (e.g. two-thirds = 66.666...% vs 66.67%)
                        if diff_a > Decimal("0.01"):
                            stats["pairs_mismatched"] += 1
                            is_fin_or_pct = (
                                fig_inside.is_currency
                                or words_before.is_currency
                                or fig_inside.is_percentage
                                or words_before.is_percentage
                            )
                            if is_fin_or_pct:
                                ref_val = max(wb_val, fig_inside.value)
                                pct_diff = diff_a / ref_val if ref_val > 0 else Decimal(1)
                                sev = Severity.CRITICAL if pct_diff >= Decimal("0.20") else Severity.HIGH
                            else:
                                sev = Severity.MEDIUM

                            match_span_end = min(len(sentence), m.end() + 20)
                            snippet = sentence[
                                max(0, m.start() - len(words_candidate_str) - 10) : match_span_end
                            ].strip()
                            evidence = (
                                f"{words_candidate_str} ({inside_raw}) in snippet: '{snippet}'"[:MAX_EVIDENCE_CHARS]
                            )
                            c_info = f" in clause {segment.clause_ref}" if segment.clause_ref else ""
                            explanation = (
                                f"The amount in words ({words_candidate_str} = {words_before.value}) "
                                f"does not match the amount in figures ({inside_raw} = {fig_inside.value}){c_info}."
                            )
                            findings.append(
                                Finding(
                                    module=CONSISTENCY_MODULE,
                                    type="figure_words_mismatch",
                                    severity=sev,
                                    page=segment.page,
                                    clause_ref=segment.clause_ref,
                                    evidence=evidence,
                                    explanation=explanation,
                                    details={
                                        "rule_id": "CONSISTENCY_FIGURE_WORDS_MISMATCH",
                                        "words_raw": words_candidate_str,
                                        "words_value": str(words_before.value),
                                        "figure_raw": inside_raw,
                                        "figure_value": str(fig_inside.value),
                                    },
                                )
                            )
                        else:
                            stats["pairs_verified"] += 1
                        continue

                # Pattern B: FIGURE (WORDS)
                inside_tokens = inside_raw.split()
                if inside_tokens and any(_is_number_token(t) for t in inside_tokens):
                    words_inside = words_to_decimal(inside_raw)
                    if words_inside is not None:
                        fig_before: ParsedNumber | None = None
                        fig_candidate_str = ""
                        if any(c.isdigit() or c in "$₹€£" for c in tokens[-1]):
                            for k in range(min(len(tokens), 4), 0, -1):
                                cand_f = " ".join(tokens[-k:])
                                parsed_fig = parse_figure(cand_f)
                                if parsed_fig is not None:
                                    fig_before = parsed_fig
                                    fig_candidate_str = cand_f
                                    break

                        if fig_before is not None:
                            stats["pairs_found"] += 1
                            wi_val = words_inside.value
                            if fig_before.is_percentage and not words_inside.is_percentage and wi_val <= 1:
                                wi_val = wi_val * 100
                            diff_b = abs(fig_before.value - wi_val)
                            if diff_b > Decimal("0.01"):
                                stats["pairs_mismatched"] += 1
                                is_fin_or_pct = (
                                    fig_before.is_currency
                                    or words_inside.is_currency
                                    or fig_before.is_percentage
                                    or words_inside.is_percentage
                                )
                                if is_fin_or_pct:
                                    ref_val = max(fig_before.value, wi_val)
                                    pct_diff = diff_b / ref_val if ref_val > 0 else Decimal(1)
                                    sev = Severity.CRITICAL if pct_diff >= Decimal("0.20") else Severity.HIGH
                                else:
                                    sev = Severity.MEDIUM

                                match_span_end = min(len(sentence), m.end() + 20)
                                snippet = sentence[
                                    max(0, m.start() - len(fig_candidate_str) - 10) : match_span_end
                                ].strip()
                                evidence = (
                                    f"{fig_candidate_str} ({inside_raw}) in snippet: '{snippet}'"[:MAX_EVIDENCE_CHARS]
                                )
                                c_info = f" in clause {segment.clause_ref}" if segment.clause_ref else ""
                                explanation = (
                                    f"The amount in figures ({fig_candidate_str} = {fig_before.value}) "
                                    f"does not match the amount in words ({inside_raw} = {words_inside.value}){c_info}."
                                )
                                findings.append(
                                    Finding(
                                        module=CONSISTENCY_MODULE,
                                        type="figure_words_mismatch",
                                        severity=sev,
                                        page=segment.page,
                                        clause_ref=segment.clause_ref,
                                        evidence=evidence,
                                        explanation=explanation,
                                        details={
                                            "rule_id": "CONSISTENCY_FIGURE_WORDS_MISMATCH",
                                            "figure_raw": fig_candidate_str,
                                            "figure_value": str(fig_before.value),
                                            "words_raw": inside_raw,
                                            "words_value": str(words_inside.value),
                                        },
                                    )
                                )
                            else:
                                stats["pairs_verified"] += 1
                            continue

                # Check unparseable count
                if re.search(r"\d", inside_raw) or any(
                    tok in inside_raw.lower()
                    for tok in ("lakh", "crore", "thousand", "hundred", "million", "only", "rupees")
                ):
                    stats["pairs_unparseable"] += 1

    return findings, stats
