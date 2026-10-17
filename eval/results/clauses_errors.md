# Clause Classification Error Analysis (TEST Split)

Honest error analysis on the 20% unseen CUAD test split (102 contracts, 2,788 clauses).
Below are the 5 weakest labels by F1 score (with support >= 5), with concrete False Positive
and False Negative examples analyzing failure modes.

## Summary of 5 Weakest Labels

| Label | Support | Pred Count | Precision (95% CI) | Recall (95% CI) | F1 |
|---|---|---|---|---|---|
| `most_favored_nation` | 7 | 0 | 0.000 [0.00, 0.00] | 0.000 [0.00, 0.35] | 0.000 |
| `affiliate_license_licensor` | 5 | 9 | 0.111 [0.02, 0.43] | 0.200 [0.04, 0.62] | 0.143 |
| `competitive_restriction_exception` | 14 | 21 | 0.191 [0.08, 0.40] | 0.286 [0.12, 0.55] | 0.229 |
| `joint_ip_ownership` | 13 | 3 | 0.667 [0.21, 0.94] | 0.154 [0.04, 0.42] | 0.250 |
| `volume_restriction` | 22 | 7 | 0.571 [0.25, 0.84] | 0.182 [0.07, 0.39] | 0.276 |

---

## Detailed Error Analysis per Weak Label

### Label: `most_favored_nation` (F1: 0.000, Support: 7)

#### False Positives (Predicted, but not in CUAD expert annotations):
- *No False Positives observed.*
#### False Negatives (In CUAD expert annotations, but missed by detector):
**FN #1** - Contract: `NANOPHASETECHNOLOGIESCORP_11_01_2005-EX-...`, Clause: `3`
- **Expert Target Span:** "NTC agrees that the Product Prices, benefits and allowances offered to ALFA AESAR shall not be less ..."
- **Clause Text:** "Product Prices. Any such increase in the Product Price shall not be effective for any unshipped portion of an order previously placed by ALFA AESAR prior to the end of the calendar year in which such ..."
- **Root Cause:** Atypical drafting vocabulary or domain-specific phrasing not captured by TF-IDF n-grams or regular expressions.

**FN #2** - Contract: `USASYNTHETICFUELCORP_10_21_2010-EX-10.10...`, Clause: `7`
- **Expert Target Span:** "If at any time on or prior to the earlier of (i) December 31, 2007, or (ii) the date on which Global..."
- **Clause Text:** "(ii) those advisors, agents, contractors or lenders with a need to know the Confidential Information for the purpose of performing work related to the transactions contemplated by this Agreement; prov..."
- **Root Cause:** Atypical drafting vocabulary or domain-specific phrasing not captured by TF-IDF n-grams or regular expressions.

**FN #3** - Contract: `ASHWORTHINC_01_29_1999-EX-10.(D)-PROMOTI...`, Clause: `9`
- **Expert Target Span:** "The Company acknowledges that Nantz Communications' and      Nantz's obligations to CBS or any other..."
- **Clause Text:** "INDEMNIFICATION Neither Nantz Communications nor Nantz shall be liable for any obligations of the Company resulting directly or indirectly from the Endorsement of Ashworth Products. The Company shall ..."
- **Root Cause:** Atypical drafting vocabulary or domain-specific phrasing not captured by TF-IDF n-grams or regular expressions.

**FN #4** - Contract: `MPLXLP_06_17_2015-EX-10.1-TRANSPORTATION...`, Clause: `10.4`
- **Expert Target Span:** "Upon termination of this Agreement for reasons other than a default by Shipper, pursuant to any prov..."
- **Clause Text:** "..."
- **Root Cause:** Atypical drafting vocabulary or domain-specific phrasing not captured by TF-IDF n-grams or regular expressions.

