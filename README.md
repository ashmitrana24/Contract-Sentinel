# ClauseGuard: Legal Document Fraud & Integrity Analysis Platform

ClauseGuard is an enterprise contract integrity and risk analysis platform designed to detect tampering, fraud, semantic inconsistencies, and anomalous clauses across legal agreements.

---

## Repository Architecture

```
legal-doc/
├── README.md                      # Platform overview and quick reference
├── DECISIONS.md                   # Architectural decisions and engineering rationales
├── docker-compose.yml             # Postgres, Redis, API, and Worker orchestration
├── datagen/                       # MODULE 1: Synthetic Dataset & Forgery Generator
│   ├── pyproject.toml
│   ├── README.md                  # Generator usage and tamper types
│   ├── DECISIONS.md
│   ├── src/datagen/               # Synthesizer, ReportLab renderer, tamper pipeline
│   └── tests/                     # 85 tests: quality gates, labels, and tamper verifiers
└── backend/                       # MODULE 2: Ingestion, Parsing & Job Pipeline
    ├── pyproject.toml
    ├── alembic.ini                # PostgreSQL schema migrations
    ├── Dockerfile                 # Container image for API, Worker, and Sweeper
    ├── README.md                  # In-depth ingestion, API walkthrough, benchmarks
    ├── alembic/                   # Database migration scripts
    ├── src/clauseguard/
    │   ├── config.py              # Pydantic v2 settings & dynamic environment overrides
    │   ├── db/                    # SQLAlchemy 2.0 models & connection pool
    │   ├── storage/               # SHA-256 content-addressed atomic FileStore
    │   ├── parsing/               # PyMuPDF span extractor, NFC normalizer, clause segmenter
    │   ├── queue/                 # Redis Streams, consumer groups, full-jitter backoff
    │   ├── api/                   # FastAPI upload, pagination, deduplication, healthz
    │   ├── worker/                # Resilient workers, crash recovery, stuck job sweeper
    │   ├── schemas/               # Pydantic models (Findings, ParsedDocument, API)
    │   └── bench/                 # High-concurrency throughput and latency benchmark
    └── tests/                     # 46 tests: Unit, Dataset Recovery, and Live Integration
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

---

## Quickstart

### 1. Start Services
```bash
# Launch PostgreSQL 16 and Redis 7
docker compose up -d postgres redis

# Run database migrations
cd backend
alembic upgrade head
```

### 2. Run the Stack
```bash
# Terminal 1: Run FastAPI server
uvicorn clauseguard.api.main:app --host 0.0.0.0 --port 8000 --reload

# Terminal 2: Run Worker process
python -m clauseguard.worker.main
```

### 3. Scaling Workers
Scale horizontally with Docker Compose or multiple worker processes:
```bash
docker compose up -d --scale worker=3
```

---

## Testing & Quality Gates

```bash
# Module 1 (Dataset Generator) Tests — 85 passed
pytest datagen/tests

# Module 2 (Backend Pipeline) Tests — 46 passed
pytest backend/tests/unit backend/tests/test_dataset.py backend/tests/integration -m "not slow or slow"

# Code Quality & Linting
ruff check backend/src backend/tests
```

See [DECISIONS.md](file:///c:/Users/Loq/Desktop/Projects/legal-doc/DECISIONS.md) for architectural records (D-01 through D-08) and [backend/README.md](file:///c:/Users/Loq/Desktop/Projects/legal-doc/backend/README.md) for the complete cURL walkthrough and benchmark metrics.
