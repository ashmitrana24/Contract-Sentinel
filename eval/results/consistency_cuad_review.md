# CUAD Clean Document Consistency Review

This document reviews every CUAD-derived clean contract that triggered a consistency finding
of severity MEDIUM or higher, along with misses and false positives per tamper type.

## Summary

- **Train/Val Clean CUAD FPs**: 3 / 28 (10.7%)
- **Held-out Test Clean CUAD FPs**: 0 / 2 (0.0%)

## Detailed CUAD Clean Findings (Medium+ Severity)

### Document: `cuad_AzulSa_20170303_F-1A_EX-10.3_9943903_EX-10.3_Maintenance Agreement2_clean`
- **Finding Type**: `dangling_reference`
  - **Severity**: `medium`
  - **Page**: 1
  - **Clause Ref**: 2
  - **Evidence**: `Target '12' referenced in: ] (ii) Any other provision of Clause 12 shall remain in full force an`
  - **Explanation**: Cross-reference to '12' in clause(s) 2 cannot be resolved: no clause with identifier '12' exists in the contract.

### Document: `cuad_BICYCLETHERAPEUTICSPLC_03_10_2020-EX-10.11-SERVICE AGREEMENT_clean`
- **Finding Type**: `dangling_reference`
  - **Severity**: `medium`
  - **Page**: 6
  - **Clause Ref**: 11.1
  - **Evidence**: `Target '13' referenced in:  including
those set forth in paragraphs 13 - 15, and (in the case of the sepa (and 2 other occurrence(s))`
  - **Explanation**: Cross-reference to '13' in clause(s) 11.1, 14.1 cannot be resolved: no clause with identifier '13' exists in the contract (referenced 3 times).

### Document: `cuad_FuseMedicalInc_20190321_10-K_EX-10.43_11575454_EX-10.43_Distributor Agreement_clean`
- **Finding Type**: `figure_words_mismatch`
  - **Severity**: `medium`
  - **Page**: 3
  - **Clause Ref**: Schedule 4
  - **Evidence**: `thirty (45) in snippet: 's within thirty (45) days of the date of'`
  - **Explanation**: The amount in words (thirty = 30) does not match the amount in figures (45 = 45) in clause Schedule 4.

## Misses by Tamper Type (up to 5 per type)

### Split: Train/Val
#### `amount_figure_only` (Miss count: 0)
No misses recorded (100% recall).

#### `date_shift` (Miss count: 0)
No misses recorded (100% recall).

#### `party_swap` (Miss count: 5)
- Document `synth_0027_v0`: details: [{'tamper_type': 'party_swap', 'page': None, 'clause_id': '4', 'original_value': 'Nexus Group Corp.', 'tampered_value': 'Nexus', 'subtype': 'name_substitution', 'dangling_xrefs': [], 'extra': {}}]
- Document `synth_0028_v0`: details: [{'tamper_type': 'party_swap', 'page': None, 'clause_id': '9', 'original_value': 'Nexus Solutions Ltd.', 'tampered_value': 'NSL', 'subtype': 'name_substitution', 'dangling_xrefs': [], 'extra': {}}]
- Document `synth_0029_v0`: details: [{'tamper_type': 'party_swap', 'page': None, 'clause_id': '15', 'original_value': 'Meridian Services LLP', 'tampered_value': 'Meridian', 'subtype': 'name_substitution', 'dangling_xrefs': [], 'extra': {}}]
- Document `cuad_AimmuneTherapeuticsInc_20200205_8-K_EX-10.3_11967170_EX-10.3_Development Agreement_v0`: details: [{'tamper_type': 'party_swap', 'page': None, 'clause_id': '15.13', 'original_value': 'XENCOR, INC.', 'tampered_value': 'XENCOR, Holdings Inc.', 'subtype': 'name_substitution', 'dangling_xrefs': [], 'extra': {}}]
- Document `cuad_ANIXABIOSCIENCESINC_06_09_2020-EX-10.1-COLLABORATION AGREEMENT_v0`: details: [{'tamper_type': 'party_swap', 'page': None, 'clause_id': '1', 'original_value': 'its biological activity', 'tampered_value': 'its Group Corp.', 'subtype': 'name_substitution', 'dangling_xrefs': [], 'extra': {}}]

