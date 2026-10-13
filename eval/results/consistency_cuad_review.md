# CUAD Clean Document Consistency Review

This document reviews every CUAD-derived clean contract that triggered a consistency finding
of severity MEDIUM or higher, along with misses and false positives per tamper type.

## Summary

- **Train/Val Clean CUAD FPs**: 14 / 28 (50.0%)
- **Held-out Test Clean CUAD FPs**: 0 / 2 (0.0%)

## Detailed CUAD Clean Findings (Medium+ Severity)

### Document: `cuad_AimmuneTherapeuticsInc_20200205_8-K_EX-10.3_11967170_EX-10.3_Development Agreement_clean`
- **Finding Type**: `numbering_gap`
  - **Severity**: `high`
  - **Page**: 1
  - **Clause Ref**: 1
  - **Evidence**: `Missing clause 1 between clause 0 and clause 2 (cross-referenced by dangling reference to '1')`
  - **Explanation**: Clause numbering gap: clause 1 is missing between clause 0 and clause 2, and a cross-reference specifically points to missing clause 1.

### Document: `cuad_AMBASSADOREYEWEARGROUPINC_11_17_1997-EX-10.28-ENDORSEMENT AGREEMENT_clean`
- **Finding Type**: `dangling_reference`
  - **Severity**: `medium`
  - **Page**: 8
  - **Clause Ref**: 21
  - **Evidence**: `Target '22' referenced in: eement, except as provided in paragraphs 8 and 22. 23. Additional Endorsers. If`
  - **Explanation**: Cross-reference to '22' in clause(s) 21 cannot be resolved: no clause with identifier '22' exists in the contract.
- **Finding Type**: `dangling_reference`
  - **Severity**: `medium`
  - **Page**: 8
  - **Clause Ref**: 21
  - **Evidence**: `Target '14' referenced in: edial and other provisions of paragraph 14 of this Agreement.`
  - **Explanation**: Cross-reference to '14' in clause(s) 21 cannot be resolved: no clause with identifier '14' exists in the contract.

### Document: `cuad_AzulSa_20170303_F-1A_EX-10.3_9943903_EX-10.3_Maintenance Agreement1_clean`
- **Finding Type**: `dangling_reference`
  - **Severity**: `medium`
  - **Page**: 1
  - **Clause Ref**: 0
  - **Evidence**: `Target '20' referenced in: obligation; 23.3.5 Subject to Clause 20 ("Confidentiality"), it will `
  - **Explanation**: Cross-reference to '20' in clause(s) 0 cannot be resolved: no clause with identifier '20' exists in the contract.

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
  - **Page**: 1
  - **Clause Ref**: 0
  - **Evidence**: `Target '13' referenced in:  including
those set forth in paragraphs 13 - 15, and (in the case of the sepa (and 2 other occurrence(s))`
  - **Explanation**: Cross-reference to '13' in clause(s) 0 cannot be resolved: no clause with identifier '13' exists in the contract (referenced 3 times).

### Document: `cuad_CardlyticsInc_20180112_S-1_EX-10.16_11002987_EX-10.16_Maintenance Agreement1_clean`
- **Finding Type**: `dangling_reference`
  - **Severity**: `medium`
  - **Page**: 6
  - **Clause Ref**: 2.1
  - **Evidence**: `Target 'B' referenced in: er as outlined
in Schedule A, Section B. Upon delivery, Bank of Ameri`
  - **Explanation**: Cross-reference to 'B' in clause(s) 2.1 cannot be resolved: no clause with identifier 'B' exists in the contract.

### Document: `cuad_CYBERIANOUTPOSTINC_07_09_1998-EX-10.13-PROMOTION AGREEMENT_clean`
- **Finding Type**: `numbering_gap`
  - **Severity**: `high`
  - **Page**: 1
  - **Clause Ref**: 4
  - **Evidence**: `Missing clause 4 between clause 3 and clause 5 (cross-referenced by dangling reference to '4')`
  - **Explanation**: Clause numbering gap: clause 4 is missing between clause 3 and clause 5, and a cross-reference specifically points to missing clause 4.

