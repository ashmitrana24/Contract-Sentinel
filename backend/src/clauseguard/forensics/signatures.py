"""Signature integrity detector using pyHanko.

For each embedded signature in the PDF:
- Checks byte-range integrity (digest matches computed digest)
- Evaluates signature coverage level and modification level
- Maps to findings:
    - post_signature_modification (CRITICAL): content changed after signing
    - signature_invalid (CRITICAL): byte-range digest check fails
    - incremental_update (LOW/INFO): only allowed form/signing revisions after signature

Trust chain evaluation is explicitly NOT performed; self-signed certs are fine.
Evidence explicitly states trust was not evaluated.

A PDF with no signatures produces no signature findings.
Malformed signatures produce a logged skip or a LOW finding, never a crash.
"""

from __future__ import annotations

import io
import logging
from typing import Any

from clauseguard.forensics.models import (
    FORENSICS_MODULE,
    ForensicsSettings,
)
from clauseguard.schemas.findings import Finding, Severity

logger = logging.getLogger(__name__)

_EVIDENCE_CAP = 300


def _import_pyhanko() -> tuple[Any, Any, Any, Any, Any]:
    """Lazy-import pyHanko modules to provide a clean error if not installed."""
    try:
        from pyhanko.pdf_utils.reader import PdfFileReader
        from pyhanko.sign.diff_analysis import ModificationLevel
        from pyhanko.sign.validation import (
            EmbeddedPdfSignature,
            SignatureCoverageLevel,
            validate_pdf_signature,
        )

        return (
            PdfFileReader,
            EmbeddedPdfSignature,
            SignatureCoverageLevel,
            ModificationLevel,
            validate_pdf_signature,
        )
    except ImportError as exc:
        raise ImportError(f"pyHanko is not installed: {exc}") from exc


def _coverage_description(level: Any) -> str:
    try:
        from pyhanko.sign.validation import SignatureCoverageLevel

        mapping = {
            SignatureCoverageLevel.UNCLEAR: "unclear",
            SignatureCoverageLevel.CONTIGUOUS_BLOCK_FROM_START: "contiguous block from start",
            SignatureCoverageLevel.ENTIRE_REVISION: "entire revision",
            SignatureCoverageLevel.ENTIRE_FILE: "entire file",
        }
        return mapping.get(level, str(level))
    except Exception:
        return str(level)


def _mod_level_description(level: Any) -> str:
    try:
        from pyhanko.sign.diff_analysis import ModificationLevel

        mapping = {
            ModificationLevel.NONE: "none",
            ModificationLevel.LTA_UPDATES: "LTA timestamp updates only",
            ModificationLevel.FORM_FILLING: "form filling only",
            ModificationLevel.ANNOTATIONS: "annotations only",
            ModificationLevel.OTHER: "other (content) changes",
        }
        return mapping.get(level, str(level))
    except Exception:
        return str(level)


