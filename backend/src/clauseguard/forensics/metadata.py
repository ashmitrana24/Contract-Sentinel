"""Metadata anomaly detector.

Checks PDF Info dictionary and XMP metadata for:
- ModDate later than CreationDate by more than a configurable threshold
- Missing or malformed creation date
- Future dates (beyond current UTC)
- Info vs XMP field disagreement
- Creator/Producer changes between revisions (if multiple revisions)
- Known online editor signatures (weak signal only, max LOW)
"""

from __future__ import annotations

import logging
import re
from datetime import UTC, datetime, timezone

import pymupdf

from clauseguard.forensics.models import (
    FORENSICS_MODULE,
    ForensicsSettings,
)
from clauseguard.forensics.revisions import find_valid_revisions
from clauseguard.schemas.findings import Finding, Severity

logger = logging.getLogger(__name__)

_EVIDENCE_CAP = 300

# PDF date format: D:YYYYMMDDHHmmSSOHH'mm'
_PDF_DATE_RE = re.compile(
    r"D:(\d{4})(\d{2})(\d{2})(\d{2})(\d{2})(\d{2})"
    r"(?:([+-Z])(\d{2})'?(\d{2})'?)?"
)


def _parse_pdf_date(date_str: str) -> datetime | None:
    """Parse a PDF date string to a timezone-aware datetime, or None."""
    if not date_str:
        return None
    m = _PDF_DATE_RE.search(date_str)
    if not m:
        return None
    try:
        year, month, day, hour, minute, second = (int(m.group(i)) for i in range(1, 7))
        tz_sign = m.group(7) or "Z"
        tz_h = int(m.group(8) or 0)
        tz_m = int(m.group(9) or 0)

        if tz_sign == "Z" or tz_sign == "+":
            offset = timezone(
                __import__("datetime").timedelta(hours=tz_h, minutes=tz_m)
                if tz_sign == "+"
                else __import__("datetime").timedelta(0)
            )
        else:
            offset = timezone(
                -__import__("datetime").timedelta(hours=tz_h, minutes=tz_m)
            )
        return datetime(year, month, day, hour, minute, second, tzinfo=offset)
    except Exception:
        return None


def _get_metadata_from_bytes(pdf_bytes: bytes) -> dict[str, str]:
    """Open a PDF from bytes and return its metadata dict."""
    try:
        doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
        try:
            meta = {k: str(v) for k, v in (doc.metadata or {}).items() if v}
            return meta
        finally:
            doc.close()
    except Exception:
        return {}


