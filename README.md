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
