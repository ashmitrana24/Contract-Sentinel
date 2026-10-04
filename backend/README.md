# ClauseGuard Backend — Module 2: Ingestion, Parsing & Pipeline

ClauseGuard is a contract integrity and legal fraud analysis platform. **Module 2** provides the core ingestion pipeline: document intake, deduplication, content-addressed storage, asynchronous Redis Streams job processing, resilient distributed workers, and a PDF parser extracting structured text, bounding box coordinates, and segmented clauses into PostgreSQL.

---

## 1. Architecture Overview

```
                      +-----------------------------+
                      |   Client / Upstream System  |
                      +--------------+--------------+
                                     |  POST /v1/documents
                                     v
                      +-----------------------------+
                      |       FastAPI Service       |
                      |  - Streaming validation     |
                      |  - SHA-256 deduplication    |
                      |  - Atomic FileStore write   |
                      |  - DB Job creation & XADD   |
                      +------+--------------+-------+
                             |              |
                Write File   |              |  Enqueue
                             v              v
               +---------------+     +------------------+
               | Content-Addrs |     |  Redis Streams   |
               |  File Store   |     |    (cg:jobs)     |
               +-------+-------+     +--------+---------+
                       |                      |
                       | Read PDF             | XAUTOCLAIM / XREADGROUP
                       v                      v
               +----------------------------------------+
               |            Worker Process              |
               |  - Lease lock (jobs.locked_until)      |
               |  - PyMuPDF extraction & NFC normalize  |
               |  - Heuristic clause segmentation       |
               |  - Atomic DB upsert (Page & Clause)    |
               |  - Backoff retry or Dead-Letter queue  |
               +-------------------+--------------------+
                                   |
                                   v
               +----------------------------------------+
               |        PostgreSQL Database 16          |
               |  - documents (metadata, sha256)        |
               |  - jobs (status, attempts, lease)      |
               |  - pages (text, dimensions, bboxes)    |
               |  - clauses (clause_id, title, text)    |
               +----------------------------------------+
```

---

## 2. Key Components

### 2.1 Content-Addressed FileStore
- **Hash-only paths**: Keyed solely by SHA-256 digest (`ab/cd/abcdef123456...pdf`).
- **Atomic persistence**: Writes via a temporary file in the target directory followed by atomic rename (`os.replace`).
- **No duplicates**: Identical files map to the same storage path without overwriting or duplicate disk usage.

### 2.2 Ingestion API
- **Streaming verification**: Validates `%PDF-` magic header within the first 1024 bytes and validates file size against `MAX_FILE_SIZE_MB` (default 50 MB) without buffering the entire payload into RAM.
- **Idempotent uploads**: Checks for an existing `Document` by `sha256`. If already ingested, returns HTTP 200 with `deduplicated: true` and the existing document and job IDs; otherwise creates new records and returns HTTP 202.

### 2.3 PDF Parsing & Clause Segmentation
- **PyMuPDF extraction**: Reading-order text extraction preserving exact character and span bounding boxes (`x0, y0, x1, y1`).
- **Normalization**: Unicode NFC normalization, invisible character removal (`\u200b`, `\ufeff`), and whitespace collapse while preserving line breaks.
- **Header & Footer filtering**: Strips repeated running headers and footers across pages ($\ge 3$ pages).
- **Segmentation heuristics**: Matches numbered headings (`1.`, `1.1`, `Section 4`, `Clause 4.2`, `Article IV`) while strictly rejecting false positives (e.g. percentages `1.5%`, dates `01.01.2026`, inline numbering).
- **Preamble extraction**: Unnumbered titles and party recitals preceding Clause 1 are categorized into preamble clause `0`.
- **Graceful degradation**: Documents with $< 2$ clauses fall back to an `unsegmented` clause without raising errors.
- **Scanned document detection**: If text density $< 50$ characters/page, flags `needs_ocr=True` in the page findings.