**FN #5** - Contract: `IntegrityMediaInc_20010329_10-K405_EX-10...`, Clause: `3`
- **Expert Target Span:** "If for any reason, Integrity and TL are subject to lower "free                   goods" limits by an..."
- **Clause Text:** "a. Integrity will, upon receipt of approved purchase orders from TL, sell to TL in non-returnable box lot quantities, TL's requirements products rates calculated on the following basis (plus freight)...."
- **Root Cause:** Atypical drafting vocabulary or domain-specific phrasing not captured by TF-IDF n-grams or regular expressions.

---

### Label: `affiliate_license_licensor` (F1: 0.143, Support: 5)

#### False Positives (Predicted, but not in CUAD expert annotations):
**FP #1** - Contract: `CerenceInc_20191002_8-K_EX-10.4_11827494...`, Clause: `Schedule G.3.01`
- **Method:** `model` (Score: 0.9621)
- **Evidence:** "(a) Patents. Subject to the terms and conditions of this Agreement, as of the Distribution Date, Nuance hereby grants to SpinCo and the members of the..."
- **Clause Text:** "(a) Patents. Subject to the terms and conditions of this Agreement, as of the Distribution Date, Nuance hereby grants to SpinCo and the members of the SpinCo Group a worldwide, non-exclusive, fully pa..."
- **Root Cause:** Clause discusses related concepts or generic legal vocabulary that triggered model/rules without rising to CUAD's specific expert annotation threshold.

**FP #2** - Contract: `CerenceInc_20191002_8-K_EX-10.4_11827494...`, Clause: `Schedule G.4.01`
- **Method:** `model` (Score: 0.9469)
- **Evidence:** "(a) Patents. Subject to the terms and conditions of this Agreement, as of the Distribution Date, SpinCo hereby grants to Nuance and the members of the..."
- **Clause Text:** "(a) Patents. Subject to the terms and conditions of this Agreement, as of the Distribution Date, SpinCo hereby grants to Nuance and the members of the Nuance Group a worldwide, non-exclusive, fully pa..."
- **Root Cause:** Clause discusses related concepts or generic legal vocabulary that triggered model/rules without rising to CUAD's specific expert annotation threshold.

**FP #3** - Contract: `CytodynInc_20200109_10-Q_EX-10.5_1194163...`, Clause: `2.1`
- **Method:** `model` (Score: 0.7938)
- **Evidence:** "Grant of Licenses. (a) License to Vyera. CytoDyn hereby grants to Vyera, and Vyera hereby accepts, an exclusive royalty-bearing license (or sublicense..."
- **Clause Text:** "..."
- **Root Cause:** Clause discusses related concepts or generic legal vocabulary that triggered model/rules without rising to CUAD's specific expert annotation threshold.

**FP #4** - Contract: `RareElementResourcesLtd_20171019_SC 13D_...`, Clause: `U`
- **Method:** `model` (Score: 0.8121)
- **Evidence:** "to grant sublicenses to Affiliates) under the Patents to practice the methods therein described and claimed and to make and have made, use, offer to s..."
- **Clause Text:** "Exhibit 4 Rare Element Resources Ltd. EXECUTION COPY IP Rights Agreement INTELLECTUAL PROPERTY RIGHTS AGREEMENT Synchron, a California corporation having a principal place of business at 3550 General ..."
- **Root Cause:** Clause discusses related concepts or generic legal vocabulary that triggered model/rules without rising to CUAD's specific expert annotation threshold.

**FP #5** - Contract: `Sonos, Inc. - Manufacturing Agreement ...`, Clause: `3.3.1`
- **Method:** `model` (Score: 0.87)
- **Evidence:** "License to Manufacture. Subject to all terms and conditions of this Agreement, Sonos hereby grants to IAC and its Affiliates a non-exclusive, worldwid..."
- **Clause Text:** "..."
- **Root Cause:** Clause discusses related concepts or generic legal vocabulary that triggered model/rules without rising to CUAD's specific expert annotation threshold.

