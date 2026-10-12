# Consistency Evaluation: 310 Unseen CUAD v1 Contracts Review

This review audits all contracts flagged at MEDIUM or higher from the single, un-tuned evaluation run on the 310 unseen commercial contracts in CUAD v1.

- **Total Contracts Analyzed**: 310
- **Total Flagged (MEDIUM+)**: 62 (20.0%)

## Overall Summary & Rates

- **Contracts Analyzed**: 310
- **Total Flagged Contracts (MEDIUM+)**: 62 (20.0%)
- **Genuine Defect Contracts**: 7 (2.26%)
- **False Alarm Contracts**: 55 (17.74%) [Target: <= 5.0% -> MISSED]

---

## Contract-by-Contract Findings and Judgements

### 1. `ASHWORTHINC_01_29_1999-EX-10.(D)-PROMOTION AGREEMENT AND NANTZ COMMUNICATIONS, INC.` — FALSE ALARM
- **Finding**: `duplicate_clause_number` (MEDIUM) at clause `2`
  - *Evidence*: Clause 2 appears 2 times: 'TERM.  Except as otherwise provided herein, this Agreement shall commence      effective June 1, 1998, and shall continue for a term of three (3) years      expiring May 31, 2001 (the "Term").' (page 1), 'ASHWORTH APPAREL AND PRODUCTS.  Subject to any restrictions, contrac
  - *Judgement*: **False Alarm** (Annexure or exhibit repeating numbering section without distinct sub-header)

### 2. `LIGHTBRIDGECORP_11_23_2015-EX-10.26-STRATEGIC ALLIANCE AGREEMENT` — FALSE ALARM
- **Finding**: `dangling_reference` (MEDIUM) at clause `6.3`
  - *Evidence*: Target '11.1' referenced in: ess in the manner provided in Section 11.1.
  - *Judgement*: **False Alarm** (Complex commercial agreement cross-reference to external exhibit or schedule item)

### 3. `LinkPlusCorp_20050802_8-K_EX-10_3240252_EX-10_Affiliate Agreement` — GENUINE INCONSISTENCY IN CONTRACT
- **Finding**: `figure_words_mismatch` (CRITICAL) at clause `3.3.3`
  - *Evidence*: twenty-percent (25%) in snippet: 'b) twenty-percent (25%) of the Net Proceeds'
  - *Judgement*: **Genuine Inconsistency** (Literal drafting conflict between words and parenthetical figures in SEC filing)
- **Finding**: `figure_words_mismatch` (CRITICAL) at clause `3.3.4`
  - *Evidence*: twenty-percent (25%) in snippet: 'b) twenty-percent (25%) of the Net Proceeds'
  - *Judgement*: **Genuine Inconsistency** (Literal drafting conflict between words and parenthetical figures in SEC filing)
- **Finding**: `party_name_variant` (MEDIUM) at clause `7.5`
  - *Evidence*: Found 'LINK PLUS CORPORATION                       AXIOMETRIC, LLC' (expected party 'Link Plus Corporation') in: ic have executed this Agreement below.

LINK PLUS CORPORATION                       AXIOMETRIC, LLC

By:                                   
  - *Judgement*: **False Alarm** (Detector scope over-reach or document OCR layout artifact)

### 4. `AULAMERICANUNITTRUST_04_24_2020-EX-99.8.77-SERVICING AGREEMENT` — FALSE ALARM
- **Finding**: `party_name_variant` (MEDIUM) at clause `19`
  - *Evidence*: Found 'Title Nationwide Fund Management LLC' (expected party 'Nationwide Fund Management LLC') in: is received by Nationwide. Accepted by: Name Title Nationwide Fund Management LLC Date: Accepted and Agreed to: By: Name:
  - *Judgement*: **False Alarm** (Detector scope over-reach or document OCR layout artifact)