### 2.4 Worker Reliability & Queueing
- **Redis Streams**: Consumes from stream `cg:jobs` via consumer group `cg-workers`.
- **Crash resilience**: Uses `XAUTOCLAIM` with a 30s visibility timeout to automatically claim jobs abandoned by crashed or killed workers.
- **Poison-pill isolation**: Permanent PDF errors (corrupt bytes, encryption passwords, excessive page count) dead-letter immediately to stream `cg:jobs:dead` with `error_kind='permanent'`, preventing retry waste.
- **Full jitter backoff**: Transient errors (database lock, network blip) retry up to 5 times with exponential backoff and full jitter: $t = \min(300, 1.0 \times 2^{\text{attempts}-1}) \times \text{random}(0, 1)$.
- **Idempotent persistence**: Workers delete prior `pages` and `clauses` for the document within an atomic transaction before inserting parsed records. Replaying a message produces zero duplicate rows.
- **Stuck job sweeper**: Background sweeper identifies un-enqueued or expired lease jobs in Postgres and re-enqueues them safely.

---

## 3. Quickstart & Local Setup

### Prerequisites
- Python 3.11+
- Docker & Docker Compose (or local PostgreSQL 16 and Redis 7)

### 3.1 Start Infrastructure
```bash
# From the repository root
docker compose up -d postgres redis
```

### 3.2 Install Dependencies
```bash
cd backend
pip install -e .
```

### 3.3 Apply Database Migrations
```bash
# Run Alembic migrations against PostgreSQL
alembic upgrade head
```

### 3.4 Start the API Server
```bash
uvicorn clauseguard.api.main:app --host 0.0.0.0 --port 8000 --reload
```

### 3.5 Start the Worker Process
```bash
python -m clauseguard.worker.main
```

### 3.6 Run with Docker Compose (Full Stack)
```bash
# Build and run API, Worker, Postgres, Redis, and run migrations automatically
docker compose up -d

# Scale to 3 concurrent workers
docker compose up -d --scale worker=3
```

---

## 4. End-to-End API Walkthrough (cURL)

### 4.1 Health Check
Verify that the API, PostgreSQL, and Redis connections are healthy:
```bash
curl -s http://localhost:8000/v1/healthz
```
**Response (HTTP 200)**:
```json
{
  "status": "healthy",
  "version": "0.1.0",
  "postgres": "connected",
  "redis": "connected"
}
```

### 4.2 Upload a Contract PDF
```bash
curl -s -X POST http://localhost:8000/v1/documents \
  -F "file=@data/generated/synth_0000_clean.pdf"
```
**Response (HTTP 202 Accepted)**:
```json
{
  "document_id": "8a329d2b-639a-4c25-bb35-cbbe8b2e1f24",
  "job_id": "4e183794-ae70-4f96-857e-97eb38b975d1",
  "sha256": "4b6ecf2f354e20790aa5e93ffdf6a831efda239ffda18ebce40dbd5bcbcdd9b4",
  "status": "queued",
  "deduplicated": false
}
```

### 4.3 Upload the Same Document Again (Deduplication)
Uploading the identical file returns HTTP 200 and indicates deduplication:
```bash
curl -s -X POST http://localhost:8000/v1/documents \
  -F "file=@data/generated/synth_0000_clean.pdf"
```
**Response (HTTP 200 OK)**:
```json
{
  "document_id": "8a329d2b-639a-4c25-bb35-cbbe8b2e1f24",
  "job_id": "4e183794-ae70-4f96-857e-97eb38b975d1",
  "sha256": "4b6ecf2f354e20790aa5e93ffdf6a831efda239ffda18ebce40dbd5bcbcdd9b4",
  "status": "succeeded",
  "deduplicated": true
}
```

