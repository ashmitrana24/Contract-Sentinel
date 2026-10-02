"""CUAD v1 plain-text contract loader.

Reads .txt files from data/raw/cuad/, segments them into clauses using a
heuristic for numbered headings, and converts each to a Contract model.

Contracts with fewer than MIN_CLAUSES are skipped and logged.
The loader does NOT download anything; the user must manually download
CUAD v1 (see datagen/README.md for instructions).

Heuristic for clause detection:
  A line is a clause heading if it matches the pattern:
    ^(\\d+\\.(?:\\d+\\.?)?\\s+[A-Z][A-Za-z ]{2,50})$
  or a common all-caps heading pattern.

We tolerate messy CUAD text by being permissive: we accept any line
that starts with a number followed by a dot and at least 2 non-digit chars.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

from datagen.models import (
    Clause,
    Contract,
    KeyFact,
    KeyFactKind,
    Party,
)

logger = logging.getLogger(__name__)

MIN_CLAUSES = 5

# Heading patterns (tried in order; first match wins)
_HEADING_PATTERNS = [
    # "1. DEFINITIONS" or "1.1 Scope" or "10. FORCE MAJEURE."
    re.compile(r"^(\d{1,3}(?:\.\d{1,3})?\.?)\s{1,4}([A-Z][A-Za-z &/\-]{2,60})\.?\s*$"),
    # ALL CAPS headings like "ARTICLE I - DEFINITIONS"
    re.compile(r"^(ARTICLE|SECTION)\s+([IVXLCDM\d]+)\s*[\-\u2013:]\s*([A-Z ]{3,60})\s*$"),
]

_DATE_RE = re.compile(r"\b(\d{4}[-/]\d{2}[-/]\d{2})\b")
_AMOUNT_RE = re.compile(r"\$([\d,]+(?:\.\d{2})?)")


def _normalise_date(raw: str) -> str:
    return raw.replace("/", "-")


def _parse_clause_id(raw: str) -> str:
    """Strip trailing dot from clause ID."""
    return raw.rstrip(".")


def _load_txt(path: Path) -> list[str]:
    """Read a text file, trying UTF-8 then latin-1."""
    try:
        return path.read_text(encoding="utf-8").splitlines()
    except UnicodeDecodeError:
        return path.read_text(encoding="latin-1").splitlines()


def _segment_clauses(lines: list[str]) -> list[tuple[str, str, str]]:
    """Segment lines into (clause_id, heading, body) tuples.

    Returns a list of (clause_id, heading, body) triples.
    """
    segments: list[tuple[str, str, str]] = []
    current_id: str | None = None
    current_heading: str | None = None
    current_body_lines: list[str] = []

    def _flush() -> None:
        if current_id and current_heading:
            body = " ".join(current_body_lines).strip()
            if body:
                segments.append((current_id, current_heading, body))

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue

        matched = False
        for pattern in _HEADING_PATTERNS:
            m = pattern.match(stripped)
            if m:
                _flush()
                groups = m.groups()
                # First pattern: groups = (id_part, heading_part)
                # Second pattern: groups = (ARTICLE/SECTION, number, heading)
                if len(groups) == 2:
                    current_id = _parse_clause_id(groups[0])
                    current_heading = groups[1].strip()
                else:
                    # Article/Section pattern
                    current_id = f"{groups[0][:3].capitalize()}.{groups[1]}"
                    current_heading = groups[2].strip()
                current_body_lines = []
                matched = True
                break

        if not matched and current_id is not None:
            current_body_lines.append(stripped)

    _flush()
    return segments


def _extract_key_facts(
    clauses: list[Clause],
    effective_date: str,
    termination_date: str,
) -> list[KeyFact]:
    """Extract basic key facts from clause text."""
    facts: list[KeyFact] = []
    seen_dates: set[str] = set()

    # Standard date facts from header
    if effective_date:
        facts.append(
            KeyFact(
                kind=KeyFactKind.DATE,
                label="effective_date",
                date_str=effective_date,
                date_label="effective_date",
            )
        )
        seen_dates.add(effective_date)
    if termination_date:
        facts.append(
            KeyFact(
                kind=KeyFactKind.DATE,
                label="termination_date",
                date_str=termination_date,
                date_label="termination_date",
            )
        )
        seen_dates.add(termination_date)

    # Cross-reference facts
    xref_re = re.compile(r"\bSection\s+(\d+(?:\.\d+)?)\b|\bClause\s+(\d+(?:\.\d+)?)\b")
    clause_ids = {c.id for c in clauses}

    for clause in clauses:
        for m in xref_re.finditer(clause.text):
            ref = m.group(1) or m.group(2)
            if ref and ref in clause_ids:
                facts.append(
                    KeyFact(
                        kind=KeyFactKind.XREF,
                        clause_id=clause.id,
                        xref_target=ref,
                        xref_source_clause=clause.id,
                    )
                )

    return facts


def _extract_parties(lines: list[str]) -> list[Party]:
    """Heuristically extract party names from the preamble."""
    parties: list[Party] = []
    # Look for "between X and Y" patterns in first 50 lines
    between_re = re.compile(
        r"between\s+(.{5,80}?)\s+(?:and|&)\s+(.{5,80}?)(?:\.|,|\(|$)",
        re.IGNORECASE,
    )
    preamble = " ".join(lines[:50])
    m = between_re.search(preamble)
    if m:
        for i, name in enumerate((m.group(1).strip(), m.group(2).strip()), start=1):
            # Clean up common trailing words
            name = re.sub(r"\s+(a|an|the|each|its)\s*$", "", name, flags=re.IGNORECASE).strip()
            if 3 <= len(name) <= 120:
                parties.append(Party(name=name, role=f"Party {i}"))
    return parties


def load_cuad_contracts(
    cuad_dir: Path,
    *,
    max_contracts: int | None = None,
) -> list[Contract]:
    """Load CUAD plain-text contracts from *cuad_dir*.

    Parameters
    ----------
    cuad_dir:
        Directory containing *.txt files (one per contract).
    max_contracts:
        If given, load at most this many contracts.

    Returns
    -------
    list[Contract]
        Successfully parsed contracts (≥ MIN_CLAUSES).
    """
    if not cuad_dir.exists():
        logger.warning("CUAD directory not found: %s - skipping CUAD source.", cuad_dir)
        return []

    txt_files = sorted(cuad_dir.glob("*.txt"))
    if not txt_files:
        logger.warning("No .txt files in %s - skipping CUAD source.", cuad_dir)
        return []

    if max_contracts is not None:
        txt_files = txt_files[:max_contracts]

    contracts: list[Contract] = []
    skipped = 0

    for path in txt_files:
        try:
            contract = _parse_cuad_file(path)
            if contract is not None:
                contracts.append(contract)
            else:
                skipped += 1
        except Exception as exc:
            logger.warning("Failed to parse %s: %s", path.name, exc)
            skipped += 1

    logger.info(
        "CUAD: loaded %d contracts, skipped %d (min_clauses=%d).",
        len(contracts),
        skipped,
        MIN_CLAUSES,
    )
    return contracts


def _parse_cuad_file(path: Path) -> Contract | None:
    """Parse one CUAD .txt file into a Contract.

    Returns None if the file cannot be segmented into MIN_CLAUSES clauses.
    """
    lines = _load_txt(path)
    contract_id = f"cuad_{path.stem}"

    # Try to find a title in the first 10 non-empty lines
    title = ""
    for line in lines[:15]:
        stripped = line.strip()
        if stripped and len(stripped) > 10:
            title = stripped[:200]
            break
    if not title:
        title = path.stem.replace("_", " ").title()

    # Segment into clauses
    segments = _segment_clauses(lines)
    if len(segments) < MIN_CLAUSES:
        logger.debug(
            "Skipping %s: only %d clause(s) found (need %d).",
            path.name,
            len(segments),
            MIN_CLAUSES,
        )
        return None

    clauses: list[Clause] = []
    for cid, heading, body in segments:
        clauses.append(Clause(id=cid, heading=heading, text=body))

    # Extract dates from first 100 lines
    preamble_text = " ".join(lines[:100])
    dates_found: list[str] = [_normalise_date(m.group(1)) for m in _DATE_RE.finditer(preamble_text)]
    effective_date = dates_found[0] if dates_found else ""
    termination_date = dates_found[1] if len(dates_found) > 1 else ""

    parties = _extract_parties(lines)

    key_facts = _extract_key_facts(clauses, effective_date, termination_date)

    return Contract(
        id=contract_id,
        title=title,
        contract_type="cuad",
        parties=parties,
        effective_date=effective_date,
        termination_date=termination_date,
        clauses=clauses,
        key_facts=key_facts,
    )