### Document: `cuad_DovaPharmaceuticalsInc_20181108_10-Q_EX-10.2_11414857_EX-10.2_Promotion Agreement_clean`
- **Finding Type**: `numbering_gap`
  - **Severity**: `high`
  - **Page**: 1
  - **Clause Ref**: 2
  - **Evidence**: `Missing clause 2 between clause 1 and clause 3 (cross-referenced by dangling reference to '2')`
  - **Explanation**: Clause numbering gap: clause 2 is missing between clause 1 and clause 3, and a cross-reference specifically points to missing clause 2.

### Document: `cuad_ELANDIAINTERNATIONALINC_04_25_2007-EX-10.21-Outsourcing Agreement_clean`
- **Finding Type**: `dangling_reference`
  - **Severity**: `medium`
  - **Page**: 1
  - **Clause Ref**: 0
  - **Evidence**: `Target '14' referenced in: 
generally in accordance with section 14 . 1.5 Hours of Support The no (and 1 other occurrence(s))`
  - **Explanation**: Cross-reference to '14' in clause(s) 0, 14.1 cannot be resolved: no clause with identifier '14' exists in the contract (referenced 2 times).

### Document: `cuad_ENTERTAINMENTGAMINGASIAINC_02_15_2005-EX-10.5-DISTRIBUTOR AGREEMENT_clean`
- **Finding Type**: `dangling_reference`
  - **Severity**: `medium`
  - **Page**: 4
  - **Clause Ref**: 3
  - **Evidence**: `Target '2' referenced in: right and license provided in Section 2 of this Agreement, Distributo`
  - **Explanation**: Cross-reference to '2' in clause(s) 3 cannot be resolved: no clause with identifier '2' exists in the contract.
- **Finding Type**: `dangling_reference`
  - **Severity**: `medium`
  - **Page**: 4
  - **Clause Ref**: 3
  - **Evidence**: `Target '5' referenced in: h the parameters set forth in Sections 5 and 6 of this Agreement; 3.2.
Distr`
  - **Explanation**: Cross-reference to '5' in clause(s) 3 cannot be resolved: no clause with identifier '5' exists in the contract.
- **Finding Type**: `dangling_reference`
  - **Severity**: `medium`
  - **Page**: 4
  - **Clause Ref**: 3
  - **Evidence**: `Target '6' referenced in: h the parameters set forth in Sections 5 and 6 of this Agreement; 3.2.
Distr`
  - **Explanation**: Cross-reference to '6' in clause(s) 3 cannot be resolved: no clause with identifier '6' exists in the contract.
- **Finding Type**: `numbering_gap`
  - **Severity**: `high`
  - **Page**: 2
  - **Clause Ref**: 2
  - **Evidence**: `Missing clause 2 between clause 1 and clause 3 (cross-referenced by dangling reference to '2')`
  - **Explanation**: Clause numbering gap: clause 2 is missing between clause 1 and clause 3, and a cross-reference specifically points to missing clause 2.
- **Finding Type**: `numbering_gap`
  - **Severity**: `high`
  - **Page**: 6
  - **Clause Ref**: 5
  - **Evidence**: `Missing clause 5 between clause 4 and clause 6 (cross-referenced by dangling reference to '5')`
  - **Explanation**: Clause numbering gap: clause 5 is missing between clause 4 and clause 6, and a cross-reference specifically points to missing clause 5.
- **Finding Type**: `numbering_gap`
  - **Severity**: `high`
  - **Page**: 1
  - **Clause Ref**: 6
  - **Evidence**: `Missing clause 6 between clause 5 and clause 7 (cross-referenced by dangling reference to '6')`
  - **Explanation**: Clause numbering gap: clause 6 is missing between clause 5 and clause 7, and a cross-reference specifically points to missing clause 6.

### Document: `cuad_FuseMedicalInc_20190321_10-K_EX-10.43_11575454_EX-10.43_Distributor Agreement_clean`
- **Finding Type**: `figure_words_mismatch`
  - **Severity**: `medium`
  - **Page**: 3
  - **Clause Ref**: Schedule 4
  - **Evidence**: `thirty (45) in snippet: 's within thirty (45) days of the date of'`
  - **Explanation**: The amount in words (thirty = 30) does not match the amount in figures (45 = 45) in clause Schedule 4.