### 4.4 Poll Ingestion Job Status
```bash
curl -s http://localhost:8000/v1/jobs/4e183794-ae70-4f96-857e-97eb38b975d1
```
**Response (HTTP 200 OK)**:
```json
{
  "id": "4e183794-ae70-4f96-857e-97eb38b975d1",
  "document_id": "8a329d2b-639a-4c25-bb35-cbbe8b2e1f24",
  "status": "succeeded",
  "attempts": 1,
  "last_error": null,
  "error_kind": null,
  "created_at": "2026-10-03T14:48:12.392000Z",
  "updated_at": "2026-10-03T14:48:12.825000Z"
}
```

### 4.5 Inspect Document Pages & Positioned Spans
```bash
curl -s http://localhost:8000/v1/documents/8a329d2b-639a-4c25-bb35-cbbe8b2e1f24/pages
```
**Response (HTTP 200 OK)**:
```json
[
  {
    "page_number": 1,
    "width": 595.28,
    "height": 841.89,
    "char_count": 1420,
    "findings": [],
    "spans": [
      {
        "text": "CONSULTING SERVICES AGREEMENT",
        "bbox": [140.2, 54.0, 455.08, 68.0],
        "font_name": "Helvetica-Bold",
        "font_size": 14.0
      }
    ]
  }
]
```

### 4.6 Inspect Segmented Clauses
```bash
curl -s http://localhost:8000/v1/documents/8a329d2b-639a-4c25-bb35-cbbe8b2e1f24/clauses
```
**Response (HTTP 200 OK)**:
```json
[
  {
    "clause_id": "0",
    "order_index": 0,
    "title": "Preamble",
    "text_clean": "CONSULTING SERVICES AGREEMENT\nThis Consulting Agreement is entered into on 14 March 2024...",
    "page_start": 1,
    "page_end": 1
  },
  {
    "clause_id": "1",
    "order_index": 1,
    "title": "Scope of Engagement",
    "text_clean": "1. Scope of Engagement\nConsultant shall provide advisory services as set forth herein...",
    "page_start": 1,
    "page_end": 1
  },
  {
    "clause_id": "2",
    "order_index": 2,
    "title": "Compensation and Payment",
    "text_clean": "2. Compensation and Payment\nClient shall pay Consultant INR 4,50,000 within thirty days...",
    "page_start": 1,
    "page_end": 2
  }
]
```

---

## 5. Testing & Verification

Run the entire test suite:
```bash
# Run all tests (Unit, Dataset Recovery, Integration)
pytest backend/tests/unit backend/tests/test_dataset.py backend/tests/integration -m "not slow or slow"

# Code formatting and style audit
ruff check backend/src backend/tests
```

### Test Suite Breakdown:
- **Unit Tests** (`backend/tests/unit/`): 29 tests verifying Unicode NFC normalization, bounding box extraction, clause heuristics, exponential backoff with full jitter, schema validation, and FileStore atomicity.
- **Dataset Test** (`backend/tests/test_dataset.py`): Parses generated clean and tampered contract PDFs from `data/generated/`.
  - **Clean Recovery Rate**: **100.0%** (target $\ge 95\%$) across all synthetic ground-truth clauses in `expected_clauses.json`.
  - **Tamper Resilience**: 100% of PDFs across all 9 tamper types successfully parsed without crashes.
- **Integration Tests** (`backend/tests/integration/`): 15 tests against real PostgreSQL and Redis containers verifying:
  - Streaming file validation and SHA-256 deduplication
  - Automatic crash recovery and lease reclaiming via `XAUTOCLAIM`
  - Dead-letter routing on corrupt PDF poison pills (`cg:jobs:dead`)
  - Exponential backoff retry on transient faults
  - Background sweeper detection and re-enqueuing
  - Graceful worker shutdown during in-flight jobs
  - High concurrency: 3 workers processing 30 documents concurrently with zero duplicates or data corruption.

---

## 6. Pipeline Benchmark & Scaling Results

The ingestion benchmark (`backend/src/clauseguard/bench/ingest_bench.py`) submits 30 PDF contracts concurrently, waits for end-to-end processing across all workers, and measures total wall clock time, throughput (docs/min), and latency percentiles.

