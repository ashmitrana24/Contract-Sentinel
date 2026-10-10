"""Incremental edit detector.

Compares consecutive PDF revisions and reports:
- incremental_update: revision that changed page text or content streams (high/critical)
- metadata_anomaly: trailer /ID mismatch between revisions (low)

Severity escalation:
- If changed tokens contain digits, dates, currency, or look like party names -> critical
- Otherwise -> high
- Revision that only changes metadata/annotations/form-fields -> low

All findings carry revision numbers, changed pages, and before/after token snippets.
"""

from __future__ import annotations

import difflib
import hashlib
import logging
import re
from typing import Any

import pymupdf

from clauseguard.forensics.models import (
    FORENSICS_MODULE,
    MAX_FINDINGS_PER_TYPE,
    ForensicsSettings,
)
from clauseguard.forensics.revisions import find_valid_revisions
from clauseguard.schemas.findings import Finding, Severity

logger = logging.getLogger(__name__)

# Tokens that escalate severity to critical
_DIGIT_RE = re.compile(r"\d")
_DATE_RE = re.compile(
    r"\b(\d{4}-\d{2}-\d{2}|\d{1,2}/\d{1,2}/\d{2,4}|\d{1,2}-\d{1,2}-\d{2,4})\b"
)
_CURRENCY_RE = re.compile(r"(Rs\.?|INR|\$|€|£|¥|\bUSD\b|\bEUR\b)")
_PARTY_KEYWORDS_RE = re.compile(
    r"\b(client|service provider|vendor|party|lessor|lessee|employer|employee|contractor)\b",
    re.IGNORECASE,
)

# Legal keywords that make hidden text HIGH severity
_LEGAL_KEYWORDS_RE = re.compile(
    r"\b(indemnif|warrant|liabilit|terminat|confidential|arbitrat|jurisdict|governing law|"
    r"intellectual property|assign|license|royalt|penalty|damages|waiv|forfeit)\b",
    re.IGNORECASE,
)

_EVIDENCE_CAP = 300
_DIFF_TOKENS_CAP = 20


def _page_content_hash(page: pymupdf.Page) -> str:
    """Hash the raw bytes of a page's content streams."""
    try:
        # get_text("rawdict") gives us raw character codes including invisible text
        raw = page.get_text("rawdict", flags=pymupdf.TEXT_PRESERVE_WHITESPACE)
        serialized = repr(raw).encode()
        return hashlib.md5(serialized).hexdigest()
    except Exception:
        return ""


def _page_normalized_text(page: pymupdf.Page) -> str:
    """Extract normalized text from a page for diffing."""
    try:
        return " ".join(page.get_text("text").split())
    except Exception:
        return ""


def _tokenize(text: str) -> list[str]:
    """Split text into whitespace-separated tokens."""
    return text.split()


def _token_diff(before: list[str], after: list[str]) -> tuple[list[str], list[str]]:
    """Sequence-based diff returning (removed, added) token lists preserving order and repetitions."""
    matcher = difflib.SequenceMatcher(None, before, after)
    removed: list[str] = []
    added: list[str] = []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag in ("replace", "delete"):
            removed.extend(before[i1:i2])
        if tag in ("replace", "insert"):
            added.extend(after[j1:j2])
    return removed, added


def _check_widget_changes(
    page_old: pymupdf.Page, page_new: pymupdf.Page
) -> tuple[bool, list[dict[str, Any]]]:
    """Check if changes are confined to AcroForm widgets, and track overwritten fields.

    Returns (is_widget_change, overwritten_widgets).
    If any non-widget text changed, returns (False, []).
    If all text changes are confined to widgets:
      - If every changed widget was empty/whitespace before, returns (True, []).
      - If any changed widget already held a non-empty value, returns (True, overwritten_widgets)
        with field_name, old_value, new_value, and rect.
    """
    try:
        old_widgets_list = list(page_old.widgets())
        new_widgets_list = list(page_new.widgets())
        w_rects = [pymupdf.Rect(w.rect) for w in new_widgets_list] + [
            pymupdf.Rect(w.rect) for w in old_widgets_list
        ]
        if not w_rects:
            return False, []

        def get_non_widget_tokens(p: pymupdf.Page) -> list[str]:
            words = []
            for w in p.get_text("words"):
                r = pymupdf.Rect(w[:4])
                if any(r.intersects(wr) for wr in w_rects):
                    continue
                words.append(w[4])
            return words

        if get_non_widget_tokens(page_old) != get_non_widget_tokens(page_new):
            return False, []

        # All changes are confined to widgets. Compare earlier vs later values.
        old_by_name: dict[str, str] = {}
        for w in old_widgets_list:
            name = w.field_name or f"xref_{w.xref}"
            old_by_name[name] = w.field_value or ""

        overwritten: list[dict[str, Any]] = []
        for w in new_widgets_list:
            name = w.field_name or f"xref_{w.xref}"
            new_val = w.field_value or ""
            if name in old_by_name:
                old_val = old_by_name[name]
                if old_val != new_val:
                    # If the widget already held a non-empty value before, this is an overwrite
                    if old_val.strip():
                        overwritten.append(
                            {
                                "field_name": name,
                                "old_value": old_val,
                                "new_value": new_val,
                                "rect": tuple(float(c) for c in w.rect),
                            }
                        )

        return True, overwritten
    except Exception:
        return False, []