### 5. `VIOLINMEMORYINC_12_12_2012-EX-10.14-SPONSORSHIP AGREEMENT` — FALSE ALARM
- **Finding**: `dangling_reference` (MEDIUM) at clause `2`
  - *Evidence*: Target '13' referenced in: rdance with the provisions of Section 13(o) of this Agreement (the "Te
  - *Judgement*: **False Alarm** (Complex commercial agreement cross-reference to external exhibit or schedule item)

### 6. `Apollo Endosurgery - Manufacturing and Supply Agreement` — GENUINE INCONSISTENCY IN CONTRACT
- **Finding**: `figure_words_mismatch` (MEDIUM) at clause `2`
  - *Evidence*: ten (90) in snippet: 's within ten (90) days from the date'
  - *Judgement*: **Genuine Inconsistency** (Literal drafting conflict between words and parenthetical figures in SEC filing)

### 7. `MJBIOTECH,INC_12_06_2018-EX-99.01-JOINT VENTURE AGREEMENT` — FALSE ALARM
- **Finding**: `party_name_variant` (MEDIUM) at clause `None`
  - *Evidence*: Found 'Simply Herbals, Inc' (expected party 'SIMPLY HERBALS, Nervanah Herbal Medicine Company of _______________________________TN 37660') in: _________

CEO: MJ Syndicated, Inc CEO: Simply Herbals, Inc.

MJ Syndicated, Inc.

Per: __/s/ Maxin
  - *Judgement*: **False Alarm** (Detector scope over-reach or document OCR layout artifact)

### 8. `IDREAMSKYTECHNOLOGYLTD_07_03_2014-EX-10.39-Cooperation Agreement on Mobile Game Business` — FALSE ALARM
- **Finding**: `duplicate_clause_number` (MEDIUM) at clause `6`
  - *Evidence*: Clause 6 appears 2 times: 'Performance Bond' (page 11), 'It shall establish efficient information safety and confidentiality management policies and technical protective measures, and accept the management, supervision and inspection of relevant competent authority of the relevant business of Dazzle
  - *Judgement*: **False Alarm** (Annexure or exhibit repeating numbering section without distinct sub-header)

### 9. `BerkshireHillsBancorpInc_20120809_10-Q_EX-10.16_7708169_EX-10.16_Endorsement Agreement` — FALSE ALARM
- **Finding**: `figure_words_mismatch` (CRITICAL) at clause `3`
  - *Evidence*: one (1%) in snippet: 'rate of one (1%) percent per month.'
  - *Judgement*: **False Alarm** (Detector scope over-reach or document OCR layout artifact)

### 10. `VALENCETECHNOLOGYINC_02_14_2003-EX-10-JOINT VENTURE CONTRACT` — FALSE ALARM
- **Finding**: `duplicate_clause_number` (MEDIUM) at clause `1`
  - *Evidence*: Clause 1 appears 2 times: 'Parties to this Joint Venture Contract' (page 1), 'Baoding Fengfan Group Limited Liability Company (hereinafter referred to         as Party A), established and existing under the laws of the People's         Republic of China ("PRC"), registered with the No. 1306001000338
  - *Judgement*: **False Alarm** (Annexure or exhibit repeating numbering section without distinct sub-header)

### 11. `SFGFINANCIALCORP_05_12_2009-EX-10.1-SOFTWARE LICENSE AND MAINTENANCE AGREEMENT` — GENUINE INCONSISTENCY IN CONTRACT
- **Finding**: `figure_words_mismatch` (MEDIUM) at clause `3`
  - *Evidence*: Six (6,000,000) in snippet: 'ceipt of Six (6,000,000) Million shares of L'
  - *Judgement*: **Genuine Inconsistency** (Literal drafting conflict between words and parenthetical figures in SEC filing)
- **Finding**: `figure_words_mismatch` (HIGH) at clause `3`
  - *Evidence*: one third (33%) in snippet: 'Licensee one third (33%) of the gross  amoun'
  - *Judgement*: **False Alarm** (Detector scope over-reach or document OCR layout artifact)

### 12. `QuantumGroupIncFl_20090120_8-K_EX-99.2_3672910_EX-99.2_Hosting Agreement` — FALSE ALARM
- **Finding**: `dangling_reference` (MEDIUM) at clause `0`
  - *Evidence*: Target '11.6' referenced in: responsibilities set forth in Section 11.6. IBM provides Materials, non-
  - *Judgement*: **False Alarm** (Complex commercial agreement cross-reference to external exhibit or schedule item)
- **Finding**: `dangling_reference` (MEDIUM) at clause `0`
  - *Evidence*: Target '8.1' referenced in: ation payments as provided in Section 8.1; damages for bodily injury (i
  - *Judgement*: **False Alarm** (Complex commercial agreement cross-reference to external exhibit or schedule item)
- **Finding**: `dangling_reference` (MEDIUM) at clause `0`
  - *Evidence*: Target '4.8' referenced in: ined under Managed Servers in Section 4.8 (Fully Managed Servers; Physi
  - *Judgement*: **False Alarm** (Complex commercial agreement cross-reference to external exhibit or schedule item)
- **Finding**: `dangling_reference` (MEDIUM) at clause `0`
  - *Evidence*: Target '8.3' referenced in: ailability Credit, subject to Section 8.3(b), 8.4, 8.5, 8.6 and 8.7. If (and 1 other occurrence(s))
  - *Judgement*: **False Alarm** (Complex commercial agreement cross-reference to external exhibit or schedule item)
- **Finding**: `dangling_reference` (MEDIUM) at clause `3`
  - *Evidence*: Target '5.2' referenced in: nd payable in accordance with section 5.2 Payment. Monthly Recurring Ch
  - *Judgement*: **False Alarm** (Complex commercial agreement cross-reference to external exhibit or schedule item)

### 13. `SUCAMPOPHARMACEUTICALS,INC_11_04_2015-EX-10.2-STRATEGIC ALLIANCE AGREEMENT` — FALSE ALARM
- **Finding**: `dangling_reference` (MEDIUM) at clause `8.01`
  - *Evidence*: Target '27' referenced in: and applicable Law, including Articles 27-2 through 27-22 of the FIEL,  (and 1 other occurrence(s))
  - *Judgement*: **False Alarm** (Complex commercial agreement cross-reference to external exhibit or schedule item)
- **Finding**: `dangling_reference` (MEDIUM) at clause `8.01`
  - *Evidence*: Target '24' referenced in: e 24, 2015 in accordance with Article 24, Paragraph 1 of the FIEL, exc
  - *Judgement*: **False Alarm** (Complex commercial agreement cross-reference to external exhibit or schedule item)
- **Finding**: `dangling_reference` (MEDIUM) at clause `3.02`
  - *Evidence*: Target '167' referenced in: r Article 166, Paragraph 1 or Article 167, Paragraph 1 of the FIEL; (xi
  - *Judgement*: **False Alarm** (Complex commercial agreement cross-reference to external exhibit or schedule item)

### 14. `FOUNDATIONMEDICINE,INC_02_02_2015-EX-10.2-Collaboration Agreement` — FALSE ALARM
- **Finding**: `duplicate_clause_number` (MEDIUM) at clause `17`
  - *Evidence*: Clause 17 appears 2 times: 'Term and Termination  53  17.1 Commencement and Term  53  17.2 Termination  53  17.2.1 Termination for Breach  53  17.2.2 Insolvency  53  17.2.3 Termination by Roche without Cause  54  17.2.4 Termination by Roche for Frustration of Purpose  54  17.3 Consequences of Termin
  - *Judgement*: **False Alarm** (Annexure or exhibit repeating numbering section without distinct sub-header)

### 15. `SigaTechnologiesInc_20190603_8-K_EX-10.1_11695818_EX-10.1_Promotion Agreement` — FALSE ALARM
- **Finding**: `date_order_conflict` (HIGH) at clause `Schedule 1`
  - *Evidence*: Start date: 'May 31, 2019' (2019-05-31) in 'this "Agreement") is entered into as of May 31, 2019 (the "Effective Date") by and between S'; End date: 'June 22, 2015' (2015-06-22) in 'compositions containing the polymorphs June 22, 2015 March 23, 2031 RU 2578606 Russia Certai'
  - *Judgement*: **False Alarm** (Table/patent schedule expiry date compared against agreement commencement date)
- **Finding**: `date_order_conflict` (HIGH) at clause `Schedule 1`
  - *Evidence*: Start date: 'May 31, 2019' (2019-05-31) in 'this "Agreement") is entered into as of May 31, 2019 (the "Effective Date") by and between S'; End date: 'January 10, 2013' (2013-01-10) in 'and dosage unit forms containing ST-246 January 10, 2013 June 18, 2024 AU 2011232551 Australia C'
  - *Judgement*: **False Alarm** (Detector scope over-reach or document OCR layout artifact)
- **Finding**: `date_order_conflict` (HIGH) at clause `Schedule 1`
  - *Evidence*: Start date: 'May 31, 2019' (2019-05-31) in 'this "Agreement") is entered into as of May 31, 2019 (the "Effective Date") by and between S'; End date: 'April 12, 2017' (2017-04-12) in 'irus infections and associated diseases April 12, 2017 June 18, 2024 FR 2887938 France Methods'
  - *Judgement*: **False Alarm** (Detector scope over-reach or document OCR layout artifact)

### 16. `DIVERSINETCORP_03_01_2012-EX-4-RESELLER AGREEMENT` — GENUINE INCONSISTENCY IN CONTRACT
- **Finding**: `figure_words_mismatch` (MEDIUM) at clause `0`
  - *Evidence*: thirty (60) in snippet: 'roviding thirty (60) days' written notic'
  - *Judgement*: **Genuine Inconsistency** (Literal drafting conflict between words and parenthetical figures in SEC filing)

### 17. `BloomEnergyCorp_20180321_DRSA (on S-1)_EX-10_11240356_EX-10_Maintenance Agreement` — FALSE ALARM
- **Finding**: `dangling_reference` (MEDIUM) at clause `Appendix A`
  - *Evidence*: Target '352' referenced in: WHEREAS, pursuant to REPS Act Section 352(16), BE will be a "Qualified  (and 1 other occurrence(s))
  - *Judgement*: **False Alarm** (Complex commercial agreement cross-reference to external exhibit or schedule item)

### 18. `RangeResourcesLouisianaInc_20150417_8-K_EX-10.5_9045501_EX-10.5_Transportation Agreement` — FALSE ALARM
- **Finding**: `party_name_variant` (MEDIUM) at clause `1`
  - *Evidence*: Found 'PennTex North Louisiana, LLC' (expected party 'PennTex North Louisiana Operating, LLC') in: ty Agreement dated April 14, 2015 among PennTex North Louisiana, LLC, Shipper, PennTex NLA Holdings, LLC and
  - *Judgement*: **False Alarm** (Detector scope over-reach or document OCR layout artifact)
- **Finding**: `party_name_variant` (MEDIUM) at clause `Exhibit A`
  - *Evidence*: Found 'PennTex North Louisiana LLC' (expected party 'PennTex North Louisiana Operating, LLC') in: Issued and Compiled by: [Contact name] [PennTex North Louisiana LLC] 11931 Wickchester Lane, Suite 300 Hous
  - *Judgement*: **False Alarm** (Detector scope over-reach or document OCR layout artifact)

### 19. `EhaveInc_20190515_20-F_EX-4.44_11678816_EX-4.44_License Agreement_ Reseller Agreement` — FALSE ALARM
- **Finding**: `dangling_reference` (MEDIUM) at clause `10`
  - *Evidence*: Target '1' referenced in: d those provisions set out in Section 1 as necessary to interpret the
  - *Judgement*: **False Alarm** (Complex commercial agreement cross-reference to external exhibit or schedule item)
- **Finding**: `dangling_reference` (MEDIUM) at clause `12`
  - *Evidence*: Target '32' referenced in: ction 65.11(7) of the BIA and section 32(6) of the CCAA. CHT shall hav
  - *Judgement*: **False Alarm** (Complex commercial agreement cross-reference to external exhibit or schedule item)
- **Finding**: `dangling_reference` (MEDIUM) at clause `14`
  - *Evidence*: Target '45' referenced in: e to time, and in particular, section 45 thereof. The determination ar
  - *Judgement*: **False Alarm** (Complex commercial agreement cross-reference to external exhibit or schedule item)

### 20. `ROCKYMOUNTAINCHOCOLATEFACTORY,INC_12_23_2019-EX-10.2-STRATEGIC ALLIANCE AGREEMENT` — FALSE ALARM
- **Finding**: `figure_words_mismatch` (CRITICAL) at clause `5.2`
  - *Evidence*: million dollars ($3,000,000) in snippet: 'hree (3) million dollars ($3,000,000) and (y) in the case'
  - *Judgement*: **False Alarm** (Detector scope over-reach or document OCR layout artifact)
- **Finding**: `dangling_reference` (MEDIUM) at clause `5.2`
  - *Evidence*: Target '6.1' referenced in: RTICLE VI REGISTRATION RIGHTS Section 6.1 Demand Registration. (a) If t (and 2 other occurrence(s))
  - *Judgement*: **False Alarm** (Complex commercial agreement cross-reference to external exhibit or schedule item)

### 21. `InnerscopeHearingTechnologiesInc_20181109_8-K_EX-10.6_11419704_EX-10.6_Distributor Agreement` — FALSE ALARM
- **Finding**: `party_name_variant` (MEDIUM) at clause `12`
  - *Evidence*: Found 'Erchonia Medical Corporation' (expected party 'Erchonia Corporation') in: if any, being herein merged.

Dated: .

Erchonia Medical Corporation. By _____________________ Its _________
  - *Judgement*: **False Alarm** (Detector scope over-reach or document OCR layout artifact)

### 22. `ARMSTRONGFLOORING,INC_01_07_2019-EX-10.2-INTELLECTUAL PROPERTY AGREEMENT` — FALSE ALARM
- **Finding**: `date_order_conflict` (HIGH) at clause `Schedule 1`
  - *Evidence*: Start date: 'December 31, 2018' (2018-12-31) in 'REEMENT (this "Agreement"), dated as of December 31, 2018 (the "Effective Date") is entered into'; End date: '19-Dec- 2018' (2018-12-19) in 'on date Owner armstrongwoodproducts.com 19-Dec- 2018 AFI'
  - *Judgement*: **False Alarm** (Table/patent schedule expiry date compared against agreement commencement date)

### 23. `SoupmanInc_20150814_8-K_EX-10.1_9230148_EX-10.1_Franchise Agreement1` — FALSE ALARM
- **Finding**: `dangling_reference` (MEDIUM) at clause `2.3`
  - *Evidence*: Target '687.4' referenced in:  non-waiver provisions of GBL Sections 687.4 and 687.5 be satisfied).
3
  - *Judgement*: **False Alarm** (Complex commercial agreement cross-reference to external exhibit or schedule item)
- **Finding**: `dangling_reference` (MEDIUM) at clause `2.3`
  - *Evidence*: Target '687.5' referenced in:  non-waiver provisions of GBL Sections 687.4 and 687.5 be satisfied).
3
  - *Judgement*: **False Alarm** (Complex commercial agreement cross-reference to external exhibit or schedule item)

### 24. `BNLFINANCIALCORP_03_30_2007-EX-10.8-OUTSOURCING AGREEMENT` — GENUINE INCONSISTENCY IN CONTRACT
- **Finding**: `figure_words_mismatch` (MEDIUM) at clause `15`
  - *Evidence*: three (2) in snippet: 'mailed, three (2) days after deposit'
  - *Judgement*: **Genuine Inconsistency** (Literal drafting conflict between words and parenthetical figures in SEC filing)
- **Finding**: `dangling_reference` (MEDIUM) at clause `0`
  - *Evidence*: Target '1' referenced in: e user Equipment specified in paragraph 1.
  - *Judgement*: **False Alarm** (Complex commercial agreement cross-reference to external exhibit or schedule item)

### 25. `FIDELITYNATIONALINFORMATIONSERVICES,INC_08_05_2009-EX-10.3-INTELLECTUAL PROPERTY AGREEMENT` — FALSE ALARM
- **Finding**: `party_name_variant` (MEDIUM) at clause `Exhibit A`
  - *Evidence*: Found 'Equifax Asia Pacific Holdings, Inc' (expected party 'EQUIFAX INC') in: .                         Scotland





Equifax Asia Pacific Holdings, Inc.                  Georgia Equifax Austr
  - *Judgement*: **False Alarm** (Detector scope over-reach or document OCR layout artifact)
- **Finding**: `party_name_variant` (MEDIUM) at clause `Exhibit M`
  - *Evidence*: Found 'Equifax                           Credit Information Services, Inc' (expected party 'EQUIFAX INC') in: essing platform source code acquired by Equifax                           Credit Information Services, Inc. from Christopher T.                   
  - *Judgement*: **False Alarm** (Detector scope over-reach or document OCR layout artifact)
- **Finding**: `dangling_reference` (MEDIUM) at clause `4.7`
  - *Evidence*: Target '365' referenced in: y Act and shall be subject to Section 365(n) thereof, all as set forth 
  - *Judgement*: **False Alarm** (Complex commercial agreement cross-reference to external exhibit or schedule item)

### 26. `TRUENORTHENERGYCORP_02_08_2007-EX-10.1-DEVELOPMENT AGREEMENT` — FALSE ALARM
- **Finding**: `dangling_reference` (MEDIUM) at clause `1`
  - *Evidence*: Target '47' referenced in:  Heirs No. 1 well, located in Section 47, Township 4 South, Range 10 E
  - *Judgement*: **False Alarm** (Complex commercial agreement cross-reference to external exhibit or schedule item)

### 27. `OFGBANCORP_03_28_2007-EX-10.23-OUTSOURCING AGREEMENT` — FALSE ALARM
- **Finding**: `party_name_variant` (MEDIUM) at clause `Exhibit A.4`
  - *Evidence*: Found 'Oriental Financial Services Corp' (expected party 'Oriental Financial Group Inc') in: Oriental Financial Services Corp.
  - *Judgement*: **False Alarm** (Detector scope over-reach or document OCR layout artifact)

### 28. `ADIANUTRITION,INC_04_01_2005-EX-10.D2-RESELLER AGREEMENT` — FALSE ALARM
- **Finding**: `dangling_reference` (MEDIUM) at clause `2.9`
  - *Evidence*: Target '227.7202' referenced in: espectively, pursuant to DFAR Section 227.7202 and FAR Section 12.212, as ap
  - *Judgement*: **False Alarm** (Complex commercial agreement cross-reference to external exhibit or schedule item)
- **Finding**: `dangling_reference` (MEDIUM) at clause `2.9`
  - *Evidence*: Target '12.212' referenced in: DFAR Section 227.7202 and FAR Section 12.212, as applicable. Any use, modi
  - *Judgement*: **False Alarm** (Complex commercial agreement cross-reference to external exhibit or schedule item)

### 29. `SoupmanInc_20150814_8-K_EX-10.1_9230148_EX-10.1_Franchise Agreement3` — FALSE ALARM
- **Finding**: `dangling_reference` (MEDIUM) at clause `0`
  - *Evidence*: Target '20000' referenced in: Business and Professions Code Sections 20000 through 20043 provide rights to you concern
  - *Judgement*: **False Alarm** (Complex commercial agreement cross-reference to external exhibit or schedule item)
- **Finding**: `dangling_reference` (MEDIUM) at clause `0`
  - *Evidence*: Target '20043' referenced in: Business and Professions Code Sections 20000 through 20043 provide rights to you concern
  - *Judgement*: **False Alarm** (Complex commercial agreement cross-reference to external exhibit or schedule item)
- **Finding**: `dangling_reference` (MEDIUM) at clause `6`
  - *Evidence*: Target '20040.5' referenced in: Business and Professions Code Section 20040.5 and Code of Civil Procedure S
  - *Judgement*: **False Alarm** (Complex commercial agreement cross-reference to external exhibit or schedule item)
- **Finding**: `dangling_reference` (MEDIUM) at clause `6`
  - *Evidence*: Target '1281' referenced in: 5 and Code of Civil Procedure Section 1281) to any provisions of a franc
  - *Judgement*: **False Alarm** (Complex commercial agreement cross-reference to external exhibit or schedule item)

### 30. `MOVADOGROUPINC_04_30_2003-EX-10.28-ENDORSEMENT AGREEMENT` — FALSE ALARM
- **Finding**: `dangling_reference` (MEDIUM) at clause `12`
  - *Evidence*: Target '2520.104' referenced in: epartment of Labor Regulation Section 2520.104-24.
  - *Judgement*: **False Alarm** (Complex commercial agreement cross-reference to external exhibit or schedule item)

### 31. `EmeraldHealthBioceuticalsInc_20200218_1-A_EX1A-6 MAT CTRCT_11987205_EX1A-6 MAT CTRCT_Development Agreement` — FALSE ALARM
- **Finding**: `party_name_variant` (MEDIUM) at clause `9`
  - *Evidence*: Found 'Murray Emerald Health Sciences Inc' (expected party 'Emerald Health Sciences Inc') in: CEUTICALS INC., 1-A, 2/18/2020





Dr. Murray Emerald Health Sciences Inc.

/s/Michael T. Murray, N.D By:/s/ Avta
  - *Judgement*: **False Alarm** (Detector scope over-reach or document OCR layout artifact)

### 32. `CHEETAHMOBILEINC_04_22_2014-EX-10.43-Cooperation Agreement` — FALSE ALARM
- **Finding**: `date_order_conflict` (HIGH) at clause `3.1.1`
  - *Evidence*: Start date: 'May 1, 2013' (2013-05-01) in 'is Agreement is effective on the day of May 1, 2013 and the effective term is the same as t'; End date: 'April 30, 2013' (2013-04-30) in 'UD0118, 151215UD0119) are terminated on April 30, 2013.'
  - *Judgement*: **False Alarm** (Detector scope over-reach or document OCR layout artifact)

### 33. `HALITRON,INC_03_01_2005-EX-10.15-SPONSORSHIP AND DEVELOPMENT AGREEMENT` — FALSE ALARM
- **Finding**: `duplicate_clause_number` (MEDIUM) at clause `4`
  - *Evidence*: Clause 4 appears 2 times: 'COMPENSATION' (page 3), 'COMPENSATION' (page 8)
  - *Judgement*: **False Alarm** (Annexure or exhibit repeating numbering section without distinct sub-header)

### 34. `WestPharmaceuticalServicesInc_20200116_8-K_EX-10.1_11947529_EX-10.1_Supply Agreement` — FALSE ALARM
- **Finding**: `party_name_variant` (MEDIUM) at clause `20`
  - *Evidence*: Found 'A West Pharmaceutical Services, Inc' (expected party 'West Pharmaceutical Services, Inc') in: n Circle Jurong, Singapore 629046


U.S.A West Pharmaceutical Services, Inc. 530 Herman O. West Drive Exton, PA 193
  - *Judgement*: **False Alarm** (Detector scope over-reach or document OCR layout artifact)
- **Finding**: `party_name_variant` (MEDIUM) at clause `20`
  - *Evidence*: Found 'ExxonMobil Chemical Company West Pharmaceutical Services, Inc' (expected party 'ExxonMobil Chemical Company') in: ing written notice to the other party.

ExxonMobil Chemical Company West Pharmaceutical Services, Inc. 22777 Springwoods Village Pkwy 530 W. 
  - *Judgement*: **False Alarm** (Detector scope over-reach or document OCR layout artifact)

### 35. `EUROPEANMICROHOLDINGSINC_03_06_1998-EX-10.6-DISTRIBUTOR AGREEMENT` — FALSE ALARM
- **Finding**: `date_order_conflict` (HIGH) at clause `7.0`
  - *Evidence*: Start date: 'November 5, 1997' (1997-11-05) in 's made and entered into effective as of November 5, 1997 (the "effective Date), by and between W'; End date: 'September 30, 1997' (1997-09-30) in 'September 30, 1997 TRADEMARKS:'
  - *Judgement*: **False Alarm** (Detector scope over-reach or document OCR layout artifact)

### 36. `GOCALLINC_03_30_2000-EX-10.7-Promotion Agreement` — FALSE ALARM
- **Finding**: `party_name_variant` (MEDIUM) at clause `14`
  - *Evidence*: Found 'At PageMaster Corporation' (expected party 'PageMaster Corporation') in: shall have no liability to one another. At PageMaster Corporation's option, an additional agreement(s) ma
  - *Judgement*: **False Alarm** (Detector scope over-reach or document OCR layout artifact)

### 37. `GluMobileInc_20070319_S-1A_EX-10.09_436630_EX-10.09_Content License Agreement2` — FALSE ALARM
- **Finding**: `date_order_conflict` (HIGH) at clause `2`
  - *Evidence*: Start date: 'November 11, 2005' (2005-11-11) in 'Preamble AMENDMENT NO. 1 Dated as of November 11, 2005 Reference is hereby made to that certai'; End date: 'October 29, 2005' (2005-10-29) in 'to the KOH Video Clips shall expire on October 29, 2005, and Licensee's right and license to di'
  - *Judgement*: **False Alarm** (Detector scope over-reach or document OCR layout artifact)

### 38. `BLUEHILLSBANCORP,INC_05_20_2014-EX-1.1-AGENCY AGREEMENT` — FALSE ALARM
- **Finding**: `party_name_variant` (MEDIUM) at clause `20`
  - *Evidence*: Found 'Blue Hills Bank   Blue Hills Bancorp, Inc' (expected party 'Blue Hills Bancorp, Inc') in: inding agreement.

Very truly yours,

  Blue Hills Bank   Blue Hills Bancorp, Inc.

By Its Authorized Representative:   B
  - *Judgement*: **False Alarm** (Detector scope over-reach or document OCR layout artifact)

### 39. `HC2HOLDINGS,INC_05_14_2020-EX-10.1-COOPERATION AGREEMENT` — FALSE ALARM
- **Finding**: `party_name_variant` (MEDIUM) at clause `Exhibit B`
  - *Evidence*: Found 'HC2 HC2 Holdings, Inc' (expected party 'HC2 Holdings, Inc') in: ng as MG Capital's legal advisor.






About HC2 HC2 Holdings, Inc. is a publicly traded (NYSE: HCHC) dive
  - *Judgement*: **False Alarm** (Detector scope over-reach or document OCR layout artifact)

### 40. `SEASPINEHOLDINGSCORP_10_10_2018-EX-10.1-SUPPLY AGREEMENT` — FALSE ALARM
- **Finding**: `party_name_variant` (MEDIUM) at clause `12.15`
  - *Evidence*: Found 'INTEGRA LIFESCIENCES CORPORATION PCOMED, LLC' (expected party 'Integra LifeSciences Corporation') in: his Agreement as of the Effective Date. INTEGRA LIFESCIENCES CORPORATION PCOMED, LLC

By: /s/ Brian Larkin By: /s/ Steve Jac
  - *Judgement*: **False Alarm** (Detector scope over-reach or document OCR layout artifact)

### 41. `ENTERPRISEPRODUCTSPARTNERSLP_07_08_1998-EX-10.3-TRANSPORTATION CONTRACT` — FALSE ALARM
- **Finding**: `party_name_variant` (MEDIUM) at clause `4`
  - *Evidence*: Found 'ENTERPRISE TRANSPORTATION COMPANY By Enterprise Products GP, LLC' (expected party 'ENTERPRISE TRANSPORTATION COMPANY') in: E.

ENTERPRISE PRODUCTS OPERATING L.P.  ENTERPRISE TRANSPORTATION COMPANY By Enterprise Products GP, LLC, its general partner (Shipper)

By: /s/
  - *Judgement*: **False Alarm** (Detector scope over-reach or document OCR layout artifact)
- **Finding**: `dangling_reference` (MEDIUM) at clause `2`
  - *Evidence*: Target '5069' referenced in: uant to applicable Texas law, Article 5069-1.04 Texas Rev. Civ. Stat., a
  - *Judgement*: **False Alarm** (Complex commercial agreement cross-reference to external exhibit or schedule item)
- **Finding**: `duplicate_clause_number` (MEDIUM) at clause `1`
  - *Evidence*: Clause 1 appears 2 times: 'Shipper shall tender commodities to Carrier for transportation by Carrier in a specialized service designed to meet the distinct needs of Shipper in  interstate or foreign commerce between points in the United States.' (page 1), 'For each shipment under this contract, Ship
  - *Judgement*: **False Alarm** (Annexure or exhibit repeating numbering section without distinct sub-header)

### 42. `HerImports_20161018_8-KA_EX-10.14_9765707_EX-10.14_Maintenance Agreement` — FALSE ALARM
- **Finding**: `date_order_conflict` (HIGH) at clause `0`
  - *Evidence*: Start date: 'October 13, 2016' (2016-10-13) in '(the "Agreement") is entered into as of October 13, 2016, between Leader Act Ltd HK ("LEADER"),'; End date: 'May 28, 2016' (2016-05-28) in 'EAS, this previous agreement expired on May 28, 2016;   NOW THEREFORE, in consideration of t'
  - *Judgement*: **False Alarm** (Recital discussing previous expired contract captured as current contract termination date)

### 43. `PROLONGINTERNATIONALCORP_03_23_1998-EX-10.16-SPONSORSHIP AGREEMENT` — FALSE ALARM
- **Finding**: `figure_words_mismatch` (MEDIUM) at clause `4`
  - *Evidence*: One (1998) in snippet: 's:  Year One (1998): $ [ * ] (four  equ'
  - *Judgement*: **False Alarm** (Detector scope over-reach or document OCR layout artifact)

### 44. `SANDRIDGEENERGYINC_08_06_2009-EX-10.6-OPERATIONS AND MAINTENANCE AGREEMENT` — FALSE ALARM
- **Finding**: `dangling_reference` (MEDIUM) at clause `1`
  - *Evidence*: Target '171.0001' referenced in: et forth in V.T.C.A. Tax Code Section 171.0001 et. seq., as the same may be  (and 1 other occurrence(s))
  - *Judgement*: **False Alarm** (Complex commercial agreement cross-reference to external exhibit or schedule item)

### 45. `NlsPharmaceuticsLtd_20200228_F-1_EX-10.14_12029046_EX-10.14_Development Agreement` — GENUINE INCONSISTENCY IN CONTRACT
- **Finding**: `figure_words_mismatch` (MEDIUM) at clause `3.3`
  - *Evidence*: thirty (45) in snippet: 'y within thirty (45) days following the'
  - *Judgement*: **Genuine Inconsistency** (Literal drafting conflict between words and parenthetical figures in SEC filing)

### 46. `BellringBrandsInc_20190920_S-1_EX-10.12_11817081_EX-10.12_Manufacturing Agreement1` — FALSE ALARM
- **Finding**: `party_name_variant` (MEDIUM) at clause `9`
  - *Evidence*: Found 'PREMIER NUTRITION CORPORATION STREMICKS HERITAGE FOODS, LLC' (expected party 'PREMIER NUTRITION CORPORATION') in: n the day and year first above written. PREMIER NUTRITION CORPORATION STREMICKS HERITAGE FOODS, LLC

BY: /s/ Darcy Davenport BY: /s/ Sam St
  - *Judgement*: **False Alarm** (Detector scope over-reach or document OCR layout artifact)

### 47. `MANUFACTURERSSERVICESLTD_06_05_2000-EX-10.14-OUTSOURCING AGREEMENT` — FALSE ALARM
- **Finding**: `party_name_variant` (MEDIUM) at clause `1.0`
  - *Evidence*: Found 'Manufacturers' Services Limited' (expected party 'MANUFACTURERS' SERVICES WESTERN U.S. OPERATIONS, INC') in: .12  "MSL Related Companies" shall mean Manufacturers' Services Limited       (Delaware, USA) and its Subsidiar
  - *Judgement*: **False Alarm** (Detector scope over-reach or document OCR layout artifact)
