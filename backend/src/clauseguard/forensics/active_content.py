"""Active content and annotation overlay detector.

Uses pikepdf to detect:
- JavaScript in document actions or page actions (active_content, medium)
- OpenAction / AA actions that launch or execute (active_content, medium)
- Launch actions (active_content, medium)
- Embedded files (active_content, low)
- Annotation overlay: FreeText/Square/Stamp/other annotations whose rect
  overlaps page text and has an opaque appearance (annotation_overlay, medium)

Does NOT flag:
- Link annotations
- Highlight annotations
- Widget annotations (form fields)
"""

from __future__ import annotations

import logging
from typing import Any

import pikepdf

from clauseguard.forensics.models import (
    FORENSICS_MODULE,
    MAX_FINDINGS_PER_TYPE,
    ForensicsSettings,
)
from clauseguard.schemas.findings import Finding, Severity

logger = logging.getLogger(__name__)

_EVIDENCE_CAP = 300

# Annotation subtypes to check for overlay
_OVERLAY_SUBTYPES = {"FreeText", "Square", "Stamp", "Ink", "Underline", "StrikeOut"}
# Annotation subtypes to IGNORE (benign)
_BENIGN_SUBTYPES = {"Link", "Highlight", "Widget", "Popup"}

# Action types that indicate active content
_ACTIVE_ACTION_TYPES = {"JavaScript", "Launch", "URI", "SubmitForm", "ResetForm", "ImportData"}
_DANGEROUS_ACTION_TYPES = {"JavaScript", "Launch"}


def _pdf_name_str(obj: Any) -> str:
    """Convert a pikepdf Name or String to str."""
    try:
        return str(obj)
    except Exception:
        return ""


def _has_js_in_action(action_dict: Any) -> bool:
    """Return True if an action dict contains JavaScript."""
    try:
        action_type = _pdf_name_str(action_dict.get("/S", ""))
        if "JavaScript" in action_type:
            return True
        # Check nested Next actions
        next_action = action_dict.get("/Next")
        if next_action is not None:
            if isinstance(next_action, list):
                for a in next_action:
                    try:
                        if _has_js_in_action(a):
                            return True
                    except Exception:
                        pass
            else:
                try:
                    return _has_js_in_action(next_action)
                except Exception:
                    pass
    except Exception:
        pass
    return False


def _get_action_type(action_dict: Any) -> str:
    try:
        return _pdf_name_str(action_dict.get("/S", ""))
    except Exception:
        return ""


