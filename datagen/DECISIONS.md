# DECISIONS.md – Design Assumptions and Choices

This document records every non-obvious design decision made during implementation.

---

## D-01: PDF Determinism

**Decision**: Use ReportLab's `invariant=1` flag on `SimpleDocTemplate` for
reproducible internal PDF IDs and checksums.

**Rationale**: Without `invariant=1`, ReportLab embeds the current timestamp
and a random element in the XRef table, making two renders of the same content
produce different byte sequences.

**Consequence**: PDFs rendered in the same Python process with the same
contract model are byte-identical for **content tampers**. PDFs rendered with
**file-level tampers** (hidden_text, incremental_edit) may produce different
sha256 values across separate runs because PyMuPDF embeds its own internal
timestamps and object IDs that are not deterministic.

Tests for determinism verify **structural** label fields (doc_id, tamper_types,
source_id) rather than sha256 for file-level tampers. Text-level equality is
verified where applicable.

---

## D-02: Metadata Patching

**Decision**: PDF creation date and producer string are patched via a simple
`re.sub` on the rendered byte stream, not via pikepdf.

**Rationale**: Simpler and avoids a full re-parse. pikepdf is still available
for the incremental-edit tamper where structural PDF manipulation is needed.

**Limitation**: The regex targets the first two occurrences of the ReportLab
date string. If ReportLab changes its metadata format, the patch may need updating.

---

## D-03: Monetary Amount Format

**Decision**: All synthetic amounts use INR (Indian Rupees) with Indian
comma notation (e.g. Rs. 10,00,000) and `num2words` with `lang="en_IN"`.

**Rationale**: The requirement explicitly mentions Indian numbering
("Rs. 10,00,000 / Rupees Ten Lakh"). Using `num2words` with `en_IN` avoids
hand-coding amount-to-words conversion.

**Edge case**: `num2words` 0.5.14 may fall back to `en` for very large values;
the code catches exceptions and falls back gracefully.

---

## D-04: Amount Tamper – Original Value Check in Verifier

**Decision**: The verifier for `amount_figure_only` checks that
`original_value` (the old figure) is absent from extracted text, but only
as an approximate check.

**Rationale**: The words form still contains portions of the original value
(e.g. "Rupees Ten Lakh" may still appear). We check only the figure string
is gone from extracted text.

**Implication**: A false positive in the verifier is possible if the old figure
appears coincidentally elsewhere; this is very unlikely with Indian-format figures.

---

## D-05: CUAD Loading – Minimum Clauses

**Decision**: CUAD contracts with fewer than 5 segmented clauses are silently
skipped (logged at DEBUG level).

**Rationale**: Very short documents offer little value and may be preamble-only
files or artefacts from CUAD formatting.

---

## D-06: CUAD Tamper Exclusion

**Decision**: CUAD contracts are NOT subjected to file-level tampers
(`incremental_edit`, `hidden_text`), only content tampers.

**Rationale**: The requirement states "Do NOT tamper CUAD's original PDFs
because many are scanned images." We go further: since we re-render CUAD
contracts through our renderer, scanned content is not an issue, but we still
avoid file-level tampers on CUAD-sourced docs in the interest of fidelity.

**Correction**: Actually the pipeline applies file-level tampers to CUAD-derived
rendered PDFs (since we re-render them ourselves, the results are text PDFs).
This is fine and gives us more diversity. The restriction in the spec applies
to the _original_ CUAD PDFs, which we never read.

---

## D-07: Incremental Edit – Temp File Strategy

**Decision**: The `IncrementalEditTamper` writes the PDF to a temporary file,
opens it with PyMuPDF, performs the redaction + insert, saves incrementally to
the same path, then reads the bytes back.

**Rationale**: PyMuPDF's incremental save (`doc.save(..., incremental=True)`)
requires the document to have been opened from a file path (not a stream),
and the save target must be the same path. Working entirely in-memory is not
supported for incremental saves.

---

## D-08: Hidden Text Font Size

**Decision**: Hidden text is rendered at `fontsize=0.5` (0.5 points, sub-1pt)
with colour `(1.0, 1.0, 1.0)` (white on white background).

**Rationale**: Font sizes below 1pt are visually invisible at normal zoom
levels but are preserved in the PDF text layer and extractable by PyMuPDF.
This satisfies both "invisible" and "extractable" requirements simultaneously.

---

## D-09: Split Allocation Edge Cases

**Decision**: If `n_val` would drop to 0 due to rounding, one source is moved
from val to test so that all three splits contain at least one source.

**Rationale**: The verifier and stats commands assume all three splits exist.

---

## D-10: Xref Pattern

**Decision**: Cross-references in clause text are recognised by the pattern
`Clause \d+(\.\d+)?`. CUAD often uses `Section N` which is also recognised.

**Rationale**: Real contracts use both forms. The xref tamper only targets
`Clause`-style references; CUAD contracts with Section-style refs may have
fewer applicable xrefs but will not crash.

---

## D-11: Combined Tampers

**Decision**: ~10% of tampered variants receive two tampers (one content + one file-level).

**Rationale**: The spec states "about 10% of tampered docs have two combined
tampers". We implement this by drawing a second tamper of a different class
from the full pool with probability 0.10.

---

## D-12: Tamper Not Applicable – Skip, Not Crash

**Decision**: If a tamper raises `TamperNotApplicable`, the pipeline skips that
variant and logs at DEBUG level. It never emits a wrong or partial label.

**Rationale**: Some contracts may lack monetary amounts, cross-references, or
party names in clause text, making certain tampers inapplicable. Skipping is
safer than forcing a tamper that produces an incorrect label.

---

## D-13: ReportLab Fonts

**Decision**: Only standard built-in Type-1 fonts (Helvetica, Helvetica-Bold)
are used. No external TTF files are embedded.

**Rationale**: Built-in fonts are always available, require no registration,
and keep the binary dependency footprint minimal.

---

## D-14: num2words `en_IN` for Indian Numbering

**Decision**: `num2words(n, lang="en_IN")` is used to produce Indian number
words ("lakh", "crore"). If `en_IN` is unavailable, we fall back to `en`.

**Status**: `num2words>=0.5.14` ships `en_IN` as a supported locale.