- **Finding**: `party_name_variant` (MEDIUM) at clause `5`
  - *Evidence*: Found 'Manufacturers' Services Western      International Business Machines Corporation' (expected party 'MANUFACTURERS' SERVICES WESTERN U.S. OPERATIONS, INC') in: :                           Agreed To:

Manufacturers' Services Western      International Business Machines Corporation U.S. Operation
  - *Judgement*: **False Alarm** (Detector scope over-reach or document OCR layout artifact)
- **Finding**: `party_name_variant` (MEDIUM) at clause `16`
  - *Evidence*: Found 'IBM Corporation                       Manufacturers' Services Western                                             US Operations, Inc' (expected party 'MANUFACTURERS' SERVICES WESTERN U.S. OPERATIONS, INC') in:          ACCEPTED AND AGREED TO:

      IBM Corporation                       Manuf
  - *Judgement*: **False Alarm** (Detector scope over-reach or document OCR layout artifact)

### 48. `LiquidmetalTechnologiesInc_20200205_8-K_EX-10.1_11968198_EX-10.1_Development Agreement` — FALSE ALARM
- **Finding**: `dangling_reference` (MEDIUM) at clause `5.3`
  - *Evidence*: Target 'iv' referenced in: s Agreement; iii. Comply with Section 9.2 and iv. transfer title and deliver t
  - *Judgement*: **False Alarm** (Complex commercial agreement cross-reference to external exhibit or schedule item)