#### `clause_delete` (Miss count: 5)
- Document `synth_0019_v0`: details: [{'tamper_type': 'clause_delete', 'page': None, 'clause_id': '10', 'original_value': 'Governing Law and Jurisdiction', 'tampered_value': '<deleted>', 'subtype': 'clause_removed', 'dangling_xrefs': [], 'extra': {}}]
- Document `synth_0019_v1`: details: [{'tamper_type': 'clause_delete', 'page': None, 'clause_id': '2', 'original_value': 'Severability', 'tampered_value': '<deleted>', 'subtype': 'clause_removed', 'dangling_xrefs': [], 'extra': {}}]
- Document `synth_0034_v2`: details: [{'tamper_type': 'clause_delete', 'page': None, 'clause_id': '8', 'original_value': 'Dispute Resolution', 'tampered_value': '<deleted>', 'subtype': 'clause_removed', 'dangling_xrefs': [], 'extra': {}}]
- Document `synth_0035_v1`: details: [{'tamper_type': 'clause_delete', 'page': None, 'clause_id': '2', 'original_value': 'Audit Rights', 'tampered_value': '<deleted>', 'subtype': 'clause_removed', 'dangling_xrefs': [], 'extra': {}}]
- Document `synth_0042_v0`: details: [{'tamper_type': 'clause_delete', 'page': None, 'clause_id': '5', 'original_value': 'Data Protection', 'tampered_value': '<deleted>', 'subtype': 'clause_removed', 'dangling_xrefs': [], 'extra': {}}, {'tamper_type': 'amount_both', 'page': None, 'clause_id': '4', 'original_value': 'Rs. 1,64,00,000 (Rupees One crore, sixty-four lakh Only)', 'tampered_value': 'Rs. 69,00,000 (Rupees Sixty-nine lakh Only)', 'subtype': 'consistent_change', 'dangling_xrefs': [], 'extra': {}}]

#### `xref_break` (Miss count: 0)
No misses recorded (100% recall).

### Split: Held-out Test
#### `amount_figure_only` (Miss count: 0)
No misses recorded (100% recall).

#### `date_shift` (Miss count: 0)
No misses recorded (100% recall).

#### `party_swap` (Miss count: 0)
No misses recorded (100% recall).

#### `clause_delete` (Miss count: 5)
- Document `synth_0003_v0`: details: [{'tamper_type': 'clause_delete', 'page': None, 'clause_id': '2', 'original_value': 'Force Majeure', 'tampered_value': '<deleted>', 'subtype': 'clause_removed', 'dangling_xrefs': [], 'extra': {}}]
- Document `synth_0056_v0`: details: [{'tamper_type': 'clause_delete', 'page': None, 'clause_id': '7', 'original_value': 'Payment Terms', 'tampered_value': '<deleted>', 'subtype': 'clause_removed', 'dangling_xrefs': [], 'extra': {}}]
- Document `synth_0096_v2`: details: [{'tamper_type': 'clause_delete', 'page': None, 'clause_id': '3', 'original_value': 'Limitation of Liability', 'tampered_value': '<deleted>', 'subtype': 'clause_removed', 'dangling_xrefs': [], 'extra': {}}]
- Document `synth_0099_v1`: details: [{'tamper_type': 'clause_delete', 'page': None, 'clause_id': '8', 'original_value': 'Entire Agreement', 'tampered_value': '<deleted>', 'subtype': 'clause_removed', 'dangling_xrefs': [], 'extra': {}}]
- Document `synth_0101_v0`: details: [{'tamper_type': 'clause_delete', 'page': None, 'clause_id': '13', 'original_value': 'Assignment', 'tampered_value': '<deleted>', 'subtype': 'clause_removed', 'dangling_xrefs': [], 'extra': {}}]

#### `xref_break` (Miss count: 0)
No misses recorded (100% recall).
