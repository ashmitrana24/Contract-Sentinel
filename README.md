# ClauseGuard: Legal Document Fraud & Integrity Analysis Platform

ClauseGuard is an enterprise contract integrity and risk analysis platform designed to detect tampering, fraud, semantic inconsistencies, and anomalous clauses across legal agreements.

---

## Repository Architecture

```
legal-doc/
├── README.md                      # Platform overview, visual gallery, and quick reference
├── DECISIONS.md                   # Architectural decisions and engineering rationales (D-01 to D-30)
├── docker-compose.yml             # Postgres, Redis, API, Worker, and Next.js Web App orchestration
├── docs/screenshots/              # Full-page screenshots (Desktop/Mobile, Light/Dark)
├── data/generated/                # Labeled ground-truth clean & tampered contracts
├── datagen/                       # MODULE 1: Synthetic Dataset & Forgery Generator
│   ├── pyproject.toml
│   ├── README.md                  # Generator usage and tamper types
│   ├── DECISIONS.md
│   ├── src/datagen/               # Synthesizer, ReportLab renderer, tamper pipeline
│   └── tests/                     # 85 tests: quality gates, labels, and tamper verifiers
├── backend/                       # MODULES 2, 3, 4, 5 & 8: Pipeline, Forensics, Consistency, Clauses & Risk
│   ├── pyproject.toml
│   ├── alembic.ini                # PostgreSQL schema migrations
│   ├── Dockerfile                 # Container image for API, Worker, and Sweeper
│   ├── README.md                  # In-depth pipeline, API walkthrough, benchmarks
│   ├── DECISIONS.md               # Architecture decision records
│   ├── alembic/                   # Database migrations (0001_initial to 0004_risk_summary)
│   ├── eval/                      # Evaluation harness & benchmarks (forensics, consistency, risk)
│   ├── src/clauseguard/
│   │   ├── config.py              # Pydantic v2 settings & dynamic environment overrides
│   │   ├── db/                    # SQLAlchemy 2.0 models (Document, Job, Finding, RiskSummary)
│   │   ├── storage/               # SHA-256 content-addressed atomic FileStore
│   │   ├── parsing/               # PyMuPDF span extractor, NFC normalizer, clause segmenter
│   │   ├── queue/                 # Redis Streams, consumer groups, full-jitter backoff
│   │   ├── api/                   # FastAPI endpoints (upload, documents, risk, findings, clauses)
│   │   ├── worker/                # Resilient workers, crash recovery, stuck job sweeper
│   │   ├── forensics/             # MODULE 3: PDF Structure Forensics Engine
│   │   ├── consistency/           # MODULE 4: Semantic & Structural Consistency Engine
│   │   ├── clauses/               # MODULE 5: Multi-Label Clause Classifier & Key-Term Extractor
│   │   └── risk/                  # MODULE 8: Finding Catalog, Aggregator & Highlight Locator
│   └── tests/                     # 472+ tests: Unit (449) and Integration (23) suites
└── frontend/                      # MODULE 9: Web Application & Review Workbench
    ├── package.json               # Next.js 16, Tailwind CSS v4, TanStack Query, react-pdf
    ├── Dockerfile                 # Multi-stage production container build
    ├── README.md                  # Frontend architecture, components, and workflows
    ├── public/                    # Bundled PDF worker and synthetic contract samples
    ├── src/
    │   ├── app/                   # Next.js App Router (Homepage and Document Report)
    │   ├── components/            # UI components (Workbench, PDF Viewer, Stepper, Tabs)
    │   └── lib/                   # API client, OpenAPI types, and PDF coordinate math
    ├── tests/                     # Vitest unit test suite (18 tests)
    └── e2e/                       # Playwright end-to-end and Axe accessibility tests
```

---

## Modules Overview