### 49. `ScansourceInc_20190822_10-K_EX-10.39_11793959_EX-10.39_Distributor Agreement` — FALSE ALARM
- **Finding**: `dangling_reference` (MEDIUM) at clause `2`
  - *Evidence*: Target '6.7' referenced in: d by adding the following new Section 6.7: 6.7 [*****]
  - *Judgement*: **False Alarm** (Complex commercial agreement cross-reference to external exhibit or schedule item)

### 50. `LOOKSMARTLTD_07_20_2012-EX-99.(D)(I)-SPONSORSHIP AGREEMENT` — FALSE ALARM
- **Finding**: `numbering_gap` (HIGH) at clause `1`
  - *Evidence*: Missing clause 1 between clause 0 and clause 2 (cross-referenced by dangling reference to '1')
  - *Judgement*: **False Alarm** (Detector scope over-reach or document OCR layout artifact)

### 51. `MOELIS_CO_03_24_2014-EX-10.19-STRATEGIC ALLIANCE AGREEMENT` — FALSE ALARM
- **Finding**: `figure_words_mismatch` (MEDIUM) at clause `4.3`
  - *Evidence*: million (2) in snippet: 'ory, $3 million, (2) restructuring advis'
  - *Judgement*: **False Alarm** (Detector scope over-reach or document OCR layout artifact)