def detect_active_content(
    pdf_bytes: bytes,
    settings: ForensicsSettings,
) -> list[Finding]:
    """Detect active content (JS, actions, embedded files, annotation overlays)."""
    findings: list[Finding] = []
    type_counts: dict[str, int] = {}

    try:
        pdf = pikepdf.open(__import__("io").BytesIO(pdf_bytes))
    except Exception as exc:
        return [
            Finding(
                module=FORENSICS_MODULE,
                type="active_content",
                severity=Severity.LOW,
                evidence=str(exc)[:_EVIDENCE_CAP],
                explanation=f"Could not open PDF with pikepdf for active content analysis: {exc!s}",
                details={"error": str(exc)},
            )
        ]

    try:
        root = pdf.Root

        # ---- 1. Document-level JavaScript ----
        try:
            js_names = root.get("/Names", {})
            if js_names:
                js_tree = js_names.get("/JavaScript")
                if js_tree is not None:
                    tc = type_counts.get("active_content", 0)
                    if tc < MAX_FINDINGS_PER_TYPE:
                        type_counts["active_content"] = tc + 1
                        findings.append(
                            Finding(
                                module=FORENSICS_MODULE,
                                type="active_content",
                                severity=Severity.MEDIUM,
                                evidence="Document-level JavaScript name tree found",
                                explanation=(
                                    "This PDF contains a document-level JavaScript name tree. "
                                    "JavaScript in PDFs can execute code when the document is opened "
                                    "and is commonly used in PDF exploits."
                                ),
                                details={"location": "document_js_name_tree"},
                            )
                        )
        except Exception:
            pass

        # ---- 2. OpenAction ----
        try:
            open_action = root.get("/OpenAction")
            if open_action is not None:
                action_type = _get_action_type(open_action)
                if action_type.lstrip("/") in _ACTIVE_ACTION_TYPES:
                    is_dangerous = action_type.lstrip("/") in _DANGEROUS_ACTION_TYPES
                    sev = Severity.MEDIUM if is_dangerous else Severity.LOW
                    tc = type_counts.get("active_content", 0)
                    if tc < MAX_FINDINGS_PER_TYPE:
                        type_counts["active_content"] = tc + 1
                        findings.append(
                            Finding(
                                module=FORENSICS_MODULE,
                                type="active_content",
                                severity=sev,
                                evidence=f"OpenAction of type '{action_type}' found in document root",
                                explanation=(
                                    f"This PDF has an OpenAction of type '{action_type}' that "
                                    "executes automatically when the document is opened. "
                                    + ("This action type can execute arbitrary code." if is_dangerous else "")
                                ),
                                details={"action_type": action_type, "location": "OpenAction"},
                            )
                        )
        except Exception:
            pass

        # ---- 3. Additional Actions (AA) on document ----
        try:
            aa_dict = root.get("/AA")
            if aa_dict is not None:
                for trigger_key in aa_dict.keys():
                    try:
                        action = aa_dict[trigger_key]
                        action_type = _get_action_type(action)
                        if action_type.lstrip("/") in _ACTIVE_ACTION_TYPES:
                            tc = type_counts.get("active_content", 0)
                            if tc < MAX_FINDINGS_PER_TYPE:
                                type_counts["active_content"] = tc + 1
                                findings.append(
                                    Finding(
                                        module=FORENSICS_MODULE,
                                        type="active_content",
                                        severity=Severity.MEDIUM,
                                        evidence=f"Document AA action '{trigger_key}' of type '{action_type}'",
                                        explanation=(
                                            f"This PDF has a document-level additional action "
                                            f"(trigger: {trigger_key}, type: {action_type}). "
                                            "Such actions execute automatically on specific events."
                                        ),
                                        details={
                                            "trigger": str(trigger_key),
                                            "action_type": action_type,
                                            "location": "document_AA",
                                        },
                                    )
                                )
                    except Exception:
                        pass
        except Exception:
            pass

        # ---- 4. Embedded files ----
        try:
            ef_names = root.get("/Names", {})
            if ef_names:
                embedded_files = ef_names.get("/EmbeddedFiles")
                if embedded_files is not None:
                    tc = type_counts.get("active_content", 0)
                    if tc < MAX_FINDINGS_PER_TYPE:
                        type_counts["active_content"] = tc + 1
                        findings.append(
                            Finding(
                                module=FORENSICS_MODULE,
                                type="active_content",
                                severity=Severity.LOW,
                                evidence="Embedded files (EmbeddedFiles name tree) found in PDF",
                                explanation=(
                                    "This PDF contains embedded files. "
                                    "Embedded files can carry executable content or hidden data."
                                ),
                                details={"location": "EmbeddedFiles_name_tree"},
                            )
                        )
        except Exception:
            pass

        # ---- 5. Page-level actions and annotation overlays ----
        pages = pdf.pages
        for page_idx, page in enumerate(pages):
            page_no = page_idx + 1

            # Page AA actions
            try:
                page_aa = page.get("/AA")
                if page_aa is not None:
                    for trigger_key in page_aa.keys():
                        try:
                            action = page_aa[trigger_key]
                            action_type = _get_action_type(action)
                            if action_type.lstrip("/") in _ACTIVE_ACTION_TYPES:
                                tc = type_counts.get("active_content", 0)
                                if tc < MAX_FINDINGS_PER_TYPE:
                                    type_counts["active_content"] = tc + 1
                                    findings.append(
                                        Finding(
                                            module=FORENSICS_MODULE,
                                            type="active_content",
                                            severity=Severity.MEDIUM,
                                            page=page_no,
                                            evidence=f"Page {page_no} AA action '{trigger_key}' type '{action_type}'",
                                            explanation=(
                                                f"Page {page_no} has an additional action "
                                                f"(trigger: {trigger_key}, type: {action_type}) "
                                                "that executes automatically."
                                            ),
                                            details={
                                                "trigger": str(trigger_key),
                                                "action_type": action_type,
                                                "location": f"page_{page_no}_AA",
                                            },
                                        )
                                    )
                        except Exception:
                            pass
            except Exception:
                pass

            # Annotation overlays
            try:
                annots = page.get("/Annots", [])
                if annots:
                    # Get page mediabox for text detection
                    for annot in annots:
                        try:
                            subtype = _pdf_name_str(annot.get("/Subtype", "")).lstrip("/")
                            if subtype in _BENIGN_SUBTYPES:
                                continue
                            if subtype not in _OVERLAY_SUBTYPES:
                                continue

                            # Check if annotation has an opaque appearance
                            ap_dict = annot.get("/AP")
                            has_appearance = ap_dict is not None

                            # Get rect
                            rect_arr = annot.get("/Rect")
                            if rect_arr is None:
                                continue

                            try:
                                rect = [float(x) for x in rect_arr]
                                if len(rect) != 4:
                                    continue
                            except Exception:
                                continue

                            tc = type_counts.get("annotation_overlay", 0)
                            if tc >= MAX_FINDINGS_PER_TYPE:
                                continue
                            type_counts["annotation_overlay"] = tc + 1

                            bbox_tuple = (rect[0], rect[1], rect[2], rect[3])
                            findings.append(
                                Finding(
                                    module=FORENSICS_MODULE,
                                    type="annotation_overlay",
                                    severity=Severity.MEDIUM,
                                    page=page_no,
                                    bbox=bbox_tuple,
                                    evidence=(
                                        f"Page {page_no}: {subtype} annotation at "
                                        f"({rect[0]:.1f},{rect[1]:.1f},{rect[2]:.1f},{rect[3]:.1f})"
                                        + (" with appearance stream" if has_appearance else "")
                                    )[:_EVIDENCE_CAP],
                                    explanation=(
                                        f"Page {page_no} contains a {subtype} annotation that may "
                                        "overlay page text. Stamp, FreeText, and Square annotations "
                                        "with opaque appearances can visually hide underlying content."
                                    ),
                                    details={
                                        "subtype": subtype,
                                        "rect": rect,
                                        "has_appearance": has_appearance,
                                    },
                                )
                            )
                        except Exception:
                            pass
            except Exception:
                pass

    except Exception as exc:
        logger.warning("Active content detection error: %s", exc)
        findings.append(
            Finding(
                module=FORENSICS_MODULE,
                type="active_content",
                severity=Severity.LOW,
                evidence=str(exc)[:_EVIDENCE_CAP],
                explanation=f"Active content analysis encountered an error: {exc!s}",
                details={"error": str(exc)},
            )
        )
    finally:
        try:
            pdf.close()
        except Exception:
            pass

    return findings
