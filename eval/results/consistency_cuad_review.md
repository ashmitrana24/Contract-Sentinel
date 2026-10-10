# CUAD Clean Document Consistency Review

This document reviews every CUAD-derived clean contract that triggered a consistency finding
of severity MEDIUM or higher, along with misses and false positives per tamper type.

## Summary

- **Train/Val Clean CUAD FPs**: 2 / 16 (12.5%)
- **Held-out Test Clean CUAD FPs**: 0 / 6 (0.0%)

## Detailed CUAD Clean Findings (Medium+ Severity)

### Document: `cuad_AtnInternationalInc_20191108_10-Q_EX-10.1_11878541_EX-10.1_Maintenance Agreement_clean`
- **Finding Type**: `dangling_reference`
  - **Severity**: `medium`
  - **Page**: 39
  - **Clause Ref**: 3.48
  - **Evidence**: `Target '222' referenced in: PNI restrictions contained in Section 222. Accordingly, Vendor
shall: P`
  - **Explanation**: Cross-reference to '222' in clause(s) 3.48 cannot be resolved: no clause with identifier '222' exists in the contract.

### Document: `cuad_DovaPharmaceuticalsInc_20181108_10-Q_EX-10.2_11414857_EX-10.2_Promotion Agreement_clean`
- **Finding Type**: `dangling_reference`
  - **Severity**: `medium`
  - **Page**: 26
  - **Clause Ref**: 12.5
  - **Evidence**: `Target '2.3' referenced in: ion or termination, including
Sections 2.3, , 4.4.2, 5.7, 5.9, 6.3.6, 6.`
  - **Explanation**: Cross-reference to '2.3' in clause(s) 12.5 cannot be resolved: no clause with identifier '2.3' exists in the contract.

## Misses by Tamper Type (up to 5 per type)

### Split: Train/Val
#### `amount_figure_only` (Miss count: 1)
- Document `synth_0041_v1`: details: [{'tamper_type': 'amount_figure_only', 'page': None, 'clause_id': '11', 'original_value': 'Rs. 37,00,000', 'tampered_value': 'Rs. 11,00,000', 'subtype': 'figure_words_mismatch', 'dangling_xrefs': [], 'extra': {}}, {'tamper_type': 'amount_both', 'page': None, 'clause_id': '11', 'original_value': 'Rs. 11,00,000 (Rupees Thirty-seven lakh Only)', 'tampered_value': 'Rs. 35,00,000 (Rupees Thirty-five lakh Only)', 'subtype': 'consistent_change', 'dangling_xrefs': [], 'extra': {}}]

#### `date_shift` (Miss count: 0)
No misses recorded (100% recall).

#### `party_swap` (Miss count: 1)
- Document `cuad_ADAMSGOLFINC_03_21_2005-EX-10.17-ENDORSEMENT AGREEMENT_v1`: details: [{'tamper_type': 'party_swap', 'page': None, 'clause_id': '11', 'original_value': 'ADAMS GOLF', 'tampered_value': 'ADAMS Group Corp.', 'subtype': 'name_substitution', 'dangling_xrefs': [], 'extra': {}}]

#### `clause_delete` (Miss count: 5)
- Document `synth_0010_v2`: details: [{'tamper_type': 'clause_delete', 'page': None, 'clause_id': '7', 'original_value': 'Force Majeure', 'tampered_value': '<deleted>', 'subtype': 'clause_removed', 'dangling_xrefs': [], 'extra': {}}]
- Document `synth_0011_v2`: details: [{'tamper_type': 'clause_delete', 'page': None, 'clause_id': '11', 'original_value': 'Termination', 'tampered_value': '<deleted>', 'subtype': 'clause_removed', 'dangling_xrefs': [], 'extra': {}}, {'tamper_type': 'clause_insert', 'page': None, 'clause_id': '3.99', 'original_value': '<none>', 'tampered_value': 'Penalty Clause', 'subtype': 'risky_clause_inserted', 'dangling_xrefs': [], 'extra': {}}]
- Document `synth_0012_v0`: details: [{'tamper_type': 'clause_delete', 'page': None, 'clause_id': '3', 'original_value': 'Entire Agreement', 'tampered_value': '<deleted>', 'subtype': 'clause_removed', 'dangling_xrefs': [], 'extra': {}}]
- Document `synth_0015_v1`: details: [{'tamper_type': 'clause_delete', 'page': None, 'clause_id': '14', 'original_value': 'Insurance', 'tampered_value': '<deleted>', 'subtype': 'clause_removed', 'dangling_xrefs': [], 'extra': {}}, {'tamper_type': 'clause_insert', 'page': None, 'clause_id': '3.99', 'original_value': '<none>', 'tampered_value': 'Governing Law Overriding Clause', 'subtype': 'risky_clause_inserted', 'dangling_xrefs': [], 'extra': {}}]
- Document `synth_0022_v1`: details: [{'tamper_type': 'clause_delete', 'page': None, 'clause_id': '13', 'original_value': 'Representations and Warranties', 'tampered_value': '<deleted>', 'subtype': 'clause_removed', 'dangling_xrefs': [], 'extra': {}}]

#### `xref_break` (Miss count: 1)
- Document `synth_0063_v0`: details: [{'tamper_type': 'xref_break', 'page': None, 'clause_id': '10', 'original_value': 'Clause 9', 'tampered_value': 'Clause 639', 'subtype': 'ghost_reference', 'dangling_xrefs': [], 'extra': {}}]

### Split: Held-out Test
#### `amount_figure_only` (Miss count: 0)
No misses recorded (100% recall).

#### `date_shift` (Miss count: 0)
No misses recorded (100% recall).

#### `party_swap` (Miss count: 1)
- Document `cuad_BONTONSTORESINC_04_20_2018-EX-99.3-AGENCY AGREEMENT_v1`: details: [{'tamper_type': 'party_swap', 'page': None, 'clause_id': '14.2', 'original_value': 'The Bon-Ton Stores, Inc.', 'tampered_value': 'The Group Corp.', 'subtype': 'name_substitution', 'dangling_xrefs': [], 'extra': {}}]

#### `clause_delete` (Miss count: 5)
- Document `synth_0009_v1`: details: [{'tamper_type': 'clause_delete', 'page': None, 'clause_id': '4', 'original_value': 'Insurance', 'tampered_value': '<deleted>', 'subtype': 'clause_removed', 'dangling_xrefs': [], 'extra': {}}]
- Document `synth_0013_v0`: details: [{'tamper_type': 'clause_delete', 'page': None, 'clause_id': '3', 'original_value': 'Term', 'tampered_value': '<deleted>', 'subtype': 'clause_removed', 'dangling_xrefs': [], 'extra': {}}]
- Document `synth_0013_v1`: details: [{'tamper_type': 'clause_delete', 'page': None, 'clause_id': '8', 'original_value': 'Amendments', 'tampered_value': '<deleted>', 'subtype': 'clause_removed', 'dangling_xrefs': [], 'extra': {}}]
- Document `synth_0032_v0`: details: [{'tamper_type': 'clause_delete', 'page': None, 'clause_id': '5', 'original_value': 'Termination', 'tampered_value': '<deleted>', 'subtype': 'clause_removed', 'dangling_xrefs': [], 'extra': {}}]
- Document `synth_0053_v2`: details: [{'tamper_type': 'clause_delete', 'page': None, 'clause_id': '8', 'original_value': 'Confidentiality', 'tampered_value': '<deleted>', 'subtype': 'clause_removed', 'dangling_xrefs': [], 'extra': {}}]

#### `xref_break` (Miss count: 0)
No misses recorded (100% recall).