- **Finding**: `dangling_reference` (MEDIUM) at clause `12.3`
  - *Evidence*: Target '8.4.1' referenced in:  General Partner set forth in Sections 8.4.1 and 8.4.2, respectively, of the Moelis 
  - *Judgement*: **False Alarm** (Complex commercial agreement cross-reference to external exhibit or schedule item)
- **Finding**: `dangling_reference` (MEDIUM) at clause `12.3`
  - *Evidence*: Target '8.4.2' referenced in:  General Partner set forth in Sections 8.4.1 and 8.4.2, respectively, of the Moelis 
  - *Judgement*: **False Alarm** (Complex commercial agreement cross-reference to external exhibit or schedule item)

### 52. `XYBERNAUTCORP_07_12_2002-EX-4-SPONSORSHIP AGREEMENT` — FALSE ALARM
- **Finding**: `term_length_conflict` (MEDIUM) at clause `3`
  - *Evidence*: Stated term: 'for a period of three (3) years'; Start: 2002-05-01, End: 2002-10-12 (span: 164 days)
  - *Judgement*: **False Alarm** (Detector scope over-reach or document OCR layout artifact)

### 53. `ArmstrongFlooringInc_20190107_8-K_EX-10.2_11471795_EX-10.2_Intellectual Property Agreement` — FALSE ALARM
- **Finding**: `date_order_conflict` (HIGH) at clause `Schedule 1`
  - *Evidence*: Start date: 'December 31, 2018' (2018-12-31) in 'REEMENT (this "Agreement"), dated as of December 31, 2018 (the "Effective Date") is entered into'; End date: '19-Dec- 2018' (2018-12-19) in 'on date Owner armstrongwoodproducts.com 19-Dec- 2018 AFI'
  - *Judgement*: **False Alarm** (Table/patent schedule expiry date compared against agreement commencement date)