### [Module 1: Synthetic Dataset & Forgery Generator (`datagen/`)](file:///c:/Users/Loq/Desktop/Projects/legal-doc/datagen/README.md)
Generates high-fidelity synthetic commercial contracts with programmatic ground-truth labels and introduces 9 distinct tampering techniques (amount alterations, clause deletions/insertions, cross-reference corruption, date shifting, party swaps, invisible font text, and incremental PDF edits). Produces sidecar files `labels.jsonl`, `labels.json`, and `expected_clauses.json`.

### [Module 2: Ingestion, Parsing & Job Pipeline (`backend/`)](file:///c:/Users/Loq/Desktop/Projects/legal-doc/backend/README.md)
Production-grade ingestion and processing engine:
- **FastAPI Upload**: Streaming validation (`%PDF-` header, max file size) and SHA-256 deduplication (returns HTTP 200 with `deduplicated: true`).
- **Content-Addressed Storage**: Pure SHA-256 filesystem partitioning with atomic temp-file rename.
- **Reliable Distributed Workers**: Redis Streams (`cg:jobs`) with consumer groups (`cg-workers`), lease management, `XAUTOCLAIM` crash recovery, dead-letter queue (`cg:jobs:dead`), and exponential backoff with full jitter.
- **Document Parsing Engine**: PyMuPDF-based text and span extraction, Unicode NFC normalization, header/footer filtering, heuristic clause segmentation, preamble isolation, and `needs_ocr` detection.
- **High Concurrency & Throughput**: Benchmarked at **2,653 docs/min** with 3 workers on 30 synthetic PDF contracts (100% completion, 0 errors).

### [Module 3: PDF Structure Forensics (`backend/src/clauseguard/forensics/`)](file:///c:/Users/Loq/Desktop/Projects/legal-doc/backend/README.md#7-module-3-pdf-structure-forensics)
Conservative file-level inspection engine for contract PDF documents:
- **Incremental Edit Detection**: Scans raw binary streams for `%%EOF` revisions, validates byte prefixes with PyMuPDF, performs sequence-preserving token diffing (`difflib.SequenceMatcher`), escalates altered financial amounts and dates to `CRITICAL`, and recognizes legitimate AcroForm field edits via widget bounding box containment.
- **Hidden & Invisible Text**: Analyzes PyMuPDF `get_texttrace()` for `type=3` invisible rendering, sub-2pt font size, and off-page coordinates. Calculates dynamic WCAG 2.0 contrast against drawn backgrounds and catches opaque white-out redaction overlays.
- **Digital Signature Integrity**: Uses pyHanko to cryptographically verify byte-range digests and DocMDP modification policies without enforcing untrusted root CA chains.
- **Metadata Chronology**: Identifies time travel, future dates, reversed modification dates, and traces from online PDF editor tools.
- **Active Content & Overlays**: Detects embedded JavaScript, `/Launch` execution commands, `/OpenAction`, and page-masking annotation rectangles.
- **Evaluation Benchmark**: Evaluated on Module 1 labeled dataset (`labels.jsonl`) achieving **100.0% precision, 100.0% recall, 0.0% clean false positive rate**, and 100% incremental edit localization.
- **Benign Baseline Suite**: 17 dedicated benchmark test cases yielding zero false alarms on standard enterprise contracts.

### [Module 4: Contract Consistency Engine (`backend/src/clauseguard/consistency/`)](file:///c:/Users/Loq/Desktop/Projects/legal-doc/backend/README.md)
Deterministic semantic and structural consistency verification engine analyzing internal contract logic across amounts, dates, parties, numbering, and cross-references:

#### Final Severity Classification Table

