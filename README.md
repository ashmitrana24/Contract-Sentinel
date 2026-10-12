# ClauseGuard: Legal Document Fraud & Integrity Analysis Platform

ClauseGuard is an enterprise contract integrity and risk analysis platform designed to detect tampering, fraud, semantic inconsistencies, and anomalous clauses across legal agreements.

---

## Repository Architecture

```
legal-doc/
├── README.md                      # Platform overview and quick reference
├── DECISIONS.md                   # Architectural decisions and engineering rationales
├── docker-compose.yml             # Postgres, Redis, API, and Worker orchestration
├── data/generated/                # Labeled ground-truth clean & tampered contracts
├── datagen/                       # MODULE 1: Synthetic Dataset & Forgery Generator
│   ├── pyproject.toml
│   ├── README.md                  # Generator usage and tamper types
│   ├── DECISIONS.md
│   ├── src/datagen/               # Synthesizer, ReportLab renderer, tamper pipeline
│   └── tests/                     # 85 tests: quality gates, labels, and tamper verifiers
└── backend/                       # MODULES 2 & 3: Ingestion, Pipeline & Forensics Engine
    ├── pyproject.toml
    ├── alembic.ini                # PostgreSQL schema migrations
    ├── Dockerfile                 # Container image for API, Worker, and Sweeper
    ├── README.md                  # In-depth ingestion, API walkthrough, benchmarks
    ├── DECISIONS.md               # Architecture decision records
    ├── alembic/                   # Database migrations (0001_initial, 0002_forensics)
    ├── eval/                      # Evaluation harness & synthetic document generators
    │   ├── forensics_eval.py      # Real dataset benchmark runner & markdown reporter
    │   └── synthetic.py           # 17 standalone PDF scenario builders (clean & tampered)
    ├── src/clauseguard/
    │   ├── config.py              # Pydantic v2 settings & dynamic environment overrides
    │   ├── db/                    # SQLAlchemy 2.0 models (FindingRow, AnalysisRun, etc.)
    │   ├── storage/               # SHA-256 content-addressed atomic FileStore
    │   ├── parsing/               # PyMuPDF span extractor, NFC normalizer, clause segmenter
    │   ├── queue/                 # Redis Streams, consumer groups, full-jitter backoff
    │   ├── api/                   # FastAPI upload, pagination, findings query, healthz
    │   ├── worker/                # Resilient workers, crash recovery, stuck job sweeper
    │   ├── schemas/               # Pydantic models (Findings, ParsedDocument, API)
    │   ├── forensics/             # MODULE 3: PDF Structure Forensics Engine
    │   │   ├── models.py          # Typed dataclasses (ForensicsSettings, ForensicsReport)
    │   │   ├── revisions.py       # Binary %%EOF scanner & revision prefix validator
    │   │   ├── incremental.py     # Token diffing, monetary/date escalation, AcroForm check
    │   │   ├── text_hiding.py     # Type=3, sub-2pt, off-page, WCAG contrast, white-outs
    │   │   ├── signatures.py      # PyHanko cryptographic digest & DocMDP verification
    │   │   ├── metadata.py        # Timestamp chronology, clock-skew, producer anomaly
    │   │   ├── active_content.py  # JavaScript, /Launch, /OpenAction, annotation masks
    │   │   └── run.py             # Time-budgeted orchestrator & standalone CLI
    │   └── bench/                 # High-concurrency throughput and latency benchmark
    └── tests/                     # 95 tests: Unit, Benign Suite, and Live Integration
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

#### Known Limitations

1. **Messy OCR Filings**: Complex SEC EDGAR Exhibit-10 filings containing scanning artifacts, multi-column tables, line-wrapped headers, or unescaped exhibit cross-references can confuse clause segmentation and trigger false dangling references or party variant warnings.
2. **Unsegmented Structures**: Contracts with nested schedules, Roman numeral articles containing non-standard indentation, or unnumbered bullet agreements may not yield reliable clause trees.
3. **Fewer Genuine-Tamper Types Detectable via Consistency**: Pure semantic consistency checks can only identify *internal contradictions* (word-digit clashes, inverted dates, unknown parties, broken references). Tampers that modify both words and numbers consistently, or insert/delete entire self-contained clauses without numbering disruption, leave zero internal inconsistency trace and must be caught via Module 3 PDF structural forensics or comparative redlining.

---

## Quickstart

### 1. Start Services
```bash
# Launch PostgreSQL 16 and Redis 7
docker compose up -d postgres redis

# Run database migrations (including 0002_forensics)
cd backend
alembic upgrade head
```

### 2. Run the Stack
```bash
# Terminal 1: Run FastAPI server
uvicorn clauseguard.api.main:app --host 0.0.0.0 --port 8000 --reload

# Terminal 2: Run Worker process (includes PDF parsing + Forensics analysis)
python -m clauseguard.worker.main
```

### 3. Standalone Forensics CLI
Analyze any PDF file directly without web services:
```bash
cd backend
python -m clauseguard.forensics.run /path/to/contract.pdf
```

### 4. Run Forensic Evaluation on Dataset
```bash
cd backend
python eval/forensics_eval.py --data data/generated
```

---

## Testing & Quality Gates

```bash
# Module 1 (Dataset Generator) Tests — 85 passed
pytest datagen/tests

# Module 2 & 3 (Backend Pipeline + Forensics) Tests — 95 passed, 1 skipped
pytest backend/tests/unit backend/tests/integration

# Benign Baseline Suite — 17 passed (0 false alarms)
pytest backend/tests/unit/forensics/test_benign_suite.py

# Cryptographic Signature Tests — 4 passed (real pyHanko signing, no mocks)
pytest backend/tests/unit/forensics/test_signatures.py

# Code Quality & Linting
ruff check backend/src backend/tests backend/eval datagen/src datagen/tests
```

See [DECISIONS.md](file:///c:/Users/Loq/Desktop/Projects/legal-doc/DECISIONS.md) for architectural records (D-01 through D-14) and [backend/README.md](file:///c:/Users/Loq/Desktop/Projects/legal-doc/backend/README.md) for API endpoints and detailed benchmarks.