#### False Negatives (In CUAD expert annotations, but missed by detector):
**FN #1** - Contract: `Array BioPharma Inc. - LICENSE, DEVELOPM...`, Clause: `2.4`
- **Expert Target Span:** "If after the Effective Date, Array retains a Third Party Partner for the Product in one or more coun..."
- **Clause Text:** "17 (a) Array and Pierre Fabre Medicament SAS ("PFM") have previously entered into that certain Development and Commercialization Agreement, dated as of November 10, 2015 (such agreement, as subsequent..."
- **Root Cause:** Atypical drafting vocabulary or domain-specific phrasing not captured by TF-IDF n-grams or regular expressions.

**FN #2** - Contract: `Array BioPharma Inc. - LICENSE, DEVELOPM...`, Clause: `12.2`
- **Expert Target Span:** "Subject to the terms and conditions of this Agreement, following registration of the Product Tradema..."
- **Clause Text:** "..."
- **Root Cause:** Atypical drafting vocabulary or domain-specific phrasing not captured by TF-IDF n-grams or regular expressions.

**FN #3** - Contract: `CCAINDUSTRIESINC_04_14_2014-EX-10.1-OUTS...`, Clause: `5.03`
- **Expert Target Span:** "Solely to the extent necessary to enable Contractor to provide the Services in accordance with the t..."
- **Clause Text:** "..."
- **Root Cause:** Atypical drafting vocabulary or domain-specific phrasing not captured by TF-IDF n-grams or regular expressions.

**FN #4** - Contract: `BERKELEYLIGHTS,INC_06_26_2020-EX-10.12-C...`, Clause: `8.1`
- **Expert Target Span:** "With respect to any Intellectual Property developed by BLI or its Affiliates in collaboration or on ..."
- **Clause Text:** "..."
- **Root Cause:** Atypical drafting vocabulary or domain-specific phrasing not captured by TF-IDF n-grams or regular expressions.

---

### Label: `competitive_restriction_exception` (F1: 0.229, Support: 14)

#### False Positives (Predicted, but not in CUAD expert annotations):
**FP #1** - Contract: `TUNIUCORP_03_06_2014-EX-10-COOPERATION A...`, Clause: `2`
- **Method:** `model` (Score: 0.7736)
- **Evidence:** "Exclusive Cooperation..."
- **Clause Text:** "..."
- **Root Cause:** Clause discusses related concepts or generic legal vocabulary that triggered model/rules without rising to CUAD's specific expert annotation threshold.

**FP #2** - Contract: `CytodynInc_20200109_10-Q_EX-10.5_1194163...`, Clause: `1`
- **Method:** `model` (Score: 0.8091)
- **Evidence:** "Licensed Product in the Field in the Territory, including any registrations and licenses, regulatory drug lists, advertising and promotion documents s..."
- **Clause Text:** "1.1 "AAA" has the meaning set forth in Section 12.3(a). 1.2 "AAI Agreement" has the meaning set forth in Section 9.2(o). 1.3 "Affiliate" means, with respect to a particular Party, a Person that contro..."
- **Root Cause:** Clause discusses related concepts or generic legal vocabulary that triggered model/rules without rising to CUAD's specific expert annotation threshold.

**FP #3** - Contract: `CytodynInc_20200109_10-Q_EX-10.5_1194163...`, Clause: `2.5`
- **Method:** `model` (Score: 0.726)
- **Evidence:** "Field and Territory Restrictions. (a) Nothing in this Agreement is intended to, nor shall it, prevent CytoDyn from (i) Developing, Manufacturing and o..."
- **Clause Text:** "..."
- **Root Cause:** Clause discusses related concepts or generic legal vocabulary that triggered model/rules without rising to CUAD's specific expert annotation threshold.

**FP #4** - Contract: `WPPPLC_04_30_2020-EX-4.28-SERVICE AGREEM...`, Clause: `Schedule 3`
- **Method:** `model` (Score: 0.8918)
- **Evidence:** "any time during the Relevant Period. Relevant Capacity means either alone or jointly with another or others, whether as principal, agent, consultant, ..."
- **Clause Text:** "(j) encourage, assist or procure any Person to do anything which if done by the Executive would be a breach of sub clauses 1 (a) to (i). 2 The Executive agrees that updating his profile and/or connect..."
- **Root Cause:** Clause discusses related concepts or generic legal vocabulary that triggered model/rules without rising to CUAD's specific expert annotation threshold.