| Finding Type | Condition / Context | Severity | Behavioral Rationale |
|---|---|---|---|
| `figure_words_mismatch` | Currency amounts or percentages with difference $\ge 20\%$ | **CRITICAL** | Major economic discrepancy indicating fraud or catastrophic drafting error. |
| `figure_words_mismatch` | Currency amounts or percentages with difference $< 20\%$ | **HIGH** | Minor economic variance or calculation/rounding discrepancy. |
| `figure_words_mismatch` | Plain quantities (days, months, years, notice periods, units) | **MEDIUM** | Standard drafting typo or operational quantity mismatch. |
| `figure_words_mismatch` | Low-confidence or ambiguous textual number phrases | **LOW** | Minor linguistic ambiguity; non-critical parse. |
| `date_order_inverted` | Effective date strictly after termination date | **HIGH** | Inverted contract term validity; logically impossible timeline. |
| `dangling_reference` | Target clause number missing from contract numbering (reliable doc) | **MEDIUM** | Broken internal cross-reference to non-existent section. |
| `dangling_reference` | Sub-clause reference (`Section 4.3(a)`, `10.1(a)(i)`) where parent exists | *(Suppressed)* | Resolves to parent clause; exact dotted numbers must match. |
| `dangling_reference` | Statutory / regulatory citations (`Section 409A`, `12(g)`, `REACH`, `Code`) | *(Suppressed)* | External statutory reference with statutory context keywords. |
| `dangling_reference` / `numbering_gap` | Document fails segmentation reliability gate | **LOW ("uncertain")** | Document structure unreliable; demoted to avoid false alarm floods. |
| `undefined_party` | Undefined entity in an operative contracting role (`shall`, `consent of X`) | **MEDIUM** | Unidentified party assuming contractual obligations or rights. |
| `undefined_party` | Single-token / first-token short forms in notice or signature blocks | **LOW** | Legitimate trade name or administrative shorthand. |
| `duplicate_clause_number`| Duplicate clause identifier in a standard agreement | **MEDIUM** | Ambiguous clause numbering or section collision. |
| `duplicate_clause_number`| Document is an amendment or restatement ("amendment", "restated") | *(Suppressed)* | Legitimate restatement of original agreement sections. |
| `numbering_gap` | Non-sequential clause numbering gap | **LOW** | Potential omitted clause or formatting irregularity. |

#### Evaluation Results (Fresh Synthetic Dataset: `data/generated_seed4242`)

| Tamper Type / Baseline | Evaluated | Flagged | Recall / Rate | Target | Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `amount_figure_only` | 33 | 33 | **100.0%** | $\ge 90.0\%$ | **MET** |
| `date_shift` | 34 | 34 | **100.0%** | $\ge 90.0\%$ | **MET** |
| `party_swap` | 47 | 43 | **91.5%** | $\ge 85.0\%$ | **MET** |
| `xref_break` | 32 | 32 | **100.0%** | $\ge 90.0\%$ | **MET** |
| `clause_delete` | 52 | 20 | **38.5%** | $\ge 80.0\%$ | **MISSED** (Semantic limitation) |
| Clean Synthetic False Positive Rate | 120 | 0 | **0.00%** | $\le 2.0\%$ | **MET** |

*Expected Undetectable by Internal Consistency Alone*:
- `amount_both`: 0/34 flagged (0.0%) — coherent words and figures require external ground-truth comparison.
- `clause_insert`: 6/38 flagged (15.8%) — cleanly inserted clauses without numbering gaps leave no internal trace.
- `incremental_edit`: 1/31 flagged (3.2%) — detected via Module 3 PDF structure forensics.
- `hidden_text`: 35/38 flagged (92.1%) — detected primarily via typography and structural heuristics.

#### Real-World Generalization & Unseen Evaluation

| Corpus / Split | Documents | Flagged (MEDIUM+) | Genuine Defects | False Alarms | False Alarm Rate | Target | Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **ContractNLI Test NDAs** *(Zero-Tuning)* | **123** | **4** (3.25%) | **1** (0.81%) | **3** (2.44%) | **2.44%** | $\le 5.0\%$ | **MET** |
| **CUAD v1 Unseen Contracts** *(Post-Tuning Optimistic)* | 310 | 85 (27.42%) | ~15 | ~70 | 22.58% | $\le 5.0\%$ | **MISSED** (OCR noise / SEC filings) |

