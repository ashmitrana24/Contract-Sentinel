"""Text index builder for parsed contracts.

Provides a normalized view of a ParsedDocument:
- ContractSegment: atomic segment of text with clause_ref, page number, and text.
- Fallback to per-page segments when the document is unsegmented or has fewer than 2 clauses.
- Pre-indexes clause IDs and page-level full text for quick lookup and safeguard checks.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from clauseguard.schemas.parsed import ParsedDocument

# Common abbreviations to avoid false sentence splits
_ABBREVIATIONS = {
    "al",
    "art",
    "co",
    "corp",
    "dr",
    "eg",
    "etc",
    "ie",
    "inc",
    "llc",
    "llp",
    "ltd",
    "mr",
    "mrs",
    "ms",
    "no",
    "para",
    "pvt",
    "rs",
    "sec",
    "vs",
}


@dataclass(frozen=True)
class ContractSegment:
    """One addressable unit of contract text."""

    clause_ref: str | None
    page: int
    text: str
    kind: str  # "preamble" | "clause" | "page_fallback"
    heading: str = ""


@dataclass
class TextIndex:
    """Indexed document text supporting segment, sentence, and page lookup."""

    segments: list[ContractSegment]
    is_unsegmented: bool
    clause_ids: set[str]
    page_texts: dict[int, str]
    full_text: str
    clause_map: dict[str, ContractSegment] = field(default_factory=dict)

    def page_contains_clause_start(self, clause_id: str) -> bool:
        """Check whether any page text starts a line with the given clause ID."""
        # Safeguard pattern: line starting with "4.2", "Clause 4.2", "Section 4.2"
        escaped_id = re.escape(clause_id)
        pat = re.compile(
            rf"(?m)^\s*(?:(?:Clause|Section|Article)\s+)?{escaped_id}(?:[.:\s]|$)",
            re.IGNORECASE,
        )
        for p_text in self.page_texts.values():
            if pat.search(p_text):
                return True
        return False


def split_sentences(text: str) -> list[str]:
    """Split text into sentences while respecting common legal abbreviations."""
    if not text:
        return []

    # Group lines: keep key-value lines standalone, merge running text lines
    raw_lines = [line.strip() for line in text.splitlines() if line.strip()]
    paragraphs: list[str] = []
    curr_lines: list[str] = []

    for line in raw_lines:
        is_kv = bool(re.match(r"^[A-Z][A-Za-z\s]{1,30}:\s*", line))
        if is_kv:
            if curr_lines:
                paragraphs.append(" ".join(curr_lines))
                curr_lines = []
            paragraphs.append(line)
        else:
            curr_lines.append(line)
    if curr_lines:
        paragraphs.append(" ".join(curr_lines))

    sentences: list[str] = []

    for para in paragraphs:
        # Candidate split on [.!?] followed by whitespace
        chunks = re.split(r"([.!?]+(?:\s+|$))", para)
        curr = ""
        for i in range(0, len(chunks), 2):
            chunk = chunks[i]
            delim = chunks[i + 1] if i + 1 < len(chunks) else ""
            curr += chunk + delim

            # Check if chunk ends in known abbreviation
            m = re.search(r"\b([A-Za-z]+)\.?\s*$", chunk)
            if m and m.group(1).lower() in _ABBREVIATIONS:
                continue

            if delim and (delim.endswith(" ") or delim.endswith("\t")):
                s = curr.strip()
                if s:
                    sentences.append(s)
                curr = ""
        if curr.strip():
            sentences.append(curr.strip())

    return sentences


def build_text_index(parsed_doc: ParsedDocument) -> TextIndex:
    """Build a TextIndex from a ParsedDocument."""
    page_texts: dict[int, str] = {p.page_no: p.text for p in parsed_doc.pages}
    full_text = "\n\n".join(p.text for p in parsed_doc.pages)

    # Determine if document has valid clause segmentation
    clauses = parsed_doc.clauses
    is_unsegmented = (
        len(clauses) == 0
        or (len(clauses) == 1 and clauses[0].kind == "unsegmented")
        or all(c.kind == "unsegmented" for c in clauses)
    )

    segments: list[ContractSegment] = []
    clause_ids: set[str] = set()
    clause_map: dict[str, ContractSegment] = {}

    if is_unsegmented:
        # Fall back to per-page segments
        for p in parsed_doc.pages:
            t = p.text.strip()
            if t:
                segments.append(
                    ContractSegment(
                        clause_ref=None,
                        page=p.page_no,
                        text=t,
                        kind="page_fallback",
                        heading="",
                    )
                )
    else:
        for c in clauses:
            clause_id = c.clause_id
            if c.kind == "preamble" or clause_id == "0":
                clause_ref = "0"
                kind = "preamble"
            elif c.kind == "unsegmented" or clause_id == "U":
                clause_ref = None
                kind = "unsegmented"
            else:
                clause_ref = clause_id
                clause_ids.add(clause_id)
                kind = "clause"

            seg_text = f"{c.heading}\n{c.text}".strip() if c.heading else c.text.strip()
            if not seg_text:
                continue

            seg = ContractSegment(
                clause_ref=clause_ref,
                page=c.page_start,
                text=seg_text,
                kind=kind,
                heading=c.heading,
            )
            segments.append(seg)
            if clause_ref and clause_ref not in ("0", "U"):
                clause_map[clause_ref] = seg

    return TextIndex(
        segments=segments,
        is_unsegmented=is_unsegmented,
        clause_ids=clause_ids,
        page_texts=page_texts,
        full_text=full_text,
        clause_map=clause_map,
    )