### Benchmark Results (30 Synthetic PDF Contracts)

| Metric | 1 Worker | 3 Workers (Concurrent) | Speedup / Scaling |
| :--- | :---: | :---: | :---: |
| **Documents Processed** | 30 / 30 | 30 / 30 | 100% Completion |
| **Wall Clock Time** | **3.69 s** | **0.68 s** | **5.4x Faster** |
| **Throughput** | **487.5 docs / min** | **2,653.0 docs / min** | **5.4x Throughput** |
| **Latency (p50)** | 0.486 s | 0.070 s | 6.9x Lower |
| **Latency (p95)** | 0.673 s | 0.198 s | 3.4x Lower |
| **Latency (p99)** | 0.775 s | 0.199 s | 3.9x Lower |
| **Failures / Errors** | 0 | 0 | 0% Error Rate |

### Running the Benchmark Locally
```bash
python -m clauseguard.bench.ingest_bench \
  --pdf-dir data/generated \
  --api-url http://localhost:8000 \
  --concurrency 5 \
  --max-docs 30
```

---

## 7. Module 3: PDF Structure Forensics

Module 3 inspects the binary structure of uploaded PDF files for post-creation edits, invisible/hidden text, digital signature alterations, and metadata anomalies, reporting detected issues as standardized `Finding` objects.

### 7.1 Detectors

1. **Incremental Edits** (`clauseguard.forensics.incremental`):
   - Scans raw binary streams for `%%EOF` markers and validates each prefix slice.
   - Computes token-level page text diffs across consecutive revisions.
   - Detects modified numeric amounts, altered dates, and party changes, escalating critical findings.
   - Verifies trailer `/ID` consistency.
2. **Text Hiding** (`clauseguard.forensics.text_hiding`):
   - Uses PyMuPDF's `get_texttrace()` to detect `type=3` invisible text, sub-1pt font sizes, and off-page text.
   - Uses `get_drawings()` to compute WCAG 2.0 contrast against dynamic effective background fills.
   - Identifies text occluded under opaque white-out redaction rectangles.
   - Conservative: ignores legitimate footnotes ($\ge 6\text{pt}$), dark headers with white text, and scanned document OCR layers.
3. **Signature Integrity** (`clauseguard.forensics.signatures`):
   - Evaluates digital signatures using pyHanko without enforcing certificate trust chains.
   - Validates cryptographic byte-range digest integrity (`signature_invalid` on byte alteration).
   - Performs DocMDP difference analysis to catch post-signature content changes (`post_signature_modification`).
4. **Metadata Anomalies** (`clauseguard.forensics.metadata`):
   - Checks `ModDate` vs `CreationDate` for reversed dates or large discrepancies.
   - Identifies future timestamps and missing dates.
   - Detects traces from known online PDF editor tools (e.g. iLovePDF, Smallpdf).
5. **Active Content & Annotation Overlays** (`clauseguard.forensics.active_content`):
   - Uses pikepdf to detect embedded JavaScript actions, `/OpenAction`, and `/Launch` execution commands.
   - Detects oversized annotation rectangles masking page text.

### 7.2 CLI & Standalone Analysis

Analyze any PDF from the command line:
```bash
python -m clauseguard.forensics.run /path/to/contract.pdf
```
Outputs a complete, pretty-printed `ForensicsReport` JSON.

### 7.3 API Endpoints

- `GET /v1/documents/{id}/findings?severity=high&limit=50&offset=0` — Retrieve paginated findings for a document.
- `GET /v1/documents/{id}/analysis` — Retrieve forensics execution run details and detector statuses.
- `GET /v1/documents/{id}` — Includes `finding_count` in response.

### 7.4 Evaluation Benchmark

Run the evaluation suite against generated or synthetic datasets:
```bash
python -m eval.forensics_eval --synthetic --out eval/results/eval_report.json
```
Computes per-category Precision, Recall, F1, False Positive Rate on clean documents, and latency percentiles.