*Genuine defect caught in real contract*: In `MUTUAL NON-DISCLOSURE AGREEMENT` (`ContractNLI_Test_056`), caught a real drafting conflict: *"shall expire five (2) years from the date hereof"*.

### [Module 5: Clause Classification & Key-Term Extraction (`backend/src/clauseguard/clauses/`)](file:///c:/Users/Loq/Desktop/Projects/legal-doc/backend/README.md)
Multi-label clause classifier and deterministic key-term extraction engine that reads clauses produced by the Module 2 parser, labels each clause across 45 legal categories, extracts structured attributes, and stores results in PostgreSQL for downstream risk analysis (Module 6).

#### Taxonomy Architecture
- **36 Core Contractual Labels**: Mapped from the Atticus Project CUAD v1 expert benchmark (excluding 5 document-level metadata categories: Document Name, Parties, Agreement Date, Effective Date, Expiration Date).
- **9 Additional Risk & Operational Labels**: High-value contract clauses evaluated via deterministic rules: `indemnification`, `confidentiality`, `payment_terms`, `unilateral_amendment`, `force_majeure`, `arbitration_or_dispute_resolution`, `waiver_of_rights`, `termination_for_cause`, `auto_renewal`.
- **Hybrid Inference & Long-Clause Sliding Windowing**: Combines high-precision regex/keyword rules with balanced TF-IDF + LogisticRegression binary classifiers. Clauses $> 250$ words are chunked into 120-word sliding windows (stride 100) and aggregated with localized evidence snippets ($\le 300$ chars).

#### 8 Deterministic Key-Term Extractors
Never guesses; returns `None` / empty when terms are silent or ambiguous:
1. `governing_law_jurisdiction`: Canonical jurisdiction string (e.g., "Delaware", "New York", "England and Wales").
2. `termination_notice_days`: Notice timeframe in days for convenience or general termination.
3. `auto_renews`: Boolean indicating auto-renewal / evergreen renewal provisions.
4. `renewal_term_months`: Duration in months of successive renewal periods.
5. `non_renewal_notice_days`: Notice timeframe in days required to prevent contract renewal.
6. `liability_cap`: Structured fixed monetary cap or fee-multiple dictionary.
7. `non_compete_duration_months`: Duration in months of restrictive non-compete covenants.
8. `payment_terms_days`: Payment window timeframe in days (e.g., Net 30 -> 30).

#### Honest Benchmark Results on Unseen TEST Split (Third Look on Corrected Labels)
> [!IMPORTANT]
> **Label Correction Notice**: The initial two evaluation looks used token-overlap alignment (30% span token overlap) which inflated ground-truth labels across contracts (e.g. 753 `governing_law` test positive clauses for 102 contracts, and 59 labels on a single agreement). **All previous per-label numbers from Looks 1 and 2 are officially VOID**.
> Ground truth was rebuilt using exact character offsets ($\ge 50\%$ span character overlap, or largest overlap). The results below represent the official **Third Look** evaluated exactly once on the corrected test split:

| Metric | Test Split Value (Third Look) |
|---|---|
| **Total Test Samples** | 2,788 clauses |
| **True Test Label Support** | 1,052 positive instances (corrected from inflated 4,500+) |
| **Micro Precision** | **64.89%** |
| **Micro Recall** | **63.59%** |
| **Micro F1** | **64.23%** |
| **Macro Precision** | **49.30%** |
| **Macro Recall** | **49.23%** |
| **Macro F1** | **47.88%** |

