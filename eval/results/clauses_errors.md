# Clause Classification Error Analysis (TEST Split)

> [!NOTE]
> **Notice on Ground-Truth Recalibration**: Initial runs of this error analysis were collected during Preliminary Looks 1 and 2, which used inflated token-overlap alignment. For the official Third Look metrics evaluated on corrected character-offset labels, refer to [`backend/models/clauses/v1/metrics.json`](file:///c:/Users/Loq/Desktop/Projects/legal-doc/backend/models/clauses/v1/metrics.json) and [`eval/results/clauses_benchmark.json`](file:///c:/Users/Loq/Desktop/Projects/legal-doc/eval/results/clauses_benchmark.json).

Honest error analysis on the 20% unseen CUAD test split (102 contracts, 2,788 clauses).
Below are the 5 weakest labels by F1 score (with support >= 5), with concrete False Positive
and False Negative examples analyzing failure modes.

## Summary of 5 Weakest Labels

| Label | Support | Pred Count | Precision (95% CI) | Recall (95% CI) | F1 |
|---|---|---|---|---|---|
| `no_solicit_of_customers` | 31 | 4 | 0.000 [0.00, 0.49] | 0.000 [0.00, 0.11] | 0.000 |
| `unlimited_all_you_can_eat_license` | 14 | 8 | 0.000 [0.00, 0.32] | 0.000 [0.00, 0.22] | 0.000 |
| `competitive_restriction_exception` | 131 | 20 | 0.050 [0.01, 0.24] | 0.008 [0.00, 0.04] | 0.013 |
| `price_restrictions` | 50 | 21 | 0.048 [0.01, 0.23] | 0.020 [0.00, 0.10] | 0.028 |
| `third_party_beneficiary` | 49 | 13 | 0.077 [0.01, 0.33] | 0.020 [0.00, 0.11] | 0.032 |

---

## Detailed Error Analysis per Weak Label

### Label: `no_solicit_of_customers` (F1: 0.000, Support: 31)

#### False Positives (Predicted, but not in CUAD expert annotations):
**FP #1** - Contract: `NETGEAR,INC_04_21_2003-EX-10.16-AMENDMEN...`, Clause: `19`
- **Method:** `model` (Score: 0.9775)
- **Evidence:** "the NETGEAR Price List in effect on the Effective Date of this Agreement is [*] off of the then current NETGEAR list price. Distributor agrees that th..."
- **Clause Text:** "This Agreement, including its attachment and order acknowledgments under the Agreement, constitutes the entire agreement between Distributor and NETGEAR with respect to the purchase, resale and distri..."
- **Root Cause:** Clause discusses related concepts or generic legal vocabulary that triggered model/rules without rising to CUAD's specific expert annotation threshold.

**FP #2** - Contract: `GSVINC_05_15_1998-EX-10-SPONSORSHIP AGRE...`, Clause: `12`
- **Method:** `model` (Score: 0.6784)
- **Evidence:** "a) For the purposes of this Agreement, "Confidential Information" means information about the disclosing party's (or its suppliers') business or activ..."
- **Clause Text:** "a) For the purposes of this Agreement, "Confidential Information" means information about the disclosing party's (or its suppliers') business or activities that is proprietary and confidential, which ..."
- **Root Cause:** Clause discusses related concepts or generic legal vocabulary that triggered model/rules without rising to CUAD's specific expert annotation threshold.

**FP #3** - Contract: `NETGEAR,INC_04_21_2003-EX-10.16- AMENDME...`, Clause: `0`
- **Method:** `model` (Score: 0.8903)
- **Evidence:** "This Amendment is entered into effective October 1,1996 ("Amendment Date") by and between NETGEAR, Inc. ("NETGEAR"), a wholly owned subsidiary of Bay ..."
- **Clause Text:** "This Amendment is entered into effective October 1,1996 ("Amendment Date") by and between NETGEAR, Inc. ("NETGEAR"), a wholly owned subsidiary of Bay Networks, Inc., and Ingram Micro ("Distributor") a..."
- **Root Cause:** Clause discusses related concepts or generic legal vocabulary that triggered model/rules without rising to CUAD's specific expert annotation threshold.

**FP #4** - Contract: `VITAMINSHOPPECOMINC_09_13_1999-EX-10.26-...`, Clause: `12`
- **Method:** `model` (Score: 0.7698)
- **Evidence:** "a) For the purposes of this Agreement, "Confidential Information" means information about the disclosing party's (or its suppliers') business or activ..."
- **Clause Text:** "a) For the purposes of this Agreement, "Confidential Information" means information about the disclosing party's (or its suppliers') business or activities that is proprietary and confidential, which ..."
- **Root Cause:** Clause discusses related concepts or generic legal vocabulary that triggered model/rules without rising to CUAD's specific expert annotation threshold.

#### False Negatives (In CUAD expert annotations, but missed by detector):
**FN #1** - Contract: `WPPPLC_04_30_2020-EX-4.28-SERVICE AGREEM...`, Clause: `0`
- **Expert Target Span:** "(c) solicit or attempt to solicit, canvass, interfere with or entice away from the Company or any Re..."
- **Clause Text:** "Exhibit 4.28 SERVICE AGREEMENT 1 OCTOBER 2019 WPP 2005 LIMITED and JOHN ROGERS CONTENTS Clause Page 1. Interpretation 3 2. Commencement of Appointment 4 3. Executive's Duties 4 4. Place of Work 5 5. W..."
- **Root Cause:** Atypical drafting vocabulary or domain-specific phrasing not captured by TF-IDF n-grams or regular expressions.

**FN #2** - Contract: `WPPPLC_04_30_2020-EX-4.28-SERVICE AGREEM...`, Clause: `2`
- **Expert Target Span:** "(c) solicit or attempt to solicit, canvass, interfere with or entice away from the Company or any Re..."
- **Clause Text:** "(l) comply with all requirements, recommendations or regulations, as amended from time to time, of the UK Listing Authority, the Market Abuse Regulation (596/2014/EU), the FCA and all other regulatory..."
- **Root Cause:** Atypical drafting vocabulary or domain-specific phrasing not captured by TF-IDF n-grams or regular expressions.

**FN #3** - Contract: `WPPPLC_04_30_2020-EX-4.28-SERVICE AGREEM...`, Clause: `10`
- **Expert Target Span:** "(c) solicit or attempt to solicit, canvass, interfere with or entice away from the Company or any Re..."
- **Clause Text:** "During the Appointment, the Executive may not accept any employment with or appointment to any office, whether paid or unpaid, in relation to anybody, whether corporate or not (other than a Group Comp..."
- **Root Cause:** Atypical drafting vocabulary or domain-specific phrasing not captured by TF-IDF n-grams or regular expressions.

**FN #4** - Contract: `WPPPLC_04_30_2020-EX-4.28-SERVICE AGREEM...`, Clause: `15`
- **Expert Target Span:** "(c) solicit or attempt to solicit, canvass, interfere with or entice away from the Company or any Re..."
- **Clause Text:** "any Group Company into disrepute or affects or is likely to affect prejudicially the interests of the Company or the Group; (c) is convicted of an arrestable offence (other than a road traffic offence..."
- **Root Cause:** Atypical drafting vocabulary or domain-specific phrasing not captured by TF-IDF n-grams or regular expressions.

**FN #5** - Contract: `WPPPLC_04_30_2020-EX-4.28-SERVICE AGREEM...`, Clause: `21`
- **Expert Target Span:** "(c) solicit or attempt to solicit, canvass, interfere with or entice away from the Company or any Re..."
- **Clause Text:** "The Company is not a party to any collective agreement which affects the Executive's employment. 22. GENERAL 22.1 This Agreement is governed by and construed in accordance with English law, save where..."
- **Root Cause:** Atypical drafting vocabulary or domain-specific phrasing not captured by TF-IDF n-grams or regular expressions.

---

### Label: `unlimited_all_you_can_eat_license` (F1: 0.000, Support: 14)

#### False Positives (Predicted, but not in CUAD expert annotations):
**FP #1** - Contract: `INKTOMICORP_06_08_1998-EX-10.14-SOFTWARE...`, Clause: `10.4`
- **Method:** `model` (Score: 0.4685)
- **Evidence:** "(a) Inktomi is in [*] of this Agreement (excluding Section [*]) and fails to cure that breach within [*] ([*]) days after written notice thereof; or (..."
- **Clause Text:** "(a) Inktomi is in [*] of this Agreement (excluding Section [*]) and fails to cure that breach within [*] ([*]) days after written notice thereof; or (b) Inktomi is in material breach of Section [*]; o..."
- **Root Cause:** Clause discusses related concepts or generic legal vocabulary that triggered model/rules without rising to CUAD's specific expert annotation threshold.

**FP #2** - Contract: `INKTOMICORP_06_08_1998-EX-10.14-SOFTWARE...`, Clause: `Exhibit D`
- **Method:** `model` (Score: 0.3828)
- **Evidence:** "INKTOMI MAINTENANCE EMPLOYEES [*] and [*] [*]=CERTAIN INFORMATION IN THIS EXHIBIT HAS BEEN OMITTED AND FILED SEPARATELY WITH THE COMMISSION. CONFIDENT..."
- **Clause Text:** "INKTOMI MAINTENANCE EMPLOYEES [*] and [*] [*]=CERTAIN INFORMATION IN THIS EXHIBIT HAS BEEN OMITTED AND FILED SEPARATELY WITH THE COMMISSION. CONFIDENTIAL TREATMENT HAS BEEN REQUESTED WITH RESPECT TO T..."
- **Root Cause:** Clause discusses related concepts or generic legal vocabulary that triggered model/rules without rising to CUAD's specific expert annotation threshold.

**FP #3** - Contract: `GpaqAcquisitionHoldingsInc_20200123_S-4A...`, Clause: `5.2`
- **Method:** `model` (Score: 0.4988)
- **Evidence:** "subject to a joint venture agreement or other mutual arrangement between the Parties. 7.10 Entire Agreement. This Agreement constitutes the entire agr..."
- **Clause Text:** "10 (b) Each Receiving Party agrees: (i) not to disclose, make public, or authorize any disclosure or publication of such Confidential Information of the Disclosing Party except as expressly permitted ..."
- **Root Cause:** Clause discusses related concepts or generic legal vocabulary that triggered model/rules without rising to CUAD's specific expert annotation threshold.

**FP #4** - Contract: `SUMMAFOURINC_06_19_1998-EX-10.3-SOFTWARE...`, Clause: `2.2`
- **Method:** `model` (Score: 0.4367)
- **Evidence:** "been paid for by Licensee's end-user customer in the prior quarter. To the extent Licensee accepts returns or is required to provide refunds to its cu..."
- **Clause Text:** "(i) Subject to the terms and conditions of this Agreement, D2 hereby grants LICENSEE a perpetual non-exclusive, worldwide license, to use Licensed Technology in Object Code format only as an incorpora..."
- **Root Cause:** Clause discusses related concepts or generic legal vocabulary that triggered model/rules without rising to CUAD's specific expert annotation threshold.

**FP #5** - Contract: `SUMMAFOURINC_06_19_1998-EX-10.3-SOFTWARE...`, Clause: `10.1`
- **Method:** `model` (Score: 0.3711)
- **Evidence:** "13 adjudicatively determined to be, or in either party's reasonable opinion will be, the subject of any claim, suit or proceeding for infringement of ..."
- **Clause Text:** "13 adjudicatively determined to be, or in either party's reasonable opinion will be, the subject of any claim, suit or proceeding for infringement of any third party's patent, copyright or trade secre..."
- **Root Cause:** Clause discusses related concepts or generic legal vocabulary that triggered model/rules without rising to CUAD's specific expert annotation threshold.

#### False Negatives (In CUAD expert annotations, but missed by detector):
**FN #1** - Contract: `ASIANDRAGONGROUPINC_08_11_2005-EX-10.5-R...`, Clause: `0`
- **Expert Target Span:** "Table 1

  Business Partner Pricing

VoIP Services One-Time Fee Monthly Service Fee

VoIP Connectivi..."
- **Clause Text:** "Exhibit 10.5 Reseller Agreement This Agreement is made and entered into by and between 695014 B.C. Ltd. dba Galaxy Telecom, having a principal office at 200 - 375 Water Street, Vancouver, British Colu..."
- **Root Cause:** Atypical drafting vocabulary or domain-specific phrasing not captured by TF-IDF n-grams or regular expressions.

**FN #2** - Contract: `ASIANDRAGONGROUPINC_08_11_2005-EX-10.5-R...`, Clause: `5`
- **Expert Target Span:** "Note 4 Unlimited calling FROM Virtual Calling Zone only. Long distance charges apply when calling to..."
- **Clause Text:** "6. PRODUCTS 6.1 Approved Products Galaxy shall, at its sole discretion, determine the technical specifications and the brand and model of those devices which it will support in providing the Services ..."
- **Root Cause:** Atypical drafting vocabulary or domain-specific phrasing not captured by TF-IDF n-grams or regular expressions.

**FN #3** - Contract: `ASIANDRAGONGROUPINC_08_11_2005-EX-10.5-R...`, Clause: `14`
- **Expert Target Span:** "Table 1

  Business Partner Pricing

VoIP Services One-Time Fee Monthly Service Fee

VoIP Connectivi..."
- **Clause Text:** "IN WITNESS WHEREOF, the parties have caused this Agreement to be executed by their duly authorized representatives as of the date first written above: 695014 B.C. LTD. GALAXY TELNET SRL Per: "Peter Wi..."
- **Root Cause:** Atypical drafting vocabulary or domain-specific phrasing not captured by TF-IDF n-grams or regular expressions.

**FN #4** - Contract: `NakedBrandGroupInc_20150731_POS AM (on S...`, Clause: `3`
- **Expert Target Span:** "During the Term, Naked shall have the right in the Territory to the unlimited broadcast use and re-u..."
- **Clause Text:** "During the Term and subject to the limitations set forth in this Agreement, Naked shall have an exclusive right and license in the Territory to use Athlete's name, nickname, initials, autograph, image..."
- **Root Cause:** Atypical drafting vocabulary or domain-specific phrasing not captured by TF-IDF n-grams or regular expressions.

**FN #5** - Contract: `NakedBrandGroupInc_20150731_POS AM (on S...`, Clause: `5`
- **Expert Target Span:** "During the Term, Naked shall have the right in the Territory to the unlimited broadcast use and re-u..."
- **Clause Text:** "A. During the first Contract Year, Wade will be available for (i) one production day for the purpose of creating marketing assets for Naked Products for unlimited use in advertisements and the media a..."
- **Root Cause:** Atypical drafting vocabulary or domain-specific phrasing not captured by TF-IDF n-grams or regular expressions.

---

### Label: `competitive_restriction_exception` (F1: 0.013, Support: 131)

#### False Positives (Predicted, but not in CUAD expert annotations):
**FP #1** - Contract: `ELECTRAMECCANICA VEHICLES CORP. - Manufa...`, Clause: `10.8`
- **Method:** `model` (Score: 0.8166)
- **Evidence:** "IN WITNESS WHEREOF, each party to this agreement has caused it to be executed on the date indicated above. ELECTRAMECCANICA VEHICLES CORP. s/ Jerry Kr..."
- **Clause Text:** "IN WITNESS WHEREOF, each party to this agreement has caused it to be executed on the date indicated above. ELECTRAMECCANICA VEHICLES CORP. s/ Jerry Kroll Name: Jerry Kroll Title: CEO and General Manag..."
- **Root Cause:** Clause discusses related concepts or generic legal vocabulary that triggered model/rules without rising to CUAD's specific expert annotation threshold.

**FP #2** - Contract: `GSVINC_05_15_1998-EX-10-SPONSORSHIP AGRE...`, Clause: `0`
- **Method:** `model` (Score: 0.9662)
- **Evidence:** "TREATMENT WITH RESPECT TO CERTAIN PORTIONS OF THIS AGREEMENT ACCORDINGLY, CERTAIN PORTIONS HAVE BEEN REDACTED Exhibit 10.1 SPONSORSHIP AGREEMENT This ..."
- **Clause Text:** "TREATMENT WITH RESPECT TO CERTAIN PORTIONS OF THIS AGREEMENT ACCORDINGLY, CERTAIN PORTIONS HAVE BEEN REDACTED Exhibit 10.1 SPONSORSHIP AGREEMENT This agreement ("Agreement") is entered into as of the ..."
- **Root Cause:** Clause discusses related concepts or generic legal vocabulary that triggered model/rules without rising to CUAD's specific expert annotation threshold.

**FP #3** - Contract: `GSVINC_05_15_1998-EX-10-SPONSORSHIP AGRE...`, Clause: `6`
- **Method:** `model` (Score: 0.82)
- **Evidence:** "a) Client and Excite will use reasonable efforts to implement the display of the promotional placements and advertising described in the Agreement by ..."
- **Clause Text:** "a) Client and Excite will use reasonable efforts to implement the display of the promotional placements and advertising described in the Agreement by April 15, 1998 (the "Launch Date"). b) Excite will..."
- **Root Cause:** Clause discusses related concepts or generic legal vocabulary that triggered model/rules without rising to CUAD's specific expert annotation threshold.

**FP #4** - Contract: `GSVINC_05_15_1998-EX-10-SPONSORSHIP AGRE...`, Clause: `8`
- **Method:** `model` (Score: 0.8917)
- **Evidence:** "Unless required by law, neither party will make any public statement, press release or other announcement relating to the terms of or existence of thi..."
- **Clause Text:** "Unless required by law, neither party will make any public statement, press release or other announcement relating to the terms of or existence of this Agreement without the prior written approval of ..."
- **Root Cause:** Clause discusses related concepts or generic legal vocabulary that triggered model/rules without rising to CUAD's specific expert annotation threshold.

**FP #5** - Contract: `GSVINC_05_15_1998-EX-10-SPONSORSHIP AGRE...`, Clause: `10`
- **Method:** `model` (Score: 0.8561)
- **Evidence:** "a) Client will retain all right, title and interest in and to its trademarks, service marks and trade names worldwide, subject to the limited license ..."
- **Clause Text:** "a) Client will retain all right, title and interest in and to its trademarks, service marks and trade names worldwide, subject to the limited license granted to Excite hereunder. b) Excite will retain..."
- **Root Cause:** Clause discusses related concepts or generic legal vocabulary that triggered model/rules without rising to CUAD's specific expert annotation threshold.

#### False Negatives (In CUAD expert annotations, but missed by detector):
**FN #1** - Contract: `WPPPLC_04_30_2020-EX-4.28-SERVICE AGREEM...`, Clause: `0`
- **Expert Target Span:** "(a) as holder or beneficial owner (for investment purposes only) of any class of securities in a com..."
- **Clause Text:** "Exhibit 4.28 SERVICE AGREEMENT 1 OCTOBER 2019 WPP 2005 LIMITED and JOHN ROGERS CONTENTS Clause Page 1. Interpretation 3 2. Commencement of Appointment 4 3. Executive's Duties 4 4. Place of Work 5 5. W..."
- **Root Cause:** Atypical drafting vocabulary or domain-specific phrasing not captured by TF-IDF n-grams or regular expressions.

**FN #2** - Contract: `WPPPLC_04_30_2020-EX-4.28-SERVICE AGREEM...`, Clause: `2`
- **Expert Target Span:** "(a) as holder or beneficial owner (for investment purposes only) of any class of securities in a com..."
- **Clause Text:** "(l) comply with all requirements, recommendations or regulations, as amended from time to time, of the UK Listing Authority, the Market Abuse Regulation (596/2014/EU), the FCA and all other regulatory..."
- **Root Cause:** Atypical drafting vocabulary or domain-specific phrasing not captured by TF-IDF n-grams or regular expressions.

**FN #3** - Contract: `WPPPLC_04_30_2020-EX-4.28-SERVICE AGREEM...`, Clause: `10`
- **Expert Target Span:** "(a) as holder or beneficial owner (for investment purposes only) of any class of securities in a com..."
- **Clause Text:** "During the Appointment, the Executive may not accept any employment with or appointment to any office, whether paid or unpaid, in relation to anybody, whether corporate or not (other than a Group Comp..."
- **Root Cause:** Atypical drafting vocabulary or domain-specific phrasing not captured by TF-IDF n-grams or regular expressions.

**FN #4** - Contract: `WPPPLC_04_30_2020-EX-4.28-SERVICE AGREEM...`, Clause: `15`
- **Expert Target Span:** "(a) as holder or beneficial owner (for investment purposes only) of any class of securities in a com..."
- **Clause Text:** "any Group Company into disrepute or affects or is likely to affect prejudicially the interests of the Company or the Group; (c) is convicted of an arrestable offence (other than a road traffic offence..."
- **Root Cause:** Atypical drafting vocabulary or domain-specific phrasing not captured by TF-IDF n-grams or regular expressions.

**FN #5** - Contract: `WPPPLC_04_30_2020-EX-4.28-SERVICE AGREEM...`, Clause: `21`
- **Expert Target Span:** "(a) as holder or beneficial owner (for investment purposes only) of any class of securities in a com..."
- **Clause Text:** "The Company is not a party to any collective agreement which affects the Executive's employment. 22. GENERAL 22.1 This Agreement is governed by and construed in accordance with English law, save where..."
- **Root Cause:** Atypical drafting vocabulary or domain-specific phrasing not captured by TF-IDF n-grams or regular expressions.

---

### Label: `price_restrictions` (F1: 0.028, Support: 50)

#### False Positives (Predicted, but not in CUAD expert annotations):
**FP #1** - Contract: `ELECTRAMECCANICA VEHICLES CORP. - Manufa...`, Clause: `1`
- **Method:** `model` (Score: 0.2625)
- **Evidence:** "and manufacturing of the Product only in accordance with the Specifications. In addition, EMV shall provide the Manufacturer with the performance test..."
- **Clause Text:** "License to EMV Firmware. Subject to the terms of this Agreement, subject to Manufacturer meeting EMV's requirements for quality, price and lead- time, EMV hereby grants Manufacturer an exclusive, non-..."
- **Root Cause:** Clause discusses related concepts or generic legal vocabulary that triggered model/rules without rising to CUAD's specific expert annotation threshold.

**FP #2** - Contract: `AzulSa_20170303_F-1A_EX-10.3_9943903_EX-...`, Clause: `0`
- **Method:** `model` (Score: 0.2594)
- **Evidence:** "be considered. In any case, any notice or communication shall be also transmitted by an e-mail with attached copy of such (in format PDF or similar su..."
- **Clause Text:** "Execution version Exhibit 10.3 CONFIDENTIAL TREATMENT REQUESTED - REDACTED COPY Confidential Treatment has been requested for portions of this Exhibit. Confidential portions of this Exhibit are design..."
- **Root Cause:** Clause discusses related concepts or generic legal vocabulary that triggered model/rules without rising to CUAD's specific expert annotation threshold.

**FP #3** - Contract: `BELLICUMPHARMACEUTICALS,INC_05_07_2019-E...`, Clause: `5.1`
- **Method:** `model` (Score: 0.2381)
- **Evidence:** "production planning for Miltenyi Products during such period. Each Long-Term Forecast shall show anticipated quantity requirements on an annual basis...."
- **Clause Text:** "(a) Rolling Monthly Forecast; Firm Zone. Within [...***...] Business Days of the Effective Date, and thereafter by the [...***...] day of each Calendar Month during the Term, Bellicum shall submit a m..."
- **Root Cause:** Clause discusses related concepts or generic legal vocabulary that triggered model/rules without rising to CUAD's specific expert annotation threshold.

**FP #4** - Contract: `BELLICUMPHARMACEUTICALS,INC_05_07_2019-E...`, Clause: `6.1`
- **Method:** `model` (Score: 0.4552)
- **Evidence:** "(a) Each quantity of Miltenyi Product(s) ordered by Bellicum in a particular Purchase Order pursuant to this Agreement shall be delivered FCA (Incoter..."
- **Clause Text:** "(a) Each quantity of Miltenyi Product(s) ordered by Bellicum in a particular Purchase Order pursuant to this Agreement shall be delivered FCA (Incoterms 2010) Miltenyi's Facility by delivery 20 of the..."
- **Root Cause:** Clause discusses related concepts or generic legal vocabulary that triggered model/rules without rising to CUAD's specific expert annotation threshold.

**FP #5** - Contract: `ACCURAYINC_09_01_2010-EX-10.31-DISTRIBUT...`, Clause: `3.13`
- **Method:** `model` (Score: 0.24)
- **Evidence:** "the services required to be performed under such Service Agreement. 4.9. Customer Training. If training of Customer's personnel is included in a Purch..."
- **Clause Text:** "connection with Multiple LINAC or Multi-Modality Purchases, including any upgrades to or expanded usage of the Products; provided, however, that if Accuray does not have a direct presence in or Accura..."
- **Root Cause:** Clause discusses related concepts or generic legal vocabulary that triggered model/rules without rising to CUAD's specific expert annotation threshold.

#### False Negatives (In CUAD expert annotations, but missed by detector):
**FN #1** - Contract: `GpaqAcquisitionHoldingsInc_20200123_S-4A...`, Clause: `0`
- **Expert Target Span:** "To the extent that the Village Media Company and PFHOF work collaboratively on media projects, the E..."
- **Clause Text:** "Exhibit 10.6 EXECUTION COPY MEDIA LICENSE AGREEMENT THIS MEDIA LICENSE AGREEMENT (this "Agreement") is made and effective as of the date of the Closing (as defined in the Merger Agreement (as defined ..."
- **Root Cause:** Atypical drafting vocabulary or domain-specific phrasing not captured by TF-IDF n-grams or regular expressions.

**FN #2** - Contract: `GpaqAcquisitionHoldingsInc_20200123_S-4A...`, Clause: `5.2`
- **Expert Target Span:** "To the extent that the Village Media Company and PFHOF work collaboratively on media projects, the E..."
- **Clause Text:** "10 (b) Each Receiving Party agrees: (i) not to disclose, make public, or authorize any disclosure or publication of such Confidential Information of the Disclosing Party except as expressly permitted ..."
- **Root Cause:** Atypical drafting vocabulary or domain-specific phrasing not captured by TF-IDF n-grams or regular expressions.

**FN #3** - Contract: `ParatekPharmaceuticalsInc_20170505_10-KA...`, Clause: `3.10`
- **Expert Target Span:** "During the Term of this Agreement, either Party may request an increase or decrease of the Fees spec..."
- **Clause Text:** "At any time during the Term, Customer may provide written notice to Supplier of its intent to expand the Territory under this Agreement to include one or more additional countries or territories. Prom..."
- **Root Cause:** Atypical drafting vocabulary or domain-specific phrasing not captured by TF-IDF n-grams or regular expressions.

**FN #4** - Contract: `ParatekPharmaceuticalsInc_20170505_10-KA...`, Clause: `3.11`
- **Expert Target Span:** "During the Term of this Agreement, either Party may request an increase or decrease of the Fees spec..."
- **Clause Text:** "In the event Customer delivers a written request to Supplier requesting that Supplier engage in negotiations with a Customer Licensee on the terms of a definitive agreement pursuant to which Supplier ..."
- **Root Cause:** Atypical drafting vocabulary or domain-specific phrasing not captured by TF-IDF n-grams or regular expressions.

**FN #5** - Contract: `ParatekPharmaceuticalsInc_20170505_10-KA...`, Clause: `3.12`
- **Expert Target Span:** "During the Term of this Agreement, either Party may request an increase or decrease of the Fees spec..."
- **Clause Text:** "At any time during the Term, Customer may elect to qualify one or more alternative Manufacturing facilities (whether owned by a Third Party, Customer or by one of Customer's Affiliates) to Manufacture..."
- **Root Cause:** Atypical drafting vocabulary or domain-specific phrasing not captured by TF-IDF n-grams or regular expressions.

---

### Label: `third_party_beneficiary` (F1: 0.032, Support: 49)

#### False Positives (Predicted, but not in CUAD expert annotations):
**FP #1** - Contract: `MetLife, Inc. - Remarketing Agreement...`, Clause: `5`
- **Method:** `model` (Score: 0.8385)
- **Evidence:** "the Disclosure Package, the effect of which, in any such case described in clause (i) or (ii), is in the judgment of the Remarketing Agents so materia..."
- **Clause Text:** "(a) The Final Prospectus shall have been filed with the Commission pursuant to Rule 424(b) under the Act within the applicable time period prescribed for such filing by the rules and regulations under..."
- **Root Cause:** Clause discusses related concepts or generic legal vocabulary that triggered model/rules without rising to CUAD's specific expert annotation threshold.

**FP #2** - Contract: `MetLife, Inc. - Remarketing Agreement...`, Clause: `11`
- **Method:** `model` (Score: 0.8692)
- **Evidence:** "obligations of the Remarketing Agents may be terminated by them by notice given to the Company prior to 12:00 noon, New York City time on the Remarket..."
- **Clause Text:** "obligations of the Remarketing Agents may be terminated by them by notice given to the Company prior to 12:00 noon, New York City time on the Remarketing Settlement Date if, prior to that time, any of..."
- **Root Cause:** Clause discusses related concepts or generic legal vocabulary that triggered model/rules without rising to CUAD's specific expert annotation threshold.

**FP #3** - Contract: `NUVEEN - REMARKETING AGREEMENT...`, Clause: `Exhibit A`
- **Method:** `model` (Score: 0.7158)
- **Evidence:** "NUVEEN AMT-FREE QUALITY MUNICIPAL INCOME FUND (NVG) (THE "FUND") SERIES [●] MUNIFUND PREFERRED SHARES IN THE VARIABLE RATE REMARKETED MODE ("VRRM-MFP ..."
- **Clause Text:** "NUVEEN AMT-FREE QUALITY MUNICIPAL INCOME FUND (NVG) (THE "FUND") SERIES [●] MUNIFUND PREFERRED SHARES IN THE VARIABLE RATE REMARKETED MODE ("VRRM-MFP SHARES") TENDER NOTICE Note: The substance of this..."
- **Root Cause:** Clause discusses related concepts or generic legal vocabulary that triggered model/rules without rising to CUAD's specific expert annotation threshold.

**FP #4** - Contract: `NUVEEN - REMARKETING AGREEMENT...`, Clause: `Schedule 1`
- **Method:** `model` (Score: 0.8463)
- **Evidence:** "TENDER NOTICE DELIVERY INFORMATION FOR THE REMARKETING AGENT This Tender Notice must be delivered by the Beneficial Owner or its Agent Member to [●] (..."
- **Clause Text:** "TENDER NOTICE DELIVERY INFORMATION FOR THE REMARKETING AGENT This Tender Notice must be delivered by the Beneficial Owner or its Agent Member to [●] (the "Remarketing Agent") by email transmission at ..."
- **Root Cause:** Clause discusses related concepts or generic legal vocabulary that triggered model/rules without rising to CUAD's specific expert annotation threshold.

**FP #5** - Contract: `Sonos, Inc. - Manufacturing Agreement ...`, Clause: `0`
- **Method:** `rules` (Score: 0.9)
- **Evidence:** "y upon written notice to the other Party. 16.2. No Third Party Beneficiaries. Unless otherwise expressly provided, no provisions of this Agreement are..."
- **Clause Text:** "Exhibit 10.07 [*] Certain confidential information contained in this document, marked by brackets, has been omitted and filed separately with the Securities and Exchange Commission pursuant to Rule 40..."
- **Root Cause:** Clause discusses related concepts or generic legal vocabulary that triggered model/rules without rising to CUAD's specific expert annotation threshold.

#### False Negatives (In CUAD expert annotations, but missed by detector):
**FN #1** - Contract: `ORBSATCORP_08_17_2007-EX-7.3-STRATEGIC A...`, Clause: `0`
- **Expert Target Span:** "Notwithstanding the foregoing, UTK may assign this Agreement or any portion of its Compensation as o..."
- **Clause Text:** "Exhibit 7.3 STRATEGIC ALLIANCE AGREEMENT This Strategic Alliance Agreement is made and entered into this 9th day of September 2005, by and between UTEK Corporation ("UTK"), 202 South Wheeler Street, P..."
- **Root Cause:** Atypical drafting vocabulary or domain-specific phrasing not captured by TF-IDF n-grams or regular expressions.

**FN #2** - Contract: `ORBSATCORP_08_17_2007-EX-7.3-STRATEGIC A...`, Clause: `2`
- **Expert Target Span:** "Notwithstanding the foregoing, UTK may assign this Agreement or any portion of its Compensation as o..."
- **Clause Text:** "IV. EXPENSES It is expressly agreed and understood that each party shall be responsible for its own normal and reasonable out-of-pocket expenses. V. COMPENSATION A. In consideration for the services t..."
- **Root Cause:** Atypical drafting vocabulary or domain-specific phrasing not captured by TF-IDF n-grams or regular expressions.

**FN #3** - Contract: `ORBSATCORP_08_17_2007-EX-7.3-STRATEGIC A...`, Clause: `2`
- **Expert Target Span:** "Notwithstanding the foregoing, UTK may assign this Agreement or any portion of its Compensation as o..."
- **Clause Text:** "B. PROVISIONS. Neither termination nor completion of the assignment shall affect the provisions of this Agreement, and the Indemnification Provisions that are incorporated herein, which shall remain o..."
- **Root Cause:** Atypical drafting vocabulary or domain-specific phrasing not captured by TF-IDF n-grams or regular expressions.

**FN #4** - Contract: `ORBSATCORP_08_17_2007-EX-7.3-STRATEGIC A...`, Clause: `Exhibit A`
- **Expert Target Span:** "Notwithstanding the foregoing, UTK may assign this Agreement or any portion of its Compensation as o..."
- **Clause Text:** "CONFIDENTIAL TERM SHEET PROPOSED STRATEGIC ALLIANCE BETWEEN UTEK CORPORATION (UTK) & WORLD ENERGY SOLUTIONS (AVDU) Statement of Work: To identify technology acquisition opportunities for AVDU from res..."
- **Root Cause:** Atypical drafting vocabulary or domain-specific phrasing not captured by TF-IDF n-grams or regular expressions.

**FN #5** - Contract: `PalmerSquareCapitalBdcInc_20200116_10-12...`, Clause: `0`
- **Expert Target Span:** "The parties agree that Investment Advisor shall be a third party beneficiary of this Agreement, and ..."
- **Clause Text:** "Exhibit 10.6 TRADEMARK LICENSE AGREEMENT This TRADEMARK LICENSE AGREEMENT (this "Agreement") is made and effective as of [ ] day of [ ], 2020 ("Effective Date"), by and between Palmer Square Capital M..."
- **Root Cause:** Atypical drafting vocabulary or domain-specific phrasing not captured by TF-IDF n-grams or regular expressions.

---