### 54. `EcoScienceSolutionsInc_20180406_8-K_EX-10.1_11135398_EX-10.1_Sponsorship Agreement` — FALSE ALARM
- **Finding**: `party_name_variant` (MEDIUM) at clause `None`
  - *Evidence*: Found 'EcoScience Solutions, Inc' (expected party 'Eco Science Solutions, Inc') in: EcoScience Solutions, Inc. (Sponsor) Address: 1135 Makawao Avenue
  - *Judgement*: **False Alarm** (Detector scope over-reach or document OCR layout artifact)

### 55. `GluMobileInc_20070319_S-1A_EX-10.09_436630_EX-10.09_Content License Agreement4` — FALSE ALARM
- **Finding**: `date_order_conflict` (HIGH) at clause `1`
  - *Evidence*: Start date: 'February 19, 2007' (2007-02-19) in 'Preamble AMENDMENT NO. 3 Dated as of February 19, 2007 Reference is hereby made to that certai'; End date: 'December 31, 2006' (2006-12-31) in 'the Effective Date and shall expire on December 31, 2006 (the "Term"); provided, however, that w'
  - *Judgement*: **False Alarm** (Detector scope over-reach or document OCR layout artifact)

### 56. `GOOSEHEADINSURANCE,INC_04_02_2018-EX-10.6-Franchise Agreement` — FALSE ALARM
- **Finding**: `dangling_reference` (MEDIUM) at clause `13`
  - *Evidence*: Target '31125' referenced in: California Corporations Code, Section 31125, requires Franchisor to give 
  - *Judgement*: **False Alarm** (Complex commercial agreement cross-reference to external exhibit or schedule item)
- **Finding**: `dangling_reference` (MEDIUM) at clause `13`
  - *Evidence*: Target '20000' referenced in: Business and Professions Code Sections 20000 through 20043 provide rights to Franchisee  (and 1 other occurrence(s))
  - *Judgement*: **False Alarm** (Complex commercial agreement cross-reference to external exhibit or schedule item)
- **Finding**: `dangling_reference` (MEDIUM) at clause `13`
  - *Evidence*: Target '20043' referenced in: Business and Professions Code Sections 20000 through 20043 provide rights to Franchisee 
  - *Judgement*: **False Alarm** (Complex commercial agreement cross-reference to external exhibit or schedule item)
- **Finding**: `dangling_reference` (MEDIUM) at clause `13`
  - *Evidence*: Target '20040.5' referenced in: Business and Professions Code Section 20040.5, Code of Civil Procedure

FDD
  - *Judgement*: **False Alarm** (Complex commercial agreement cross-reference to external exhibit or schedule item)
