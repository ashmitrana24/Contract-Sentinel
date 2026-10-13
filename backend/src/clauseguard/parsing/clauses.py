"""Heuristic clause segmenter.

Segments the text of a document (lines across all pages) into numbered clauses.

Recognised heading patterns (at LINE START, after stripping leading whitespace):
  - Numeric:   "1."   "1.1"   "4.2.3"
  - Keyword:   "Section 4"  "Clause 4.2"  "Article IV"
  - The heading text may follow on the same line, or appear on the next line
    starting with a capital letter.

NOT treated as clause starts:
  - Numbers embedded in sentences ("pay 2.5 percent")
  - Dates ("1.1.2026")
  - Page numbers (a lone digit at the end of a line or by itself)
  - Lettered sub-items "(a)" "(i)" — accumulated into parent clause body

Special cases:
  - Text before the first clause becomes a preamble (clause_id "0")
  - If fewer than 2 headings found: one "unsegmented" clause for the whole doc
  - Repeated page headers/footers (lines appearing on ≥70% of pages) are stripped
  - level is nesting depth: "1" → 1, "1.1" → 2, "1.1.1" → 3
  - parent_clause_id is the id of the enclosing higher-level clause

The function is pure: takes list[PageModel], returns list[ClauseModel].
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import NamedTuple

from clauseguard.schemas.parsed import ClauseModel, PageModel

# ---------------------------------------------------------------------------
# Heading detection patterns
# ---------------------------------------------------------------------------

# Numeric patterns: "1."  "1.1"  "4.2.3"  — must start the stripped line
# Followed optionally by a space then the heading text.
# A trailing date like "1.1.2026" is excluded by requiring no more than 2
# numeric segments AFTER the first dot when the pattern is purely numeric.
# We use a lookahead to reject 3+ numeric segments (dates have year).
_NUMERIC_RE = re.compile(
    r"""
    ^(?P<id>
        \d{1,3}             # section: 1..999
        (?:\.\d{1,3}){0,2}  # up to 2 sub-levels: .1 .2
    )
    \.                      # trailing dot is required for top-level "1."
                            # (sub-levels: "1.1" includes the dot in the id)
    (?=\s|$)                # must be followed by space or end-of-line
    """,
    re.VERBOSE,
)

# Like the numeric pattern but for sub-levels that already contain a dot:
# "1.1" "4.2.3" — no trailing dot required since the dot is part of the id
_SUBLEVEL_RE = re.compile(
    r"""
    ^(?P<id>
        \d{1,3}
        \.\d{1,3}
        (?:\.\d{1,3})?
    )
    (?=\s|$)
    """,
    re.VERBOSE,
)

# Keyword patterns: "Section 4", "Clause 4.2", "Article IV"
# (Exhibits and Schedules are handled separately by _SCHEDULE_RE)
_KEYWORD_RE = re.compile(
    r"""
    ^(?:Section|Clause|Article|Part)\s+
    (?P<id>[IVXLCDM]+|\d+(?:\.\d+)*)
    (?=\s|$|[.:]?)
    """,
    re.VERBOSE | re.IGNORECASE,
)

# SEC filing headers: "EX-10.3", "Exhibit 10.16", "EXHIBIT 10.1", "EX-4"
_SEC_FILING_RE = re.compile(
    r"^(?:\d+\s+)?(?:EX-\d+(?:\.\d+)?|EXHIBIT\s+\d+(?:\.\d+)?)\b",
    re.IGNORECASE,
)

# Schedule / Exhibit / Annex / Appendix headers:
# "Schedule A", "Exhibit B", "Schedule 1", "Annex I", "Appendix A"
_SCHEDULE_RE = re.compile(
    r"""
    ^(?P<type>Schedule|Exhibit|Annex|Appendix)\s+
    (?P<id>[A-Z]|\d+|[IVXLCDM]+)
    (?:\s*[-:—–.]\s*|\s+|$)
    (?P<title>.*)
    """,
    re.VERBOSE | re.IGNORECASE,
)

# Table of Contents lines with dot leaders: "24. ACKNOWLEDGMENTS..............70"
_TOC_LINE_RE = re.compile(r"\.{3,}\s*\d+\s*$")

# Lettered sub-items: "(a)" "(i)" "(ii)" "(1)" at line start
_LETTER_ITEM_RE = re.compile(r"^\([a-z]{1,4}\)\s", re.IGNORECASE)

# A standalone integer (page number in footer): entire line is a small integer
_PAGE_NUMBER_RE = re.compile(r"^\d{1,4}$")

# Capitalized heading words (first letter uppercase, not all caps which may be body)
_CAP_RE = re.compile(r"^[A-Z]")


# ---------------------------------------------------------------------------
# Internal line data
# ---------------------------------------------------------------------------


class _Line(NamedTuple):
    page_no: int  # 1-based
    text: str  # stripped text
    char_start: int = 0
    char_end: int = 0


@dataclass
class _ClauseDraft:
    clause_id: str
    heading: str
    lines: list[str] = field(default_factory=list)
    page_start: int = 1
    page_end: int = 1
    level: int = 1
    parent_clause_id: str | None = None
    kind: str = "clause"
    char_start: int = 0
    char_end: int = 0


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _id_level(clause_id: str) -> int:
    """Return the nesting level of a clause id.

    "1" → 1, "1.1" → 2, "1.2.3" → 3.
    Roman numerals (from keyword patterns) → 1.
    """
    if not clause_id:
        return 1
    parts = clause_id.split(".")
    return len(parts)


def _parent_id(clause_id: str) -> str | None:
    """Return the parent clause id for a given clause id.

    "1.2" → "1", "1.2.3" → "1.2", "1" → None.
    """
    parts = clause_id.split(".")
    if len(parts) <= 1:
        return None
    return ".".join(parts[:-1])


def _roman_to_int(s: str) -> int:
    """Convert a Roman numeral string to int for ordering purposes."""
    vals = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100, "D": 500, "M": 1000}
    result = 0
    prev = 0
    for ch in reversed(s.upper()):
        v = vals.get(ch, 0)
        if v < prev:
            result -= v
        else:
            result += v
        prev = v
    return result


def _normalise_keyword_id(raw_id: str) -> str:
    """Convert keyword match id to a normalised clause_id string."""
    # Roman numeral → decimal integer for consistency
    if re.fullmatch(r"[IVXLCDM]+", raw_id, re.IGNORECASE):
        return str(_roman_to_int(raw_id))
    return raw_id


def _is_date_like(num_str: str) -> bool:
    """Return True if num_str looks like a date (e.g. '1.1.2026')."""
    parts = num_str.split(".")
    if len(parts) == 3:
        # Middle or last part looks like a year
        try:
            if int(parts[2]) > 1900 or int(parts[1]) > 31:
                return True
        except ValueError:
            pass
    return False


def _detect_heading(line: str) -> tuple[str, str, bool] | None:
    """Return (clause_id, remainder_heading, is_schedule) if line is a clause heading, else None.

    Remainder heading is the text after the clause number on the same line
    (may be empty if heading is on the next line).
    is_schedule indicates whether this heading introduces an exhibit, schedule, or appendix.
    """
    stripped = line.strip()
    if not stripped:
        return None

    # Skip SEC exhibit and filing headers like "EX-10.3", "Exhibit 10.16", "EX-4"
    if _SEC_FILING_RE.match(stripped):
        return None

    # Skip Table of Contents entries with dot leaders
    if _TOC_LINE_RE.search(stripped):
        return None

    # Skip lettered sub-items
    if _LETTER_ITEM_RE.match(stripped):
        return None

    # Skip standalone page numbers
    if _PAGE_NUMBER_RE.match(stripped):
        return None

    # --- Schedule / Exhibit / Annex / Appendix headers ---
    m_sch = _SCHEDULE_RE.match(stripped)
    if m_sch:
        stype = m_sch.group("type").title()
        sid = m_sch.group("id").upper()
        sch_id = f"{stype} {sid}"
        title = m_sch.group("title").strip().lstrip("-:—–. ")
        return sch_id, title, True

    # --- Numeric with trailing dot: "1." "1.1." "4.2." ---
    m = _NUMERIC_RE.match(stripped)
    if m:
        num_id = m.group("id")
        if _is_date_like(num_id):
            return None
        remainder = stripped[m.end():].strip()
        # If remainder is an SEC filing header like "Exhibit 10.17", ignore
        if _SEC_FILING_RE.match(remainder):
            return None
        # If remainder is a multi-item Table of Contents line (e.g. "Interpretation 3 2. Commencement 4"), ignore
        # If remainder is a list item ending with a semicolon/conjunction or party definition, ignore
        if remainder.endswith((";", "; and", "; or", ", and", ", or")):
            return None
        if re.search(r'\(\s*(?:the\s+)?["\u201c\u2018][^"\u201d\u2019]+["\u201d\u2019]\s*\)\s*$', remainder):
            return None
        return num_id, remainder, False

    # --- Sub-level without trailing dot: "1.1" "4.2.3" ---
    m2 = _SUBLEVEL_RE.match(stripped)
    if m2:
        num_id = m2.group("id")
        if _is_date_like(num_id):
            return None
        remainder = stripped[m2.end():].strip()
        # Require that remainder starts with capital or is empty
        # (to avoid matching decimal numbers inside sentences)
        if remainder and not _CAP_RE.match(remainder):
            return None
        return num_id, remainder, False

    # --- Keyword: "Section 4", "Clause 1.2" ---
    m3 = _KEYWORD_RE.match(stripped)
    if m3:
        raw_id = m3.group("id")
        clause_id = _normalise_keyword_id(raw_id)
        remainder = stripped[m3.end():].strip()
        if remainder:
            if remainder.startswith((",", ";", ")", "]")):
                return None
            clean_rem = remainder.lstrip("-:—–. ")
            if clean_rem and not _CAP_RE.match(clean_rem):
                return None
        return clause_id, remainder.lstrip(".:-—– "), False

    return None


# ---------------------------------------------------------------------------
# Header/footer stripping
# ---------------------------------------------------------------------------


def _collect_repeated_lines(all_lines: list[_Line], n_pages: int, threshold: float = 0.7) -> set[str]:
    """Return lines that appear on at least threshold * n_pages pages."""
    if n_pages < 3:
        return set()

    from collections import Counter, defaultdict

    page_line_sets: dict[int, set[str]] = defaultdict(set)
    for ln in all_lines:
        t = ln.text.strip()
        if t:
            page_line_sets[ln.page_no].add(t)

    counts: Counter[str] = Counter()
    for lines_set in page_line_sets.values():
        for t in lines_set:
            counts[t] += 1

    min_pages = max(2, int(threshold * n_pages))
    return {t for t, c in counts.items() if c >= min_pages}


def _split_embedded_headings(text: str) -> list[str]:
    """Split lines that have embedded Article or Section headings within body text.

    Handles contracts where headings are not on their own line:
    1. Sentences ending with period/parenthesis followed by an Article or Section heading:
       "...end of term. ARTICLE V TERMINATION..." -> "...end of term.\\nARTICLE V TERMINATION..."
    2. Article headings immediately followed by a nested section on the same line:
       "ARTICLE VI REGISTRATION RIGHTS Section 6.1 Demand Registration" ->
       "ARTICLE VI REGISTRATION RIGHTS\\nSection 6.1 Demand Registration"
       "ARTICLE 3 - RELATIONSHIP OF PARTIES 3.1 The Company" ->
       "ARTICLE 3 - RELATIONSHIP OF PARTIES\\n3.1 The Company"
    3. Inline Section definitions:
       "...shall survive. Section 8.12 Severability..." ->
       "...shall survive.\\nSection 8.12 Severability..."
    """
    if not text.strip():
        return [text]

    # Break after period/paren/quote before ARTICLE or Section heading
    t = re.sub(
        r'([.;!?)"\u201d\u2019])\s+(?=(?:ARTICLE\s+[IVXLCDM\d]+|Section\s+\d+(?:\.\d+)*)\b)',
        r"\1\n",
        text,
        flags=re.IGNORECASE,
    )
    # Break between ARTICLE ... and nested Section / dotted number
    t = re.sub(
        r"(\bARTICLE\s+[IVXLCDM\d]+[^\n.;]{0,60}?)\s+(?=(?:Section\s+\d+|\d+\.\d+\s+[A-Z]))",
        r"\1\n",
        t,
        flags=re.IGNORECASE,
    )
    # Break before inline Section N.N
    t = re.sub(
        r'([.;!?)"\u201d\u2019])\s+(?=Section\s+\d+(?:\.\d+)*\b)',
        r"\1\n",
        t,
        flags=re.IGNORECASE,
    )
    return [ln for ln in t.split("\n") if ln.strip()]


# ---------------------------------------------------------------------------
# Main segmentation function
# ---------------------------------------------------------------------------


def segment_clauses(pages: list[PageModel]) -> list[ClauseModel]:
    """Segment a list of pages into clauses with start/end character offsets.

    Returns list of ClauseModel sorted by order_idx.
    """
    if not pages:
        return [
            ClauseModel(
                order_idx=0,
                clause_id="U",
                heading="",
                text="",
                level=1,
                parent_clause_id=None,
                page_start=1,
                page_end=1,
                kind="unsegmented",
                char_start=0,
                char_end=0,
            )
        ]

    n_pages = len(pages)
    doc_text = "".join(p.text for p in pages)
    total_len = len(doc_text)

    # Collect all lines with page number and character offsets
    all_lines: list[_Line] = []
    page_base_offset = 0

    for page in pages:
        p_text = page.text
        line_cursor = page_base_offset
        for raw_line in p_text.splitlines(keepends=True):
            raw_start = line_cursor
            raw_end = raw_start + len(raw_line)
            line_cursor = raw_end

            sub_lines = _split_embedded_headings(raw_line)
            if len(sub_lines) <= 1:
                all_lines.append(
                    _Line(
                        page_no=page.page_no,
                        text=raw_line.rstrip("\r\n"),
                        char_start=raw_start,
                        char_end=raw_end,
                    )
                )
            else:
                sub_cursor = 0
                for sub in sub_lines:
                    pos = raw_line.find(sub, sub_cursor)
                    if pos != -1:
                        s_start = raw_start + pos
                        s_end = s_start + len(sub)
                        sub_cursor = pos + len(sub)
                    else:
                        s_start = raw_start
                        s_end = raw_end
                    all_lines.append(
                        _Line(
                            page_no=page.page_no,
                            text=sub,
                            char_start=s_start,
                            char_end=s_end,
                        )
                    )
        page_base_offset += len(p_text)

    # Detect repeated headers/footers to strip
    repeated = _collect_repeated_lines(all_lines, n_pages)

    # Filter out repeated header/footer lines (keep if only 1-2 pages or not repeated)
    filtered_lines: list[_Line] = []
    for ln in all_lines:
        if ln.text.strip() in repeated:
            continue
        filtered_lines.append(ln)

    # ---------------------------------------------------------------------------
    # Pass 1: detect clause boundaries
    # ---------------------------------------------------------------------------
    drafts: list[_ClauseDraft] = []
    preamble_lines: list[str] = []
    in_preamble = True
    current: _ClauseDraft | None = None
    # pending_heading: (effective_id, partial_heading, parent_id, level, char_start)
    pending_heading: tuple[str, str, str | None, int, int] | None = None
    current_schedule: str | None = None

    for i, ln in enumerate(filtered_lines):
        text = ln.text
        stripped = text.strip()

        # Preserve pending heading across blank lines
        if not stripped:
            if pending_heading is None and current is not None:
                current.lines.append("")
            continue

        # Check if this line is an operative transition / recitals marker
        # e.g. "NOW, THEREFORE, the parties agree:", "IT IS HEREBY AGREED"
        if re.search(r"\b(?:NOW,?\s+THEREFORE|IT\s+IS\s+(?:HEREBY\s+)?AGREED)\b", stripped, re.IGNORECASE):
            if drafts or current is not None:
                if current is not None:
                    drafts.append(current)
                    current = None
                for d in drafts:
                    preamble_lines.append(f"{d.clause_id}. {d.heading}")
                    preamble_lines.extend(d.lines)
                drafts.clear()
            preamble_lines.append(text)
            in_preamble = True
            pending_heading = None
            continue

        # Check if this line is a clause heading
        result = _detect_heading(text)

        if result is None:
            # Not a heading line.
            if pending_heading is not None:
                # We had a number-only line before; this line might be the heading
                pid, _, pparent, plevel, p_char_start = pending_heading
                # Accept as heading if starts with capital or is substantial
                if stripped and (_CAP_RE.match(stripped) or len(stripped) > 3):
                    heading_text = stripped
                    pending_heading = None
                    # Start new clause
                    if current is not None:
                        drafts.append(current)
                    current = _ClauseDraft(
                        clause_id=pid,
                        heading=heading_text,
                        page_start=ln.page_no,
                        page_end=ln.page_no,
                        level=plevel,
                        parent_clause_id=pparent,
                        kind="clause",
                        char_start=p_char_start,
                        char_end=total_len,
                    )
                    in_preamble = False
                    continue
                else:
                    # Discard the pending heading (was probably a number in text)
                    if current is not None:
                        current.lines.append(filtered_lines[i - 1].text)
                    elif in_preamble:
                        preamble_lines.append(filtered_lines[i - 1].text)
                    pending_heading = None

            # Normal body line
            if current is not None:
                current.lines.append(text)
                current.page_end = ln.page_no
            elif in_preamble:
                preamble_lines.append(text)
        else:
            # It IS a heading line.
            clause_id, remainder, is_schedule = result

            seen_ids = {d.clause_id for d in drafts} | ({current.clause_id} if current else set())
            if is_schedule:
                current_schedule = clause_id
                effective_id = clause_id
                parent_id = None
                level = 1
            elif current_schedule is not None and clause_id in seen_ids:
                effective_id = f"{current_schedule}.{clause_id}"
                parent_id = current_schedule
                level = _id_level(clause_id) + 1
            else:
                effective_id = clause_id
                parent_id = _parent_id(clause_id)
                level = _id_level(clause_id)

            if pending_heading is not None:
                # Discard previous pending (was a false positive)
                prev_ln = filtered_lines[i - 1] if i > 0 else ln
                if current is not None:
                    current.lines.append(prev_ln.text)
                elif in_preamble:
                    preamble_lines.append(prev_ln.text)
                pending_heading = None

            if remainder or is_schedule:
                # Heading is on the same line (or schedule starts): start clause immediately
                if current is not None:
                    drafts.append(current)
                current = _ClauseDraft(
                    clause_id=effective_id,
                    heading=remainder,
                    page_start=ln.page_no,
                    page_end=ln.page_no,
                    level=level,
                    parent_clause_id=parent_id,
                    kind="clause",
                    char_start=ln.char_start,
                    char_end=total_len,
                )
                in_preamble = False
            else:
                # Number-only line; defer until we see the heading on the next line
                pending_heading = (effective_id, "", parent_id, level, ln.char_start)

    # Flush pending
    if pending_heading is not None:
        pid, _, _, _, p_start = pending_heading
        if current is not None:
            current.lines.append(f"{pid}.")
        elif in_preamble:
            preamble_lines.append(f"{pid}.")
    if current is not None:
        drafts.append(current)

    # ---------------------------------------------------------------------------
    # Check: if fewer than 2 clause headings, return unsegmented
    # ---------------------------------------------------------------------------
    if len(drafts) < 2:
        full_text = "\n".join(ln.text for ln in filtered_lines).strip()
        return [
            ClauseModel(
                order_idx=0,
                clause_id="U",
                heading="",
                text=full_text,
                level=1,
                parent_clause_id=None,
                page_start=pages[0].page_no,
                page_end=pages[-1].page_no,
                kind="unsegmented",
                char_start=0,
                char_end=total_len,
            )
        ]

    # ---------------------------------------------------------------------------
    # Build final ClauseModel list with contiguous, exact character offsets
    # ---------------------------------------------------------------------------
    result: list[ClauseModel] = []
    order = 0

    first_clause_start = drafts[0].char_start if drafts else total_len
    preamble_text = "\n".join(preamble_lines).strip()
    if preamble_text or first_clause_start > 0:
        result.append(
            ClauseModel(
                order_idx=order,
                clause_id="0",
                heading="Preamble",
                text=preamble_text,
                level=1,
                parent_clause_id=None,
                page_start=pages[0].page_no,
                page_end=drafts[0].page_start if drafts else pages[0].page_no,
                kind="preamble",
                char_start=0,
                char_end=first_clause_start,
            )
        )
        order += 1

    for i, draft in enumerate(drafts):
        body = "\n".join(draft.lines).strip()
        # Set char_end to next clause's char_start, or end of document
        c_end = drafts[i + 1].char_start if i + 1 < len(drafts) else total_len
        result.append(
            ClauseModel(
                order_idx=order,
                clause_id=draft.clause_id,
                heading=draft.heading,
                text=body,
                level=draft.level,
                parent_clause_id=draft.parent_clause_id,
                page_start=draft.page_start,
                page_end=draft.page_end,
                kind="clause",
                char_start=draft.char_start,
                char_end=c_end,
            )
        )
        order += 1

    return result