*Core High-Support Benchmark Labels (Third Look)*:
- `governing_law` (Support: 89): Precision **96.3%**, Recall **86.5%**, F1 **91.1%** (95% CI: `[0.90, 0.99]`)
- `anti_assignment` (Support: 86): Precision **86.8%**, Recall **83.7%**, F1 **85.2%** (95% CI: `[0.78, 0.92]`)
- `cap_on_liability` (Support: 66): Precision **80.6%**, Recall **81.8%**, F1 **81.2%** (95% CI: `[0.70, 0.88]`)
- `license_grant` (Support: 83): Precision **90.8%**, Recall **71.1%**, F1 **79.7%** (95% CI: `[0.81, 0.96]`)
- `audit_rights` (Support: 57): Precision **71.6%**, Recall **84.2%**, F1 **77.4%** (95% CI: `[0.60, 0.81]`)
- `notice_period_to_terminate_renewal` (Support: 22): Precision **72.0%**, Recall **81.8%**, F1 **76.6%** (95% CI: `[0.52, 0.86]`)
- `uncapped_liability` (Support: 24): Precision **68.2%**, Recall **62.5%**, F1 **65.2%** (95% CI: `[0.47, 0.84]`)
- `termination_for_convenience` (Support: 44): Precision **53.7%**, Recall **50.0%**, F1 **51.8%** (95% CI: `[0.39, 0.68]`)

