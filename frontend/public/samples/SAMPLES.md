# Sample Contracts

All contract documents provided in this directory are **100% synthetically generated** using ClauseGuard's synthetic contract generator (`datagen/`).

**None of these files contain proprietary, confidential, or real-world data, and none are derived from the CUAD corpus.**

## Included Sample Documents

1. **Clean Sample (`clean_consulting_agreement.pdf` / `synth_0000_clean.pdf`)**:
   - Standard consulting agreement generated with consistent clauses, valid cross-references, matching dates, and unaltered PDF structure.
   - Expected Risk Band: **Low** (score: 0).

2. **Amount and Date Discrepancy Sample (`amount_and_date_discrepancy.pdf` / `synth_0014_v1.pdf`)**:
   - Synthetically perturbed contract containing figure-to-words mismatch (e.g., numeral amount differing from written word amount) and chronological order conflicts between effective and termination dates.
   - Expected Risk Band: **Medium / High** with finding title: *"Amount in words doesn't match the figure"*.

3. **Edited PDF Sample (`post_creation_edited_contract.pdf` / `synth_0000_v1.pdf`)**:
   - Synthetically modified contract with post-creation revisions (incremental update altering dates/amounts after initial save) and hidden text.
   - Expected Risk Band: **High** with finding: *"Post-creation revision or alteration"*.