**FP #5** - Contract: `ELECTRAMECCANICA VEHICLES CORP. - Manufa...`, Clause: `2.5`
- **Method:** `model` (Score: 0.7808)
- **Evidence:** "other proprietary rights notices placed by EMV on or in the Products. 2.8 Exclusivity The manufacturing license granted in this Agreement is exclusive..."
- **Clause Text:** "..."
- **Root Cause:** Clause discusses related concepts or generic legal vocabulary that triggered model/rules without rising to CUAD's specific expert annotation threshold.

#### False Negatives (In CUAD expert annotations, but missed by detector):
**FN #1** - Contract: `WPPPLC_04_30_2020-EX-4.28-SERVICE AGREEM...`, Clause: `12`
- **Expert Target Span:** "(a) as holder or beneficial owner (for investment purposes only) of any class of securities in a com..."
- **Clause Text:** "During the Appointment, the Executive may not accept any employment with or appointment to any office, whether paid or unpaid, in relation to anybody, whether corporate or not (other than a Group Comp..."
- **Root Cause:** Atypical drafting vocabulary or domain-specific phrasing not captured by TF-IDF n-grams or regular expressions.

**FN #2** - Contract: `CERES,INC_01_25_2012-EX-10.20-Collaborat...`, Clause: `3`
- **Expert Target Span:** "IGER will have the right to make available germplasm of CERTAIN MISCANTHUS ACCESSIONS to third parti..."
- **Clause Text:** "CERES-IGER Collaboration Agreement Page 8 of 75 a. CERES will not unreasonably withhold its consent for collaborations with small companies (less than fifty (50) employees including world-wide affilia..."
- **Root Cause:** Atypical drafting vocabulary or domain-specific phrasing not captured by TF-IDF n-grams or regular expressions.

**FN #3** - Contract: `ASHWORTHINC_01_29_1999-EX-10.(D)-PROMOTI...`, Clause: `15`
- **Expert Target Span:** "Notwithstanding the foregoing Nantz shall be permitted to wear a Lynx hat or clothing logo when perf..."
- **Clause Text:** "16. The second Option to purchase up to an additional 40,000 shares upon payment of the aggregate Option Share Price for the number of Shares so purchased shall become exercisable on June 1, 2000, unl..."
- **Root Cause:** Atypical drafting vocabulary or domain-specific phrasing not captured by TF-IDF n-grams or regular expressions.

**FN #4** - Contract: `VAXCYTE,INC_05_22_2020-EX-10.19-SUPPLY A...`, Clause: `2.20`
- **Expert Target Span:** "SutroVax agrees to purchase all its requirements of Extract from Sutro in accordance with this Agree..."
- **Clause Text:** "..."
- **Root Cause:** Atypical drafting vocabulary or domain-specific phrasing not captured by TF-IDF n-grams or regular expressions.

**FN #5** - Contract: `AIRTECHINTERNATIONALGROUPINC_05_08_2000-...`, Clause: `16.04`
- **Expert Target Span:** "AIRSOPURE covenants and agrees that the restrictions set forth above in Paragraphs 16.02.C and 16.03..."
- **Clause Text:** "..."
- **Root Cause:** Atypical drafting vocabulary or domain-specific phrasing not captured by TF-IDF n-grams or regular expressions.

---

### Label: `joint_ip_ownership` (F1: 0.250, Support: 13)