Complete per-label performance, 95% Wilson intervals, and error breakdowns are recorded in [`backend/models/clauses/v1/metrics.json`](file:///c:/Users/Loq/Desktop/Projects/legal-doc/backend/models/clauses/v1/metrics.json).

### [Module 8: Transparent Risk Summary (`backend/src/clauseguard/risk/`)](file:///c:/Users/Loq/Desktop/Projects/legal-doc/backend/src/clauseguard/risk/)
Deterministic risk aggregation, human-readable cataloging, and coordinate highlight resolution:
- **Finding Catalog**: Maps every detector finding to plain English title, `what_it_means`, and `what_to_check`.
- **Deterministic Aggregator**: Weights (Critical: 40, High: 20, Medium: 8) with diminishing returns (1st instance 100%, each additional 25%, 2x cap per type). Low and uncertain findings are categorized as minor notes and never scored.
- **Coverage & Reliability Warnings**: Checks `needs_ocr`, segmentation quality, and detector execution status, flagging a visible warning banner and asterisk when analysis is partial.
- **Evidence-Driven Highlights**: Top-left PyMuPDF points with multi-span text search, exact token clipping, clause-level heading fallbacks, and rotated page support.
- **Reviewer Feedback**: Persists reviewer verdicts (`confirmed` / `dismissed`) with notes per finding.

### [Module 9: Web Application & Review Workbench (`frontend/`)](file:///c:/Users/Loq/Desktop/Projects/legal-doc/frontend/)
A polished contract integrity review workbench built with Next.js 16 (App Router), TypeScript, Tailwind CSS v4, Radix UI, TanStack Query, and react-pdf:
- **Review Workbench Principle**: Designed specifically as a review workbench to show human reviewers what to look at and why. **It never claims that a contract is fraudulent or legally sound.**
- **Risk Band Guidance**: The risk band indicates how much manual review is recommended (Low = "No significant issues found", Medium = "Review recommended", High = "Needs careful review"), not whether legal fraud occurred.
- **Privacy & Security**: Zero third-party network calls, zero tracking/analytics, no CDN scripts. PDF documents are streamed strictly inline from our own API. Local storage is strictly used for theme preference.
- **Responsive & Accessible**: Continuous PDF scroll, zoom controls, coordinate-scaled highlight overlays (dashed for approximate, pulsing for active), split view resizable workbench (55/45 desktop, tabbed mobile), dark/light mode toggle, and WCAG AA compliance with zero axe accessibility violations.

---

## Web App

### Visual Gallery

| View | Light Theme | Dark Theme |
| :--- | :--- | :--- |
| **Workbench (Desktop)** | ![Report Desktop Light](docs/screenshots/home-desktop-light.png) | ![Report Desktop Dark](docs/screenshots/home-desktop-dark.png) |
| **Contract Report (Desktop)** | ![Report Desktop Light](docs/screenshots/report-desktop-light.png) | ![Report Desktop Dark](docs/screenshots/report-desktop-dark.png) |
| **Mobile Home (375px)** | ![Home Mobile Light](docs/screenshots/home-mobile-light.png) | ![Home Mobile Dark](docs/screenshots/home-mobile-dark.png) |
| **Mobile Report (375px)** | ![Report Mobile Light](docs/screenshots/report-mobile-light.png) | ![Report Mobile Dark](docs/screenshots/report-mobile-dark.png) |

---

## Quickstart

### 1. Launch with Docker Compose (Recommended)
```bash
docker compose up --build
```
- **Web App**: http://localhost:3000
- **FastAPI Documentation**: http://localhost:8000/docs
- **PostgreSQL**: localhost:5432
- **Redis**: localhost:6379

### 2. Local Development

#### Backend
```bash
# Launch PostgreSQL and Redis
docker compose up -d postgres redis

# Apply database migrations
cd backend
alembic upgrade head

# Terminal 1: Run FastAPI server
uvicorn clauseguard.api.main:app --host 0.0.0.0 --port 8000 --reload

# Terminal 2: Run Worker process
python -m clauseguard.worker.main
```

#### Frontend
```bash
cd frontend
npm install
npm run dev
# App will run on http://localhost:3000
```

---

## API Reference

> [!CAUTION]
> The ClauseGuard API does not enforce authentication or user session separation. It is designed for internal network or authenticated reverse-proxy deployment only and **must not be exposed publicly to the internet**.

- `GET /v1/documents?limit=20&offset=0&status=succeeded`: Paginated document list with size, page count, risk score, band, and finding counts by severity.
- `GET /v1/documents/{id}`: Detailed document status, metadata, and latest job run.
- `GET /v1/documents/{id}/file`: Streams the stored PDF inline as `application/pdf` directly from the secure content store.
- `DELETE /v1/documents/{id}`: Cascading deletion of document database rows and stored disk file (HTTP 204, idempotent).
- `GET /v1/documents/{id}/risk`: Deterministic risk score (0–100), risk band (`low`, `medium`, `high`), headline, top reasons, and coverage notes.
- `GET /v1/documents/{id}/findings`: Comprehensive finding list enriched with catalog metadata (`category`, `title`, `what_it_means`, `what_to_check`), reviewer feedback, and localized bounding box highlights.
- `POST /v1/findings/{id}/feedback`: Submit human review verdict (`verdict: "confirmed" | "dismissed"`, optional note).
- `DELETE /v1/findings/{id}/feedback`: Clear human review verdict (HTTP 204).
- `GET /v1/documents/{id}/clauses`: Segmented document clauses with confidence scores and multi-label classifications.
- `GET /v1/documents/{id}/attributes`: Extracted structured legal attributes and key contract terms.
- `GET /v1/jobs/{id}`: Detailed job execution progress with 6 granular stages (`upload`, `parse`, `forensics`, `consistency`, `clauses`, `summary`).
- `GET /v1/finding-types`: Complete catalog of supported tampering and inconsistency finding types.

---

## Testing & Quality Gates

```bash
# Backend Unit Tests (Aggregator, Catalog, Highlights, Forensics, Consistency, Clauses) — 449 passed
pytest backend/tests/unit

# Backend Integration Tests (End-to-end API, Risk API, Feedback, Worker reliability) — 23 passed
pytest -m integration backend/tests/integration

# Risk Aggregation Calibration Benchmark
python backend/eval/risk_eval.py --data data/generated

# Frontend Unit Tests (Vitest: Gauge, Badge, Findings, Coordinate scaling, Validation) — 18 passed
cd frontend && npm test

# Frontend Linting
cd frontend && npm run lint

# Backend Linting
ruff check backend/src backend/tests backend/eval

# Playwright End-to-End & Accessibility Tests
cd frontend && npx playwright test
```

See [DECISIONS.md](file:///c:/Users/Loq/Desktop/Projects/legal-doc/DECISIONS.md) for architectural records (D-01 through D-30).