- **Finding Type**: `party_name_variant`
  - **Severity**: `medium`
  - **Page**: 9
  - **Clause Ref**: 24.1
  - **Evidence**: `Found 'CPM Medical LLC' (expected party 'CPM Medical Consultants LLC Source: FUSE') in:  Director
Name (please print) SIGNED by CPM Medical LLC ) ) ) ) ) Director/Secretary Name (plea`
  - **Explanation**: Party name variant 'CPM Medical LLC' differs from defined party 'CPM Medical Consultants LLC Source: FUSE' (similarity 100.0%).

### Document: `cuad_GRANTIERRAENERGYINC_05_07_2012-EX-10.6-TRANSPORTATION CONTRACT_clean`
- **Finding Type**: `duplicate_clause_number`
  - **Severity**: `medium`
  - **Page**: 3
  - **Clause Ref**: 3
  - **Evidence**: `Clause 3 appears 2 times: 'VOLUMETRIC COMPENSATION FOR QUALITY - CVC' (page 1), 'Crude Oil delivered by the Pipeline' (page 3)`
  - **Explanation**: Duplicate clause number: clause 3 is used multiple times in the document (2 occurrences).

### Document: `cuad_GSVINC_05_15_1998-EX-10-SPONSORSHIP AGREEMENT_clean`
- **Finding Type**: `dangling_reference`
  - **Severity**: `medium`
  - **Page**: 5
  - **Clause Ref**: 5
  - **Evidence**: `Target '7' referenced in: his Agreement as described in Sections 7(a) and 7(b). Should
these results differ  (and 3 other occurrence(s))`
  - **Explanation**: Cross-reference to '7' in clause(s) 5 cannot be resolved: no clause with identifier '7' exists in the contract (referenced 4 times).
- **Finding Type**: `numbering_gap`
  - **Severity**: `high`
  - **Page**: 1
  - **Clause Ref**: 7
  - **Evidence**: `Missing clause 7 between clause 6 and clause 8 (cross-referenced by dangling reference to '7')`
  - **Explanation**: Clause numbering gap: clause 7 is missing between clause 6 and clause 8, and a cross-reference specifically points to missing clause 7.

### Document: `cuad_HarpoonTherapeuticsInc_20200312_10-K_EX-10.18_12051356_EX-10.18_Development Agreement_clean`
- **Finding Type**: `party_name_variant`
  - **Severity**: `medium`
  - **Page**: 43
  - **Clause Ref**: Schedule 10.13.8.1
  - **Evidence**: `Found 'AbbVie Inc' (expected party 'ABBVIE BIOTECHNOLOGY LTD Dated') in: (which shall not
constitute notice) to: AbbVie Inc. 1 North Waukegan Road North Chicago, I`
  - **Explanation**: Party name variant 'AbbVie Inc' differs from defined party 'ABBVIE BIOTECHNOLOGY LTD Dated' (similarity 100.0%).
- **Finding Type**: `numbering_gap`
  - **Severity**: `high`
  - **Page**: 1
  - **Clause Ref**: 1
  - **Evidence**: `Missing clause 1 between clause 0 and clause 2 (cross-referenced by dangling reference to '1')`
  - **Explanation**: Clause numbering gap: clause 1 is missing between clause 0 and clause 2, and a cross-reference specifically points to missing clause 1.

## Misses by Tamper Type (up to 5 per type)

### Split: Train/Val
#### `amount_figure_only` (Miss count: 0)
No misses recorded (100% recall).

#### `date_shift` (Miss count: 0)
No misses recorded (100% recall).

#### `party_swap` (Miss count: 4)
- Document `synth_0027_v0`: details: [{'tamper_type': 'party_swap', 'page': None, 'clause_id': '4', 'original_value': 'Nexus Group Corp.', 'tampered_value': 'Nexus', 'subtype': 'name_substitution', 'dangling_xrefs': [], 'extra': {}}]
- Document `synth_0028_v0`: details: [{'tamper_type': 'party_swap', 'page': None, 'clause_id': '9', 'original_value': 'Nexus Solutions Ltd.', 'tampered_value': 'NSL', 'subtype': 'name_substitution', 'dangling_xrefs': [], 'extra': {}}]
- Document `synth_0029_v0`: details: [{'tamper_type': 'party_swap', 'page': None, 'clause_id': '15', 'original_value': 'Meridian Services LLP', 'tampered_value': 'Meridian', 'subtype': 'name_substitution', 'dangling_xrefs': [], 'extra': {}}]
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