- **Finding**: `dangling_reference` (MEDIUM) at clause `1281`
  - *Evidence*: Target '31000' referenced in: (California Corporations Code Section 31000-31516). Business and Professi
  - *Judgement*: **False Alarm** (Complex commercial agreement cross-reference to external exhibit or schedule item)
- **Finding**: `dangling_reference` (MEDIUM) at clause `1281`
  - *Evidence*: Target '20010' referenced in: Business and Professions Code Section 20010 voids a waiver of Franchisee'
  - *Judgement*: **False Alarm** (Complex commercial agreement cross-reference to external exhibit or schedule item)
- **Finding**: `dangling_reference` (MEDIUM) at clause `Exhibit A.2`
  - *Evidence*: Target '25.5' referenced in: T SUMMARY

v. Choice of forum Section 25.5 Litigation may be brought in 
  - *Judgement*: **False Alarm** (Complex commercial agreement cross-reference to external exhibit or schedule item)
- **Finding**: `dangling_reference` (MEDIUM) at clause `Exhibit A.5`
  - *Evidence*: Target '687.4' referenced in: sions of General Business Law Sections 687.4 and 687.5 be satisfied. (and 2 other occurrence(s))
  - *Judgement*: **False Alarm** (Complex commercial agreement cross-reference to external exhibit or schedule item)
- **Finding**: `dangling_reference` (MEDIUM) at clause `Exhibit A.5`
  - *Evidence*: Target '687.5' referenced in: sions of General Business Law Sections 687.4 and 687.5 be satisfied. (and 2 other occurrence(s))
  - *Judgement*: **False Alarm** (Complex commercial agreement cross-reference to external exhibit or schedule item)
- **Finding**: `dangling_reference` (MEDIUM) at clause `Exhibit A.8`
  - *Evidence*: Target '33' referenced in: ew York General Business Law, Article 33, Sections 680 through 695, an (and 2 other occurrence(s))
  - *Judgement*: **False Alarm** (Complex commercial agreement cross-reference to external exhibit or schedule item)
- **Finding**: `dangling_reference` (MEDIUM) at clause `Exhibit A.8`
  - *Evidence*: Target '680' referenced in: ral Business Law, Article 33, Sections 680 through 695, and of the regulations promu (and 3 other occurrence(s))
  - *Judgement*: **False Alarm** (Complex commercial agreement cross-reference to external exhibit or schedule item)
- **Finding**: `dangling_reference` (MEDIUM) at clause `Exhibit A.8`
  - *Evidence*: Target '681' referenced in: ral Business Law, Article 33, Sections 680 through 695, and of the regulations promu
  - *Judgement*: **False Alarm** (Complex commercial agreement cross-reference to external exhibit or schedule item)
- **Finding**: `dangling_reference` (MEDIUM) at clause `Exhibit A.8`
  - *Evidence*: Target '682' referenced in: ral Business Law, Article 33, Sections 680 through 695, and of the regulations promu
  - *Judgement*: **False Alarm** (Complex commercial agreement cross-reference to external exhibit or schedule item)
- **Finding**: `dangling_reference` (MEDIUM) at clause `Exhibit A.8`
  - *Evidence*: Target '683' referenced in: ral Business Law, Article 33, Sections 680 through 695, and of the regulations promu
  - *Judgement*: **False Alarm** (Complex commercial agreement cross-reference to external exhibit or schedule item)
- **Finding**: `dangling_reference` (MEDIUM) at clause `Exhibit A.8`
  - *Evidence*: Target '684' referenced in: ral Business Law, Article 33, Sections 680 through 695, and of the regulations promu
  - *Judgement*: **False Alarm** (Complex commercial agreement cross-reference to external exhibit or schedule item)
- **Finding**: `dangling_reference` (MEDIUM) at clause `Exhibit A.8`
  - *Evidence*: Target '685' referenced in: ral Business Law, Article 33, Sections 680 through 695, and of the regulations promu
  - *Judgement*: **False Alarm** (Complex commercial agreement cross-reference to external exhibit or schedule item)
- **Finding**: `dangling_reference` (MEDIUM) at clause `Exhibit A.8`
  - *Evidence*: Target '686' referenced in: ral Business Law, Article 33, Sections 680 through 695, and of the regulations promu
  - *Judgement*: **False Alarm** (Complex commercial agreement cross-reference to external exhibit or schedule item)
- **Finding**: `dangling_reference` (MEDIUM) at clause `Exhibit A.8`
  - *Evidence*: Target '687' referenced in: ral Business Law, Article 33, Sections 680 through 695, and of the regulations promu
  - *Judgement*: **False Alarm** (Complex commercial agreement cross-reference to external exhibit or schedule item)
- **Finding**: `dangling_reference` (MEDIUM) at clause `Exhibit A.8`
  - *Evidence*: Target '688' referenced in: ral Business Law, Article 33, Sections 680 through 695, and of the regulations promu
  - *Judgement*: **False Alarm** (Complex commercial agreement cross-reference to external exhibit or schedule item)
- **Finding**: `dangling_reference` (MEDIUM) at clause `Exhibit A.8`
  - *Evidence*: Target '689' referenced in: ral Business Law, Article 33, Sections 680 through 695, and of the regulations promu
  - *Judgement*: **False Alarm** (Complex commercial agreement cross-reference to external exhibit or schedule item)
- **Finding**: `dangling_reference` (MEDIUM) at clause `Exhibit A.8`
  - *Evidence*: Target '690' referenced in: ral Business Law, Article 33, Sections 680 through 695, and of the regulations promu
  - *Judgement*: **False Alarm** (Complex commercial agreement cross-reference to external exhibit or schedule item)
- **Finding**: `dangling_reference` (MEDIUM) at clause `Exhibit A.8`
  - *Evidence*: Target '691' referenced in: ral Business Law, Article 33, Sections 680 through 695, and of the regulations promu
  - *Judgement*: **False Alarm** (Complex commercial agreement cross-reference to external exhibit or schedule item)
- **Finding**: `dangling_reference` (MEDIUM) at clause `Exhibit A.8`
  - *Evidence*: Target '692' referenced in: ral Business Law, Article 33, Sections 680 through 695, and of the regulations promu
  - *Judgement*: **False Alarm** (Complex commercial agreement cross-reference to external exhibit or schedule item)
- **Finding**: `dangling_reference` (MEDIUM) at clause `Exhibit A.8`
  - *Evidence*: Target '693' referenced in: ral Business Law, Article 33, Sections 680 through 695, and of the regulations promu
  - *Judgement*: **False Alarm** (Complex commercial agreement cross-reference to external exhibit or schedule item)
- **Finding**: `dangling_reference` (MEDIUM) at clause `Exhibit A.8`
  - *Evidence*: Target '694' referenced in: ral Business Law, Article 33, Sections 680 through 695, and of the regulations promu
  - *Judgement*: **False Alarm** (Complex commercial agreement cross-reference to external exhibit or schedule item)
- **Finding**: `dangling_reference` (MEDIUM) at clause `Exhibit A.8`
  - *Evidence*: Target '695' referenced in: ral Business Law, Article 33, Sections 680 through 695, and of the regulations promu
  - *Judgement*: **False Alarm** (Complex commercial agreement cross-reference to external exhibit or schedule item)