def detect_signatures(
    pdf_bytes: bytes,
    settings: ForensicsSettings,
) -> list[Finding]:
    """Detect signature integrity issues in ``pdf_bytes``."""
    findings: list[Finding] = []

    # Import pyHanko
    try:
        (
            PdfFileReader,
            _EmbSig,
            SignatureCoverageLevel,
            ModificationLevel,
            validate_pdf_signature,
        ) = _import_pyhanko()
    except ImportError as exc:
        return [
            Finding(
                module=FORENSICS_MODULE,
                type="signature_invalid",
                severity=Severity.LOW,
                evidence=str(exc)[:_EVIDENCE_CAP],
                explanation=(
                    "pyHanko is not available; signature integrity could not be verified. "
                    "Install pyHanko to enable this check."
                ),
                details={"error": str(exc)},
            )
        ]

    # Open with pyHanko
    try:
        reader = PdfFileReader(io.BytesIO(pdf_bytes))
    except Exception as exc:
        logger.debug("pyHanko could not open PDF: %s", exc)
        return [
            Finding(
                module=FORENSICS_MODULE,
                type="signature_invalid",
                severity=Severity.LOW,
                evidence=f"pyHanko could not open PDF: {exc!s}"[:_EVIDENCE_CAP],
                explanation=(
                    "The PDF could not be opened by pyHanko for signature analysis. "
                    f"Reason: {exc!s}"
                ),
                details={"error": str(exc)},
            )
        ]

    # Get embedded signatures
    try:
        sigs = reader.embedded_signatures
    except Exception as exc:
        logger.debug("Could not enumerate embedded signatures: %s", exc)
        return []

    if not sigs:
        # No signatures — no findings
        return []

    # Temporarily silence verbose certvalidator logger during signature validation
    # because trust chains are deliberately out of scope and self-signed certs are expected.
    cert_logger = logging.getLogger("pyhanko_certvalidator")
    diff_logger = logging.getLogger("pyhanko.sign.diff_analysis")
    cms_logger = logging.getLogger("pyhanko.sign.validation.generic_cms")
    old_cert_level = cert_logger.level
    old_diff_level = diff_logger.level
    old_cms_level = cms_logger.level
    cert_logger.setLevel(logging.CRITICAL)
    diff_logger.setLevel(logging.CRITICAL)
    cms_logger.setLevel(logging.CRITICAL)

    try:
        for sig_idx, sig in enumerate(sigs):
            sig_label = f"Signature {sig_idx + 1} (field: {getattr(sig, 'field_name', 'unknown')})"
            logger.debug("Analyzing %s", sig_label)

            try:
                status = validate_pdf_signature(sig)
            except Exception as exc:
                logger.warning("validate_pdf_signature failed for %s: %s", sig_label, exc)
                findings.append(
                    Finding(
                        module=FORENSICS_MODULE,
                        type="signature_invalid",
                        severity=Severity.CRITICAL,
                        evidence=f"{sig_label}: validation raised exception: {exc!s}"[:_EVIDENCE_CAP],
                        explanation=(
                            f"{sig_label} could not be validated due to an internal error or corruption. "
                            f"Reason: {exc!s} "
                            "Note: certificate trust chain was not evaluated."
                        ),
                        details={"sig_index": sig_idx, "error": str(exc)},
                    )
                )
                continue

            intact = bool(status.intact)
            coverage = status.coverage
            docmdp_ok = status.docmdp_ok
            mod_level = getattr(status, "modification_level", None)
            diff_res = getattr(status, "diff_result", None)

            # ---- Check 1: Digest integrity ----
            if not intact:
                findings.append(
                    Finding(
                        module=FORENSICS_MODULE,
                        type="signature_invalid",
                        severity=Severity.CRITICAL,
                        evidence=(
                            f"{sig_label}: signature digest does not match document content. "
                            f"Coverage: {_coverage_description(coverage) if coverage else 'unknown'}"
                        )[:_EVIDENCE_CAP],
                        explanation=(
                            f"The cryptographic digest of {sig_label} does not match the signed "
                            "portion of the document. The document has been altered within the "
                            "signed byte range, invalidating the signature. "
                            "Note: certificate trust chain was not evaluated."
                        ),
                        details={
                            "sig_index": sig_idx,
                            "field_name": getattr(sig, "field_name", ""),
                            "coverage": _coverage_description(coverage) if coverage else None,
                            "trust_not_evaluated": True,
                        },
                    )
                )
                continue

            # ---- Check 2: Signature coverage and post-signing modifications ----
            if coverage is not None:
                if coverage == SignatureCoverageLevel.ENTIRE_FILE:
                    # Intact signature covering the entire file
                    pass
                elif coverage == SignatureCoverageLevel.ENTIRE_REVISION:
                    if docmdp_ok is False or (
                        mod_level is not None and mod_level == ModificationLevel.OTHER
                    ):
                        findings.append(
                            Finding(
                                module=FORENSICS_MODULE,
                                type="post_signature_modification",
                                severity=Severity.CRITICAL,
                                evidence=(
                                    f"{sig_label}: content changes detected after signing. "
                                    f"Coverage: {_coverage_description(coverage)}, "
                                    f"Modification: {_mod_level_description(mod_level)}"
                                )[:_EVIDENCE_CAP],
                                explanation=(
                                    f"The document was modified after {sig_label} was applied. "
                                    f"The signature covers the revision it was applied to, but "
                                    f"subsequent modifications ({_mod_level_description(mod_level)}) "
                                    "altered the document content. "
                                    "Note: certificate trust chain was not evaluated."
                                ),
                                details={
                                    "sig_index": sig_idx,
                                    "field_name": getattr(sig, "field_name", ""),
                                    "coverage": _coverage_description(coverage),
                                    "modification_level": _mod_level_description(mod_level),
                                    "diff_result": str(diff_res)[:_EVIDENCE_CAP] if diff_res else None,
                                    "trust_not_evaluated": True,
                                },
                            )
                        )
                    else:
                        findings.append(
                            Finding(
                                module=FORENSICS_MODULE,
                                type="incremental_update",
                                severity=Severity.LOW,
                                evidence=(
                                    f"{sig_label}: permitted modifications after signing. "
                                    f"Coverage: {_coverage_description(coverage)}, "
                                    f"Modification: {_mod_level_description(mod_level)}"
                                )[:_EVIDENCE_CAP],
                                explanation=(
                                    f"The document was modified after {sig_label} was applied, "
                                    f"but only in permitted ways: {_mod_level_description(mod_level)}. "
                                    "Note: certificate trust chain was not evaluated."
                                ),
                                details={
                                    "sig_index": sig_idx,
                                    "field_name": getattr(sig, "field_name", ""),
                                    "coverage": _coverage_description(coverage),
                                    "modification_level": _mod_level_description(mod_level),
                                    "trust_not_evaluated": True,
                                },
                            )
                        )
                elif coverage == SignatureCoverageLevel.CONTIGUOUS_BLOCK_FROM_START:
                    if docmdp_ok is False or (
                        mod_level is not None and mod_level == ModificationLevel.OTHER
                    ):
                        findings.append(
                            Finding(
                                module=FORENSICS_MODULE,
                                type="post_signature_modification",
                                severity=Severity.CRITICAL,
                                evidence=(
                                    f"{sig_label}: bytes exist after signature with content changes. "
                                    f"Coverage: {_coverage_description(coverage)}"
                                )[:_EVIDENCE_CAP],
                                explanation=(
                                    f"The document has content after the signed byte range of {sig_label}. "
                                    "Content-level changes were detected in the unsigned portion, indicating "
                                    "the document was tampered with after signing. "
                                    "Note: certificate trust chain was not evaluated."
                                ),
                                details={
                                    "sig_index": sig_idx,
                                    "field_name": getattr(sig, "field_name", ""),
                                    "coverage": _coverage_description(coverage),
                                    "modification_level": _mod_level_description(mod_level)
                                    if mod_level
                                    else None,
                                    "trust_not_evaluated": True,
                                },
                            )
                        )
                    else:
                        findings.append(
                            Finding(
                                module=FORENSICS_MODULE,
                                type="incremental_update",
                                severity=Severity.LOW,
                                evidence=(
                                    f"{sig_label}: file has bytes after signature, "
                                    f"coverage: {_coverage_description(coverage)}, "
                                    f"modification: {_mod_level_description(mod_level) if mod_level else 'unknown'}"
                                )[:_EVIDENCE_CAP],
                                explanation=(
                                    f"The file has content after the signed byte range of {sig_label}. "
                                    "No unauthorized content changes were detected. "
                                    "Note: certificate trust chain was not evaluated."
                                ),
                                details={
                                    "sig_index": sig_idx,
                                    "field_name": getattr(sig, "field_name", ""),
                                    "coverage": _coverage_description(coverage),
                                    "modification_level": _mod_level_description(mod_level)
                                    if mod_level
                                    else None,
                                    "trust_not_evaluated": True,
                                },
                            )
                        )
                elif coverage == SignatureCoverageLevel.UNCLEAR:
                    findings.append(
                        Finding(
                            module=FORENSICS_MODULE,
                            type="signature_invalid",
                            severity=Severity.LOW,
                            evidence=f"{sig_label}: coverage level is unclear"[:_EVIDENCE_CAP],
                            explanation=(
                                f"The coverage of {sig_label} could not be determined. "
                                "The signature structure may be non-standard. "
                                "Note: certificate trust chain was not evaluated."
                            ),
                            details={
                                "sig_index": sig_idx,
                                "field_name": getattr(sig, "field_name", ""),
                                "coverage": "unclear",
                                "trust_not_evaluated": True,
                            },
                        )
                    )

        return findings
    finally:
        cert_logger.setLevel(old_cert_level)
        diff_logger.setLevel(old_diff_level)
        cms_logger.setLevel(old_cms_level)
