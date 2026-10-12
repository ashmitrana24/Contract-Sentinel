# Consistency Evaluation: Final Review on Unseen ContractNLI Corpus

This document reports the final, single-pass evaluation of Module 4 (Contract Consistency Engine) on a completely fresh, previously unseen public contract corpus: the 123 held-out test Non-Disclosure Agreements (NDAs) from **ContractNLI**.

In strict accordance with the evaluation protocol, this evaluation was executed **ONCE** with **ZERO TUNING** on this corpus.

---

## 1. Corpus Provenance & Licensing

- **Dataset**: ContractNLI (Document-level Natural Language Inference for Contracts)
- **Reference**: Koreeda & Manning, *ContractNLI: A Dataset for Document-level Natural Language Inference for Contracts*, Findings of EMNLP 2021.
- **Repository**: Hugging Face `kiddothe2b/contract-nli` (`contract_nli_long.zip` / `contract_nli_long.jsonl`)
- **License**: Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International (**CC BY-NC-SA 4.0**)
- **Corpus Characteristics**: Real-world commercial Non-Disclosure Agreements (NDAs) sourced from SEC EDGAR and public corporate repositories.
- **Evaluation Split**: Held-out `test` split (`subset == 'test'`), comprising 123 complete contracts. None of these contracts were used during prompt design, regex development, or diagnostic tuning.

---

## 2. Evaluation Results Summary

| Metric | Target | Result | Status |
| :--- | :--- | :--- | :--- |
| **Documents Analyzed** | $\ge 100$ | **123** | MET |
| **Flagged at MEDIUM or Higher** | - | **4** (3.25%) | - |
| **Genuine Inconsistencies Found** | - | **1** (0.81%) | - |
| **False Alarms** | - | **3** (2.44%) | - |
| **False Alarm Rate** | $\le 5.0\%$ | **2.44%** (3/123) | **MET** |

---

## 3. Detailed Audit of Flagged Documents

All 4 flagged documents were audited manually against the full contract text.

### Document 1: `ContractNLI_Test_056` — GENUINE INCONSISTENCY
- **Title / First Line**: `MUTUAL NON-DISCLOSURE AGREEMENT`
- **Finding Type**: `figure_words_mismatch` (Severity: `MEDIUM`)
- **Clause**: Clause `4`
- **Evidence Sentence**:
  > *"This Agreement and the obligations concerning confidentiality shall expire five (2) years from the date hereof, unless terminated earlier..."*
- **Explanation**: The amount written in words (`five` = 5) directly conflicts with the parenthetical figure (`(2)` = 2).
- **Judgement**: **GENUINE DRAFTING DEFECT**. This is a classic human drafter copy-paste discrepancy in a real commercial agreement.

---

### Document 2: `ContractNLI_Test_014` — FALSE ALARM
- **Title / First Line**: `Please fill in your contact details, sign on the last page an fax this document`
- **Finding Type**: `figure_words_mismatch` (Severity: `CRITICAL`)
- **Clause**: Clause `12`
- **Evidence Sentence**:
  > *"...liquidated damages in the amount of €10 000 (ten thousand Euro) for each such use or disclosure..."*
- **Explanation**: European formatting uses a space as a thousands separator (`10 000`). The number-word parser treated `000` adjacent to `(ten thousand Euro)` as a figure of 0 rather than 10,000.
- **Judgement**: **FALSE ALARM** (International space-separated thousands notation).

---

### Document 3: `ContractNLI_Test_054` — FALSE ALARM
- **Title / First Line**: `NON-DISCLOSURE AND NON-USE AGREEMENT (First Amendment, January 2008)`
- **Finding Type**: `dangling_reference` (Severity: `MEDIUM`)
- **Clause**: Clause `3` and Clause `4`
- **Evidence Sentences**:
  > Clause 3: *"...Safety Data Sheets as defined in Article 31 of REACH, (ii) relevant exposure scenarios..."*
  > Clause 4: *"...Member State Committee in compliance with Article 119 of REACH on electronic public access..."*
- **Explanation**: The agreement cites the European Union chemical regulation (EC Regulation No 1907/2006, commonly known as "REACH"). Because "REACH" is an EU regulation acronym not present in the US-centric statutory keyword list (`Code`, `Act`, `Rule`, `Securities`, `Exchange`), the detector attempted to resolve Articles 31 and 119 as contract clauses.
- **Judgement**: **FALSE ALARM** (External EU regulatory citation).

---

### Document 4: `ContractNLI_Test_055` — FALSE ALARM
- **Title / First Line**: `LAST MAN STANDS INTERNATIONAL NON-DISCLOSURE AGREEMENT`
- **Finding Type**: `duplicate_clause_number` (Severity: `MEDIUM`)
- **Clause**: Clause `1`
- **Evidence Sentences**:
  > Preamble Item (1): *"1. Last Man Stands, (the "Disclosing Party"); and"*
  > Body Clause 1: *"1. In consideration of the disclosure of Proprietary Information by the Disclosing Party, the Receiving Party hereby agrees..."*
- **Explanation**: The contract preamble enumerated party names using numbered paragraphs (`1. Last Man Stands...`, `2. [Receiving Party]...`), and then restarted numbering at `1.` for the substantive terms. The segmenter identified both as Clause 1.
- **Judgement**: **FALSE ALARM** (Preamble list enumeration colliding with operative clause numbering).

---

## 4. Benchmark Comparison: CUAD 310 Contracts (Optimistic Post-Tuning Baseline)

For transparency and per user specification, the performance on the 310 CUAD v1 unseen contracts is recorded below. Note that this set was used to guide diagnostic improvements during development and is therefore labeled as **optimistic**:

- **Corpus**: 310 commercial agreements from CUAD v1 (SEC EDGAR Exhibit-10 filings).
- **Status**: *After tuning on this set, optimistic*.
- **Documents Analyzed**: 310
- **Documents Flagged (MEDIUM+)**: 85 (27.42%)
  - Prior to Module 4 final round: 145 (46.77%)
  - Reduction achieved: 60 false alarm documents eliminated (-41.4% relative reduction)
- **Finding Breakdown**:
  - `dangling_reference`: 65 occurrences (reduced from 199+)
  - `party_name_variant`: 22 occurrences
  - `numbering_gap`: 15 occurrences
  - `figure_words_mismatch`: 13 occurrences
  - `date_order_conflict`: 10 occurrences
  - `duplicate_clause_number`: 7 occurrences
  - `term_length_conflict`: 1 occurrences

---

## 5. Conclusions

1. **Target Met on Unseen Corpus**: On the fresh ContractNLI corpus, the false alarm rate is **2.44%**, well below the $\le 5.0\%$ target.
2. **Real Tamper / Defect Discovery**: The consistency engine successfully discovered a genuine drafting defect (`five (2) years`) in a real-world mutual NDA without human intervention.
3. **Generalization Gap**: While clean commercial NDAs exhibit a very low false alarm rate (2.44%), complex SEC filings (CUAD 310) show a higher flag rate (27.42% optimistic) due to heavy boilerplate, OCR noise in historical filings, and complex schedule/exhibit structures.