#### False Positives (Predicted, but not in CUAD expert annotations):
**FP #1** - Contract: `BERKELEYLIGHTS,INC_06_26_2020-EX-10.12-C...`, Clause: `8.3`
- **Method:** `model` (Score: 0.7885)
- **Evidence:** "Ownership of Remaining Collaboration Intellectual Property. Subject to Section 8.2 (Ownership of Ginkgo Inventions and BLI Inventions), as between the..."
- **Clause Text:** "..."
- **Root Cause:** Clause discusses related concepts or generic legal vocabulary that triggered model/rules without rising to CUAD's specific expert annotation threshold.

#### False Negatives (In CUAD expert annotations, but missed by detector):
**FN #1** - Contract: `INKTOMICORP_06_08_1998-EX-10.14-SOFTWARE...`, Clause: `2.3.2`
- **Expert Target Span:** "All Usage Data shall be owned jointly by Microsoft and





Inktomi, and Inktomi hereby irrevocably ..."
- **Clause Text:** "Inktomi, and Inktomi hereby irrevocably assigns to Microsoft an [*] interest therein. However, Inktomi shall not have the right to share any of such Usage Data with third parties (except that Inktomi ..."
- **Root Cause:** Atypical drafting vocabulary or domain-specific phrasing not captured by TF-IDF n-grams or regular expressions.

**FN #2** - Contract: `CERES,INC_01_25_2012-EX-10.20-Collaborat...`, Clause: `3.3.3`
- **Expert Target Span:** ""JOINT INTELLECTUAL PROPERTY" shall mean (a) all patentable inventions conceived, discovered, develo..."
- **Clause Text:** "4.1 "JOINT INTELLECTUAL PROPERTY" shall mean (a) all patentable inventions conceived, discovered, developed and/or reduced to practice (i) jointly by one or more employees, agents, or students of CERE..."
- **Root Cause:** Atypical drafting vocabulary or domain-specific phrasing not captured by TF-IDF n-grams or regular expressions.

**FN #3** - Contract: `CERES,INC_01_25_2012-EX-10.20-Collaborat...`, Clause: `4.6`
- **Expert Target Span:** "CERES and IGER shall have an undivided interest in JOINT INTELLECTUAL PROPERTY. Consequently, any an..."
- **Clause Text:** "..."
- **Root Cause:** Atypical drafting vocabulary or domain-specific phrasing not captured by TF-IDF n-grams or regular expressions.

**FN #4** - Contract: `CERES,INC_01_25_2012-EX-10.20-Collaborat...`, Clause: `4.7`
- **Expert Target Span:** "Each Party will notify the other Party, in writing ("INVENTION NOTICE"), within thirty (30) days of ..."
- **Clause Text:** "..."
- **Root Cause:** Atypical drafting vocabulary or domain-specific phrasing not captured by TF-IDF n-grams or regular expressions.

**FN #5** - Contract: `CERES,INC_01_25_2012-EX-10.20-Collaborat...`, Clause: `4.8.2`
- **Expert Target Span:** "The ADMINISTERING PARTY shall keep the non-administering Party advised as to all developments with r..."
- **Clause Text:** "..."
- **Root Cause:** Atypical drafting vocabulary or domain-specific phrasing not captured by TF-IDF n-grams or regular expressions.

---

### Label: `volume_restriction` (F1: 0.276, Support: 22)

#### False Positives (Predicted, but not in CUAD expert annotations):
**FP #1** - Contract: `BELLICUMPHARMACEUTICALS,INC_05_07_2019-E...`, Clause: `5.2`
- **Method:** `rules` (Score: 0.9)
- **Evidence:** "Volume Limitations. (a) Subject to Bellicum's adherence to its Forecast obligations pursuant to Section 5.1 abov..."
- **Clause Text:** "(a) Subject to Bellicum's adherence to its Forecast obligations pursuant to Section 5.1 above, or as specifically modified in a specific Module, Miltenyi shall meet the demands of any Purchase Orders ..."
- **Root Cause:** Clause discusses related concepts or generic legal vocabulary that triggered model/rules without rising to CUAD's specific expert annotation threshold.