- **Finding**: `dangling_reference` (MEDIUM) at clause `Exhibit A.5`
  - *Evidence*: Target '51' referenced in:  to North Dakota franchisees (Section 51-19-09, N.D.C.C.):

A. Restric
  - *Judgement*: **False Alarm** (Complex commercial agreement cross-reference to external exhibit or schedule item)

### 57. `JOINTCORP_09_19_2014-EX-10.15-FRANCHISE AGREEMENT` — FALSE ALARM
- **Finding**: `duplicate_clause_number` (MEDIUM) at clause `6`
  - *Evidence*: Clause 6 appears 2 times: 'FEES AND COSTS.   6.1 Initial Franchise Fee.   You agree to pay us the initial franchise fee of Twenty-Nine Thousand and No/100 Dollars ($29,000.00) (the "Initial Franchise Fee") when you sign this Agreement. In recognition of the expenses we incur in furnishing assistance
  - *Judgement*: **False Alarm** (Annexure or exhibit repeating numbering section without distinct sub-header)

### 58. `VnueInc_20150914_8-K_EX-10.1_9259571_EX-10.1_Promotion Agreement` — GENUINE INCONSISTENCY IN CONTRACT
- **Finding**: `figure_words_mismatch` (CRITICAL) at clause `None`
  - *Evidence*: and Five Thousand Dollars ($5,000,00) in snippet: 'er venue and Five Thousand Dollars ($5,000,00) for each Two (2) Ye'
  - *Judgement*: **Genuine Inconsistency** (Literal drafting conflict between words and parenthetical figures in SEC filing)

### 59. `SteelVaultCorp_20081224_10-K_EX-10.16_3074935_EX-10.16_Affiliate Agreement` — FALSE ALARM
- **Finding**: `duplicate_clause_number` (MEDIUM) at clause `1`
  - *Evidence*: Clause 1 appears 2 times: 'Equidata provides certain personal credit, fraud detection, credit scoring services and credit monitoring for consumers, the  ("Services").    2.   Marketing Affiliate and Equidata wish to enter into an agreement under which Marketing Affiliate may market the Services.    
  - *Judgement*: **False Alarm** (Annexure or exhibit repeating numbering section without distinct sub-header)

### 60. `WARNERCHILCOTTPLC_12_31_2003-EX-4.36-DEVELOPMENT AGREEMENT` — FALSE ALARM
- **Finding**: `dangling_reference` (MEDIUM) at clause `0`
  - *Evidence*: Target 'I' referenced in: ave the meanings set forth in Article I of this Agreement.

WHEREAS B
  - *Judgement*: **False Alarm** (Complex commercial agreement cross-reference to external exhibit or schedule item)

### 61. `MidwestEnergyEmissionsCorp_20080604_8-K_EX-10.2_3093976_EX-10.2_Content License Agreement` — FALSE ALARM
- **Finding**: `dangling_reference` (MEDIUM) at clause `20`
  - *Evidence*: Target 'o' referenced in:  operation of any other term, clause o provision and such invalid te
  - *Judgement*: **False Alarm** (Complex commercial agreement cross-reference to external exhibit or schedule item)

### 62. `NOVOINTEGRATEDSCIENCES,INC_12_23_2019-EX-10.1-JOINT VENTURE AGREEMENT` — FALSE ALARM
- **Finding**: `dangling_reference` (MEDIUM) at clause `2`
  - *Evidence*: Target '3' referenced in: y in relation to the project. ARTICLE 3 - RELATIONSHIP OF PARTIES 3.1
  - *Judgement*: **False Alarm** (Complex commercial agreement cross-reference to external exhibit or schedule item)
- **Finding**: `dangling_reference` (MEDIUM) at clause `2`
  - *Evidence*: Target '4' referenced in:  of the agricultural project. ARTICLE 4 - OFFICE LOCATION 4.1 The Com
  - *Judgement*: **False Alarm** (Complex commercial agreement cross-reference to external exhibit or schedule item)
- **Finding**: `dangling_reference` (MEDIUM) at clause `6.2`
  - *Evidence*: Target '7' referenced in: nding buyer contract receipt. ARTICLE 7 - PRINCIPLE AND LINE OF CREDI
  - *Judgement*: **False Alarm** (Complex commercial agreement cross-reference to external exhibit or schedule item)
- **Finding**: `dangling_reference` (MEDIUM) at clause `10`
  - *Evidence*: Target '11' referenced in: l rotation as per SCHEDULE A. ARTICLE 11 - MANAGEMENT PERSONNEL 11.1 A
  - *Judgement*: **False Alarm** (Complex commercial agreement cross-reference to external exhibit or schedule item)
- **Finding**: `dangling_reference` (MEDIUM) at clause `10`
  - *Evidence*: Target '13' referenced in: ths of annual considerations. ARTICLE 13 - CURRENCY 13.1 Except where 
  - *Judgement*: **False Alarm** (Complex commercial agreement cross-reference to external exhibit or schedule item)
- **Finding**: `dangling_reference` (MEDIUM) at clause `10`
  - *Evidence*: Target '14' referenced in: referenced are in US dollars. ARTICLE 14 - BANKING AND ACCOUNTING 14.1
  - *Judgement*: **False Alarm** (Complex commercial agreement cross-reference to external exhibit or schedule item)
- **Finding**: `dangling_reference` (MEDIUM) at clause `15.2`
  - *Evidence*: Target '16' referenced in: eptember 1 through August 31. ARTICLE 16 - TAXES 16.1 The Company will
  - *Judgement*: **False Alarm** (Complex commercial agreement cross-reference to external exhibit or schedule item)
- **Finding**: `dangling_reference` (MEDIUM) at clause `15.2`
  - *Evidence*: Target '17' referenced in: ion of any tax consideration. ARTICLE 17 - PRESERVATION OF RECORDS 17.
  - *Judgement*: **False Alarm** (Complex commercial agreement cross-reference to external exhibit or schedule item)
- **Finding**: `dangling_reference` (MEDIUM) at clause `15.2`
  - *Evidence*: Target '18' referenced in: by federal or provincial law. ARTICLE 18 - ASSIGNMENT BY NVOS 18.1 Dur
  - *Judgement*: **False Alarm** (Complex commercial agreement cross-reference to external exhibit or schedule item)
- **Finding**: `dangling_reference` (MEDIUM) at clause `15.2`
  - *Evidence*: Target '19' referenced in:  prior written notice to HGF. ARTICLE 19 - ASSIGNMENT BY HGF 19.1 Duri
  - *Judgement*: **False Alarm** (Complex commercial agreement cross-reference to external exhibit or schedule item)
- **Finding**: `dangling_reference` (MEDIUM) at clause `15.2`
  - *Evidence*: Target '20' referenced in: r interest in this agreement. ARTICLE 20 - BEST EFFORTS 20.1 NVOS and 
  - *Judgement*: **False Alarm** (Complex commercial agreement cross-reference to external exhibit or schedule item)
- **Finding**: `dangling_reference` (MEDIUM) at clause `15.2`
  - *Evidence*: Target '22' referenced in: rt of competent jurisdiction. ARTICLE 22 - INDEMNIFICATION 22.1 The Pa
  - *Judgement*: **False Alarm** (Complex commercial agreement cross-reference to external exhibit or schedule item)
