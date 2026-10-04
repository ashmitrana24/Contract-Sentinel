# DECISIONS.md — Module 3: PDF Structure Forensics Design Decisions

This document records the architectural and design decisions made while implementing Module 3 (PDF Structure Forensics).

---

## D-01: Multi-Revision Validation via `%%EOF` Marker Scanning

**Decision**: Instead of relying solely on PDF parser abstractions that only see the final revision, we scan the raw binary stream for `%%EOF` markers and validate each byte prefix by opening it as a standalone PDF with PyMuPDF.

**Rationale**: Attackers inject incremental updates (`IncrementalEditTamper`) by appending changes after the initial document. PyMuPDF's `incremental=True` leaves earlier revisions intact in the byte stream. Scanning `%%EOF` offsets and verifying each slice provides exact revision boundaries.

**False Positive Guards**:
- Discard candidate slices that fail to open or have 0 pages (handles linearized first-page headers and corrupt fragments).
- Require at least 2 distinct valid revisions before flagging incremental edits.
- Revisions with only metadata or form updates are marked `LOW` severity; only unauthorized page content or text modifications are escalated to `HIGH` or `CRITICAL`.

---

## D-02: Hidden and Invisible Text Detection via `get_texttrace()`

**Decision**: Use PyMuPDF's low-level `get_texttrace()` API rather than standard `get_text("words")` or `get_text("blocks")`.

**Rationale**: `get_texttrace()` provides direct access to:
- Render mode (`type=3` invisible text)
- Exact font size (catching sub-1pt micro-text like `size=0.5`)
- Fill color and alpha opacity
- Character origins and bounding boxes

**Conservative Tuning**:
- **Contrast calculation**: Relative luminance and WCAG 2.0 contrast ratio computed against effective background. Text on white page with contrast < 1.5 is flagged; white text on dark background (headers/banners) has high contrast (> 10.0) and is explicitly NOT flagged.
- **Footnote protection**: Normal small text ($\ge 6\text{pt}$) is never flagged as tiny text; threshold is set strictly to $< 2.0\text{pt}$.
- **OCR layer heuristic**: Invisible render mode (`type=3`) on pages containing large image scans is treated as an OCR text layer and exempted from false alarm flagging.
- **Occlusion detection**: A text span is only considered occluded if an opaque white or near-white rectangle ($\ge 90\%$ opacity, RGB components $\ge 0.9$) was drawn *after* the text in the drawing sequence. Translucent or yellow highlight annotations are not flagged as occluding white-outs.

---

## D-03: Signature Integrity Verification via pyHanko

**Decision**: Use `pyhanko.sign.validation.validate_pdf_signature` to evaluate cryptographic byte-range digests and DocMDP modification policies, while explicitly skipping certificate trust chain validation.

**Rationale**:
- ClauseGuard's forensic scope is document integrity and tamper detection, not PKI certificate authority trust evaluation.
- Contract signatures may be self-signed, internally generated, or signed by enterprise CAs not present in public trust stores.
- `status.intact` validates that the signed byte-range digest matches the CMS cryptographic signature.
- `status.docmdp_ok` evaluates whether subsequent incremental updates comply with PDF signature modification policies (detecting post-signing content alterations).

**Severity Mapping**:
- `signature_invalid` (`CRITICAL`): Byte-range cryptographic digest check failed (byte corruption or tamper).
- `post_signature_modification` (`CRITICAL`): Unauthorized content changes detected after signing.
- `incremental_update` (`LOW`): Permitted changes only (e.g. form filling, signing maintenance).

---

## D-04: Metadata Anomaly Detection

**Decision**: Compare Info dictionary and XMP metadata with strict conservative rules:
- `ModDate` earlier than `CreationDate` indicates fabricated or clock-skewed metadata (`LOW`).
- `ModDate` significantly later than `CreationDate` without incremental revisions is noted; if combined with content-changing revisions, it supports escalating suspicion (`MEDIUM`).
- Known online editor signatures (`iLovePDF`, `Smallpdf`, `Sejda`) in producer/creator strings are flagged as weak indicators (`LOW`).
- Missing `CreationDate` is only flagged if `ModDate` is present; plain programmatic PDFs without dates are not falsely flagged.

---

## D-05: Orchestrator Isolation and Time Budgeting

**Decision**: The `analyze(pdf_bytes, settings)` orchestrator runs all detectors in isolation inside try/except blocks with per-document execution time budgeting.

**Rationale**:
- A failure or malformed structure in one detector (e.g. invalid ASN.1 signature structure) must never crash the entire analysis.
- Unhandled detector exceptions set `DetectorStatus.status = "error"` and mark the report `partial`, while allowing all remaining detectors to complete.
- Budget checks between detectors prevent catastrophic slowdowns on complex or adversarial PDFs.