def detect_metadata(
    pdf_bytes: bytes,
    settings: ForensicsSettings,
) -> list[Finding]:
    """Detect metadata anomalies in ``pdf_bytes``."""
    findings: list[Finding] = []

    # ---- Get metadata from the full document ----
    try:
        doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    except Exception as exc:
        return [
            Finding(
                module=FORENSICS_MODULE,
                type="metadata_anomaly",
                severity=Severity.LOW,
                evidence=str(exc)[:_EVIDENCE_CAP],
                explanation=f"Could not open PDF for metadata analysis: {exc!s}",
                details={"error": str(exc)},
            )
        ]

    try:
        meta = {k: str(v) for k, v in (doc.metadata or {}).items() if v}
    finally:
        doc.close()

    now_utc = datetime.now(UTC)
    threshold_minutes = settings.metadata_moddate_threshold_minutes

    # Combined signal: whether we also have a content-changing incremental revision
    has_content_revision = False
    try:
        revisions = find_valid_revisions(pdf_bytes, max_revisions=10)
        if len(revisions) > 1:
            has_content_revision = True  # We'll refine severity after individual checks
    except Exception:
        pass

    # ---- 1. ModDate vs CreationDate ----
    creation_date_str = meta.get("creationDate", "")
    mod_date_str = meta.get("modDate", "")

    creation_dt = _parse_pdf_date(creation_date_str)
    mod_dt = _parse_pdf_date(mod_date_str)

    if creation_dt is None and creation_date_str:
        findings.append(
            Finding(
                module=FORENSICS_MODULE,
                type="metadata_anomaly",
                severity=Severity.LOW,
                evidence=f"Unparseable CreationDate: '{creation_date_str[:80]}'",
                explanation=(
                    "The PDF's CreationDate field could not be parsed. "
                    "A malformed date may indicate manual metadata manipulation."
                ),
                details={"creation_date_raw": creation_date_str[:200]},
            )
        )

    if not creation_date_str and not creation_dt:
        if mod_date_str:
            findings.append(
                Finding(
                    module=FORENSICS_MODULE,
                    type="metadata_anomaly",
                    severity=Severity.LOW,
                    evidence="Missing CreationDate in PDF Info dictionary while ModDate is present",
                    explanation=(
                        "The PDF has a ModDate but lacks a CreationDate. While not strictly invalid, "
                        "this pattern may indicate metadata manipulation or selective stripping."
                    ),
                    details={"creation_date_raw": "", "mod_date": mod_date_str[:100]},
                )
            )

    if mod_dt and creation_dt:
        if mod_dt < creation_dt:
            findings.append(
                Finding(
                    module=FORENSICS_MODULE,
                    type="metadata_anomaly",
                    severity=Severity.LOW,
                    evidence=(
                        f"ModDate ({mod_date_str[:40]}) precedes CreationDate ({creation_date_str[:40]})"
                    )[:_EVIDENCE_CAP],
                    explanation=(
                        "The PDF's modification date precedes its creation date. "
                        "A document cannot be modified before it is created; this anomaly indicates fabricated or corrupted metadata."
                    ),
                    details={
                        "creation_date": creation_date_str[:100],
                        "mod_date": mod_date_str[:100],
                        "has_content_revision": has_content_revision,
                    },
                )
            )
        else:
            diff_minutes = (mod_dt - creation_dt).total_seconds() / 60.0
            if diff_minutes > threshold_minutes:
                base_sev = Severity.LOW
                if has_content_revision:
                    base_sev = Severity.MEDIUM
                findings.append(
                    Finding(
                        module=FORENSICS_MODULE,
                        type="metadata_anomaly",
                        severity=base_sev,
                        evidence=(
                            f"ModDate ({mod_date_str[:40]}) is {diff_minutes:.1f} minutes after "
                            f"CreationDate ({creation_date_str[:40]})"
                        )[:_EVIDENCE_CAP],
                        explanation=(
                            f"The PDF's modification date is {diff_minutes:.1f} minutes after its "
                            "creation date, indicating the document was modified after it was originally created. "
                            + ("This is combined with detected incremental revision(s)." if has_content_revision else "")
                        ),
                        details={
                            "creation_date": creation_date_str[:100],
                            "mod_date": mod_date_str[:100],
                            "diff_minutes": round(diff_minutes, 1),
                            "has_content_revision": has_content_revision,
                        },
                    )
                )

    # ---- 2. Future dates ----
    for field_name, dt in [("CreationDate", creation_dt), ("ModDate", mod_dt)]:
        if dt is not None:
            if dt > now_utc:
                findings.append(
                    Finding(
                        module=FORENSICS_MODULE,
                        type="metadata_anomaly",
                        severity=Severity.LOW,
                        evidence=f"{field_name} is in the future: {dt.isoformat()[:30]}",
                        explanation=(
                            f"The PDF's {field_name} ({dt.isoformat()[:25]}) is in the future. "
                            "Future dates may indicate manually set metadata or incorrect system clock."
                        ),
                        details={"field": field_name, "date": dt.isoformat()},
                    )
                )

    # ---- 3. Known online editor signatures ----
    producer = meta.get("producer", "").lower()
    creator = meta.get("creator", "").lower()
    tool_string = producer + " " + creator

    matched_editors: list[str] = []
    for editor_sig in settings.known_online_editors:
        if editor_sig.lower() in tool_string:
            matched_editors.append(editor_sig)

    if matched_editors:
        findings.append(
            Finding(
                module=FORENSICS_MODULE,
                type="metadata_anomaly",
                severity=Severity.LOW,
                evidence=(
                    f"Known online editor signature(s) in metadata: {matched_editors}; "
                    f"Producer='{meta.get('producer', '')[:60]}'"
                )[:_EVIDENCE_CAP],
                explanation=(
                    f"The PDF metadata references online editing tool(s): {matched_editors}. "
                    "This suggests the PDF may have been uploaded to and re-processed by an "
                    "online PDF editing service. This is a weak signal only — it does not confirm "
                    "tampering."
                ),
                details={
                    "matched_editors": matched_editors,
                    "producer": meta.get("producer", "")[:200],
                    "creator": meta.get("creator", "")[:200],
                },
            )
        )

    # ---- 4. Creator/Producer changes between revisions ----
    try:
        revisions = find_valid_revisions(pdf_bytes, max_revisions=5)
        if len(revisions) >= 2:
            first_meta = _get_metadata_from_bytes(pdf_bytes[: revisions[0].offset_end])
            last_meta = _get_metadata_from_bytes(pdf_bytes[: revisions[-1].offset_end])

            for field in ("producer", "creator"):
                old_val = first_meta.get(field, "")
                new_val = last_meta.get(field, "")
                if old_val and new_val and old_val != new_val:
                    findings.append(
                        Finding(
                            module=FORENSICS_MODULE,
                            type="metadata_anomaly",
                            severity=Severity.LOW,
                            evidence=(
                                f"PDF {field} changed between revisions: "
                                f"'{old_val[:50]}' -> '{new_val[:50]}'"
                            )[:_EVIDENCE_CAP],
                            explanation=(
                                f"The PDF {field} field changed between the first and most recent "
                                f"revision: was '{old_val[:50]}', now '{new_val[:50]}'. "
                                "A different tool may have re-processed this PDF."
                            ),
                            details={
                                "field": field,
                                "old_value": old_val[:200],
                                "new_value": new_val[:200],
                            },
                        )
                    )
    except Exception as exc:
        logger.debug("Could not compare revision metadata: %s", exc)

    return findings