**FP #2** - Contract: `BELLICUMPHARMACEUTICALS,INC_05_07_2019-E...`, Clause: `6.2`
- **Method:** `rules` (Score: 0.9)
- **Evidence:** "Miltenyi Products shall be fulfilled, even if the volume limitations defined in Section 5.2 are exceeded, by Miltenyi in good faith and as soon as pra..."
- **Clause Text:** "..."
- **Root Cause:** Clause discusses related concepts or generic legal vocabulary that triggered model/rules without rising to CUAD's specific expert annotation threshold.

**FP #3** - Contract: `BellringBrandsInc_20190920_S-1_EX-10.12_...`, Clause: `2`
- **Method:** `rules` (Score: 0.9)
- **Evidence:** "ood faith estimated maximum monthly unit volume ("Maximum Volume") for each Facility during such [***] period. Modifications to the Maximum Volume sha..."
- **Clause Text:** "(a) Heritage shall produce the products described on Schedule A attached hereto, as may be amended by the Parties hereafter from time to time (the "Products"), for Premier at [***] Heritage's or Herit..."
- **Root Cause:** Clause discusses related concepts or generic legal vocabulary that triggered model/rules without rising to CUAD's specific expert annotation threshold.

#### False Negatives (In CUAD expert annotations, but missed by detector):
**FN #1** - Contract: `SUMMAFOURINC_06_19_1998-EX-10.3-SOFTWARE...`, Clause: `3.2`
- **Expert Target Span:** "The CAP for Licensed Technology shall be cumulative across all "Supported Processors" (including "ad..."
- **Clause Text:** "(A) "Supported Processors": If D2 offers or plans to offer all or part of Licensed Technology on a processor ("Supported Processor") different from the Texas Instruments (TI) TMS320C54x family of proc..."
- **Root Cause:** Atypical drafting vocabulary or domain-specific phrasing not captured by TF-IDF n-grams or regular expressions.

**FN #2** - Contract: `SUMMAFOURINC_06_19_1998-EX-10.3-SOFTWARE...`, Clause: `Exhibit A.3`
- **Expert Target Span:** "There shall be fewer than 1 talkoff in 5 hours of voice when the          detector is programmed wit..."
- **Clause Text:** "A.5.3.1.9 Unknown Tone Any single tone, dual tone, amplitude modulated tone or single tone sequence that is not classified as a CP, SIT, CNG or modem ANS tone, shall be reported as an unknown tone. Pe..."
- **Root Cause:** Atypical drafting vocabulary or domain-specific phrasing not captured by TF-IDF n-grams or regular expressions.

**FN #3** - Contract: `MPLXLP_06_17_2015-EX-10.1-TRANSPORTATION...`, Clause: `3.6`
- **Expert Target Span:** "If, during any Quarter of the Contract Year, Shipper deliveries on the Pipeline exceed the applicabl..."
- **Clause Text:** "..."
- **Root Cause:** Atypical drafting vocabulary or domain-specific phrasing not captured by TF-IDF n-grams or regular expressions.

**FN #4** - Contract: `MPLXLP_06_17_2015-EX-10.1-TRANSPORTATION...`, Clause: `6.6`
- **Expert Target Span:** "The amount of expansion capacity available for volume commitments pursuant to this Section 6.6 shall..."
- **Clause Text:** "(a) MPL will provide each Shipper with notice of such proposed expansion not less than one hundred and eighty (180) days prior to the expected in-service date of such proposed expansion ("Expansion No..."
- **Root Cause:** Atypical drafting vocabulary or domain-specific phrasing not captured by TF-IDF n-grams or regular expressions.

**FN #5** - Contract: `DIVERSINETCORP_03_01_2012-EX-4-RESELLER ...`, Clause: `1`
- **Expert Target Span:** "Diversinet will arrange for the initial personal technical and sales instruction of up to three (3) ..."
- **Clause Text:** "..."
- **Root Cause:** Atypical drafting vocabulary or domain-specific phrasing not captured by TF-IDF n-grams or regular expressions.

---