def _escalate_severity(removed: list[str], added: list[str]) -> Severity:
    """Determine severity based on the nature of changed tokens."""
    changed_text = " ".join(removed + added)
    if (
        _DATE_RE.search(changed_text)
        or _CURRENCY_RE.search(changed_text)
        or (_DIGIT_RE.search(changed_text) and len([t for t in changed_text.split() if _DIGIT_RE.search(t)]) >= 1)
        or _PARTY_KEYWORDS_RE.search(changed_text)
        or _LEGAL_KEYWORDS_RE.search(changed_text)
    ):
        return Severity.CRITICAL
    return Severity.HIGH


def _get_trailer_id(data: bytes, revision_end: int) -> bytes | None:
    """Extract the first element of the PDF trailer /ID array from a revision slice."""
    slice_bytes = data[:revision_end]
    # Find trailer dict in the last 2048 bytes of this slice
    tail = slice_bytes[-2048:]
    # Look for /ID [ <hex> <hex> ]
    m = re.search(rb"/ID\s*\[\s*<([0-9a-fA-F]+)>", tail)
    if m:
        return bytes.fromhex(m.group(1).decode())
    return None


def detect_incremental(
    pdf_bytes: bytes,
    settings: ForensicsSettings,
) -> list[Finding]:
    """Detect content-changing incremental updates in ``pdf_bytes``.

    Returns a list of Finding objects.
    """
    findings: list[Finding] = []

    # --- Find revisions ---
    try:
        revisions = find_valid_revisions(pdf_bytes, max_revisions=settings.max_revisions)
    except Exception as exc:
        return [
            Finding(
                module=FORENSICS_MODULE,
                type="incremental_update",
                severity=Severity.LOW,
                evidence=str(exc)[:_EVIDENCE_CAP],
                explanation=(
                    "Could not analyze PDF revisions due to a parsing error. "
                    f"Reason: {exc!s}"
                ),
                details={"error": str(exc)},
            )
        ]

    if len(revisions) <= 1:
        # Single revision: no incremental update
        return []

    # Warn if revision count was capped
    raw_eof_count = pdf_bytes.count(b"%%EOF")
    capped = raw_eof_count > settings.max_revisions

    incr_findings: list[Finding] = []
    id_findings: list[Finding] = []

    # Analyze pairs of consecutive revisions
    for i in range(len(revisions) - 1):
        rev_old = revisions[i]
        rev_new = revisions[i + 1]

        try:
            doc_old = pymupdf.open(stream=pdf_bytes[: rev_old.offset_end], filetype="pdf")
            doc_new = pymupdf.open(stream=pdf_bytes[: rev_new.offset_end], filetype="pdf")
        except Exception as exc:
            logger.warning("Cannot open revision pair %d/%d: %s", i, i + 1, exc)
            incr_findings.append(
                Finding(
                    module=FORENSICS_MODULE,
                    type="incremental_update",
                    severity=Severity.LOW,
                    evidence=f"Revision {i + 1} could not be opened: {exc!s}"[:_EVIDENCE_CAP],
                    explanation=(
                        f"PDF revision {i + 1} of {len(revisions)} could not be parsed. "
                        "Manual review recommended."
                    ),
                    details={"revision_old": i, "revision_new": i + 1, "error": str(exc)},
                )
            )
            continue

        try:
            # Compare trailer /ID
            old_id = _get_trailer_id(pdf_bytes, rev_old.offset_end)
            new_id = _get_trailer_id(pdf_bytes, rev_new.offset_end)
            if old_id is not None and new_id is not None and old_id != new_id:
                id_findings.append(
                    Finding(
                        module=FORENSICS_MODULE,
                        type="metadata_anomaly",
                        severity=Severity.LOW,
                        evidence=(
                            f"Trailer /ID changed between revision {i + 1} and {i + 2}: "
                            f"{old_id.hex()[:16]} -> {new_id.hex()[:16]}"
                        )[:_EVIDENCE_CAP],
                        explanation=(
                            "The PDF file identifier (trailer /ID) changed between revisions, "
                            "which can indicate the document was recreated or its identity was altered."
                        ),
                        details={
                            "revision_old": i,
                            "revision_new": i + 1,
                            "id_old": old_id.hex(),
                            "id_new": new_id.hex(),
                        },
                    )
                )

            # Compare page content
            n_pages_old = doc_old.page_count
            n_pages_new = doc_new.page_count
            n_pages = max(n_pages_old, n_pages_new)

            changed_pages: list[int] = []
            page_diffs: list[dict[str, Any]] = []

            for pg_idx in range(n_pages):
                if pg_idx >= n_pages_old or pg_idx >= n_pages_new:
                    changed_pages.append(pg_idx + 1)
                    page_diffs.append(
                        {
                            "page": pg_idx + 1,
                            "change": "page added or removed",
                            "removed": [],
                            "added": [],
                        }
                    )
                    continue

                old_page = doc_old[pg_idx]
                new_page = doc_new[pg_idx]

                old_hash = _page_content_hash(old_page)
                new_hash = _page_content_hash(new_page)

                if old_hash == new_hash:
                    continue

                is_widget, overwritten_widgets = _check_widget_changes(old_page, new_page)
                if is_widget:
                    if not overwritten_widgets:
                        # Form field update of blank fields via incremental revision (standard benign PDF operation)
                        continue
                    # Overwriting an already-filled widget is a content change
                    changed_pages.append(pg_idx + 1)
                    rem_tokens: list[str] = []
                    add_tokens: list[str] = []
                    widget_snippets: list[str] = []
                    widget_bbox = None
                    for ow in overwritten_widgets:
                        fn = ow["field_name"]
                        ov = ow["old_value"]
                        nv = ow["new_value"]
                        rem_tokens.extend(ov.split())
                        add_tokens.extend(nv.split())
                        widget_snippets.append(f"field '{fn}': '{ov}' -> '{nv}'")
                        if widget_bbox is None and "rect" in ow:
                            widget_bbox = ow["rect"]

                    page_diffs.append(
                        {
                            "page": pg_idx + 1,
                            "removed": rem_tokens[:_DIFF_TOKENS_CAP],
                            "added": add_tokens[:_DIFF_TOKENS_CAP],
                            "widget_snippets": widget_snippets,
                            "bbox": widget_bbox,
                        }
                    )
                    continue

                # Content changed — compute text diff
                old_text = _page_normalized_text(old_page)
                new_text = _page_normalized_text(new_page)

                old_tokens = _tokenize(old_text)
                new_tokens = _tokenize(new_text)

                removed, added = _token_diff(old_tokens, new_tokens)

                changed_pages.append(pg_idx + 1)
                page_diffs.append(
                    {
                        "page": pg_idx + 1,
                        "removed": removed[:_DIFF_TOKENS_CAP],
                        "added": added[:_DIFF_TOKENS_CAP],
                    }
                )

            if not changed_pages:
                # Only metadata/form/annotation changes -> low severity
                incr_findings.append(
                    Finding(
                        module=FORENSICS_MODULE,
                        type="incremental_update",
                        severity=Severity.LOW,
                        evidence=(
                            f"Revision {i + 2} of {len(revisions)}: "
                            "no page text or content stream changes detected "
                            "(metadata, annotations, or form fields may have changed)"
                        )[:_EVIDENCE_CAP],
                        explanation=(
                            f"The PDF was saved incrementally (revision {i + 2} of {len(revisions)}), "
                            "but only non-content changes were detected (such as metadata updates, "
                            "annotation additions, or form field values). "
                            "This is a normal operation (e.g., filling a form or adding a signature)."
                        ),
                        details={
                            "revision_old": i,
                            "revision_new": i + 1,
                            "changed_pages": [],
                        },
                    )
                )
            else:
                # Content changed — build evidence string
                snippets: list[str] = []
                for pd in page_diffs[:5]:
                    pg_no = pd["page"]
                    if pd.get("widget_snippets"):
                        snippets.append(f"Page {pg_no}: {'; '.join(pd['widget_snippets'])}")
                    else:
                        removed_snip = " ".join(pd.get("removed", [])[:5])
                        added_snip = " ".join(pd.get("added", [])[:5])
                        if removed_snip or added_snip:
                            snippets.append(
                                f"Page {pg_no}: '{removed_snip}' -> '{added_snip}'"
                            )
                        else:
                            snippets.append(f"Page {pg_no}: content changed")

                evidence = (
                    f"Revision {i + 2} of {len(revisions)} changed page(s) "
                    f"{changed_pages[:10]}: {'; '.join(snippets)}"
                )[:_EVIDENCE_CAP]

                # Collect all changed tokens for severity
                all_removed: list[str] = []
                all_added: list[str] = []
                for pd in page_diffs:
                    all_removed.extend(pd.get("removed", []))
                    all_added.extend(pd.get("added", []))

                severity = _escalate_severity(all_removed, all_added)

                # Build explanation
                changed_str = ", ".join(str(p) for p in changed_pages[:10])
                if len(changed_pages) > 10:
                    changed_str += f" ... ({len(changed_pages)} pages total)"

                explanation_parts = [
                    f"This PDF was modified after its original creation "
                    f"(revision {i + 2} of {len(revisions)}).",
                    f"Page(s) {changed_str} had text or content stream changes.",
                ]
                if snippets:
                    explanation_parts.append(f"Example: {snippets[0]}")
                if severity == Severity.CRITICAL:
                    explanation_parts.append(
                        "The changed content includes numbers, dates, currency values, "
                        "or party names — high risk of document tampering."
                    )

                # Get bbox for first changed page/token if possible
                bbox = page_diffs[0].get("bbox") if page_diffs else None
                if bbox is None and changed_pages:
                    try:
                        first_pg = doc_new[changed_pages[0] - 1]
                        blocks = first_pg.get_text("dict").get("blocks", [])
                        for block in blocks:
                            if block.get("type") == 0:
                                for line in block.get("lines", []):
                                    for span in line.get("spans", []):
                                        raw_bbox = span.get("bbox")
                                        if raw_bbox:
                                            bbox = (
                                                float(raw_bbox[0]),
                                                float(raw_bbox[1]),
                                                float(raw_bbox[2]),
                                                float(raw_bbox[3]),
                                            )
                                            break
                                    if bbox:
                                        break
                                if bbox:
                                    break
                    except Exception:
                        pass

                incr_findings.append(
                    Finding(
                        module=FORENSICS_MODULE,
                        type="incremental_update",
                        severity=severity,
                        page=changed_pages[0] if changed_pages else None,
                        bbox=bbox,
                        evidence=evidence,
                        explanation=" ".join(explanation_parts),
                        details={
                            "revision_old": i,
                            "revision_new": i + 1,
                            "total_revisions": len(revisions),
                            "changed_pages": changed_pages[:20],
                            "page_diffs": page_diffs[:5],
                        },
                    )
                )

        except Exception as exc:
            logger.warning("Error comparing revisions %d and %d: %s", i, i + 1, exc)
            incr_findings.append(
                Finding(
                    module=FORENSICS_MODULE,
                    type="incremental_update",
                    severity=Severity.LOW,
                    evidence=f"Revision comparison error: {exc!s}"[:_EVIDENCE_CAP],
                    explanation=(
                        f"Could not compare revision {i + 1} and {i + 2} of {len(revisions)}. "
                        "Manual review may be needed."
                    ),
                    details={"revision_old": i, "revision_new": i + 1, "error": str(exc)},
                )
            )
        finally:
            try:
                doc_old.close()
            except Exception:
                pass
            try:
                doc_new.close()
            except Exception:
                pass

    # Add cap-exceeded summary if needed
    if capped:
        findings.append(
            Finding(
                module=FORENSICS_MODULE,
                type="incremental_update",
                severity=Severity.LOW,
                evidence=f"PDF contains {raw_eof_count} %%EOF markers; only {settings.max_revisions} analyzed",
                explanation=(
                    f"This PDF has {raw_eof_count} revision markers, which exceeds the analysis "
                    f"cap of {settings.max_revisions}. Only the first and last few revisions were "
                    "analyzed. The document may have been edited many times."
                ),
                details={
                    "raw_eof_count": raw_eof_count,
                    "analyzed_count": settings.max_revisions,
                },
            )
        )

    # Apply per-type caps
    for type_key, type_findings in [
        ("incremental_update", incr_findings),
        ("metadata_anomaly", id_findings),
    ]:
        if len(type_findings) > MAX_FINDINGS_PER_TYPE:
            findings.extend(type_findings[:MAX_FINDINGS_PER_TYPE])
            findings.append(
                Finding(
                    module=FORENSICS_MODULE,
                    type=type_key,
                    severity=Severity.LOW,
                    evidence=f"Cap of {MAX_FINDINGS_PER_TYPE} reached for {type_key}; {len(type_findings)} total",
                    explanation=(
                        f"More than {MAX_FINDINGS_PER_TYPE} {type_key} findings were detected. "
                        "Only the first findings are shown; the document has extensive modifications."
                    ),
                    details={"total_count": len(type_findings), "cap": MAX_FINDINGS_PER_TYPE},
                )
            )
        else:
            findings.extend(type_findings)

    return findings
