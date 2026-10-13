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
# Run all tests (Unit, Benign Suite, Dataset Recovery, Integration)
pytest tests/unit tests/integration

# Code formatting and style audit
ruff check src tests eval
```

### Test Suite Breakdown:
- **Unit & Forensics Tests** (`backend/tests/unit/`): 80 tests covering:
  - Unicode NFC normalization, character bounding box extraction, clause heuristics, exponential backoff with full jitter, schema validation, and FileStore atomicity.
  - PDF revision scanner, incremental edit diffing, text hiding, WCAG contrast calculation, and metadata analysis.
  - **17-Document Benign Baseline Suite** (`test_benign_suite.py`): 0 false alarms on standard plain text, headers/footers, links, highlights, AcroForm field edits, Word/Google Docs exports, scanned OCR pages, mixed fonts, embedded graphics, linearized files, PyMuPDF re-saved files, and small 6 pt footnotes.
  - **Cryptographic Signatures** (`test_signatures.py`): Real pyHanko signing with generated 2048-bit RSA keys and X.509 certificates (no mocks).
- **Integration Tests** (`backend/tests/integration/`): 16 tests against live PostgreSQL and Redis containers verifying:
  - Streaming file validation and SHA-256 deduplication
  - Automatic crash recovery and lease reclaiming via `XAUTOCLAIM`
  - Dead-letter routing on corrupt PDF poison pills (`cg:jobs:dead`)
  - Exponential backoff retry on transient faults
  - Background sweeper detection and re-enqueuing
  - End-to-end forensics execution, finding persistence, and analysis run status updates
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
  --pdf-dir ../data/generated \
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
   - Computes sequence-preserving page text diffs across consecutive revisions (`difflib.SequenceMatcher`).
   - Detects modified numeric amounts, altered dates, and party changes, escalating critical findings.
   - Distinguishes legitimate AcroForm field edits via widget bounding box containment (`_is_widget_change`).
   - Verifies trailer `/ID` consistency.
2. **Text Hiding** (`clauseguard.forensics.text_hiding`):
   - Uses PyMuPDF's `get_texttrace()` to detect `type=3` invisible text, sub-2pt font sizes, and off-page text.
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

### 7.4 Evaluation Benchmark Results

Run the evaluation suite against the Module 1 generated dataset:
```bash
python eval/forensics_eval.py --data data/generated
```

#### Ground-Truth Dataset Results (303 Documents across Train/Val & Test)

| Metric | Train/Val Split (259 Docs) | Held-Out Test Split (44 Docs) |
|---|:---:|:---:|
| **Precision** | **100.0%** | **100.0%** |
| **Recall** | **100.0%** | **100.0%** |
| **F1 Score** | **100.0%** | **100.0%** |
| **Recall (`incremental_edit`)** | 10 / 10 (100.0%) | 2 / 2 (100.0%) |
| **Recall (`hidden_text`)** | 24 / 24 (100.0%) | 4 / 4 (100.0%) |
| **FPR (Clean Documents)** | **0.0%** (0 / 85) | **0.0%** (0 / 15) |
| **FPR (Content-Tampered Documents)** | **0.0%** (0 / 141) | **0.0%** (0 / 23) |
| **Incremental Page Match Rate** | 10 / 10 (100.0%) | 2 / 2 (100.0%) |
| **Incremental Value Match in Evidence** | 10 / 10 (100.0%) | 2 / 2 (100.0%) |
| **Latency (p50)** | 6.99 ms | 7.39 ms |
| **Latency (p95)** | 78.48 ms | 106.17 ms |
| **Misses (False Negatives)** | **0** | **0** |
| **False Positives** | **0** | **0** |

---

## 8. Module 4: Consistency Checks

Module 4 checks whether a contract contradicts **itself**: verifying agreement between written words and numbers, internal chronological order, consistent party naming, resolvable cross-references, and coherent clause numbering. It reads the parsed document structure from Module 2 and generates structured `Finding` objects.

### 8.1 Detectors & Consistency Rules

1. **Words vs. Figures** (`clauseguard.consistency.pairs`):
   - **`FIG001` (`figure_words_mismatch`, `CRITICAL` / `HIGH`)**: Compares numeric amounts written in digits against amounts written in words within parenthetical definitions (`$50,000 (Fifty Thousand Dollars)`) or within adjacent 120-character sentence windows. Supports both Western and Indian numbering notation (Lakh and Crore). Escalates to `CRITICAL` if discrepancy $\ge 20\%$.
2. **Date Order & Term Lengths** (`clauseguard.consistency.dates`):
   - **`DATE001` (`effective_date_conflict`, `HIGH`)**: Conflicting effective dates stated across preamble recitals and operational clauses.
   - **`DATE002` (`date_order_conflict`, `CRITICAL`)**: Termination or expiration date precedes the effective commencement date.
   - **`DATE003` (`term_length_conflict`, `MEDIUM`)**: Stated term duration (e.g. "for a period of 12 months") contradicts the computed calendar duration between effective and termination dates.
3. **Party Name Variations** (`clauseguard.consistency.parties`):
   - **`PRT001` (`party_name_variant`, `HIGH`)**: Uses `rapidfuzz` token ratio matching ($\ge 85\%$) to detect altered entity names across clauses (e.g., swapping "Stellar Systems Pvt. Ltd." with "Stellar Networks Pvt. Ltd.").
   - **`PRT002` (`party_case_mismatch`, `LOW`)**: Capitalization variations for formal corporate names.
   - **`PRT003` (`party_name_variant`, `MEDIUM`)**: Undefined party acronyms or initials used without formal introduction.
   - **`PRT004` (`party_name_variant`, `MEDIUM`)**: Single-token short names used in operational or possessive contexts without being defined as aliases.
4. **Cross-Reference Resolution** (`clauseguard.consistency.references`):
   - **`XRF001` (`dangling_reference`, `HIGH` / `MEDIUM`)**: Cross-references pointing to non-existent clauses (`Section 14`, `Clause 9.3`), supporting multi-target ranges (`Sections 4.1 to 4.3`) and lists (`Clauses 2, 5 and 7`). Whitelists external statutory citations (e.g., `U.S.C.`, `C.F.R.`, `FD&C Act`, `Bankruptcy Code`) and external defined agreements (`Section 3.1 of the Merger Agreement`).
5. **Clause Numbering Structure** (`clauseguard.consistency.numbering`):
   - **`NUM001` (`numbering_gap`, `MEDIUM`)**: Detects missing integer clause indices (e.g., `1, 2, 4, 5` skipping `3`).
   - **`NUM002` (`duplicate_clause_number`, `HIGH`)**: Flags duplicated clause numbers, with multi-schedule disambiguation for legitimate annexure numbering restarts.

### 8.2 CLI Usage

Run consistency checks directly on any PDF or parsed document:
```bash
python -m clauseguard.consistency.run /path/to/contract.pdf
```

Example JSON output snippet:
```json
{
  "document_id": "synth_0001_v1",
  "overall_status": "ok",
  "duration_ms": 11.45,
  "findings": [
    {
      "module": "consistency",
      "type": "figure_words_mismatch",
      "severity": "critical",
      "page": 1,
      "clause_ref": "3",
      "evidence": "Rs. 25,00,000 (Rupees Twenty lakh Only)",
      "explanation": "Amount figure Rs. 25,00,000 (numeric value 2500000.0) does not match words 'Rupees Twenty lakh Only' (numeric value 2000000.0). Difference: 25.0%.",
      "details": {
        "rule_id": "FIG001",
        "figure_value": 2500000.0,
        "words_value": 2000000.0,
        "discrepancy_pct": 25.0
      }
    }
  ],
  "detector_statuses": {
    "numbers": {"status": "ok", "duration_ms": 2.1},
    "dates": {"status": "ok", "duration_ms": 1.4},
    "parties": {"status": "ok", "duration_ms": 3.8},
    "references": {"status": "ok", "duration_ms": 2.2},
    "numbering": {"status": "ok", "duration_ms": 1.1}
  }
}
```

### 8.3 Benchmark Results (303 Documents across Train/Val & Test)

Run the consistency benchmark:
```bash
python eval/consistency_eval.py --data data/generated
```

| Metric | Target | Train/Val Split (259 Docs) | Held-Out Test Split (44 Docs) |
|---|:---:|:---:|:---:|
| **Recall (`amount_figure_only`)** | $\ge 90\%$ | **95.0%** (19 / 20) | **100.0%** (3 / 3) |
| **Recall (`date_shift`)** | $\ge 70\%$ | **100.0%** (20 / 20) | **100.0%** (1 / 1) |
| **Recall (`party_swap`)** | $\ge 70\%$ | **96.2%** (25 / 26) | **66.7%** (2 / 3) |
| **Recall (`xref_break`)** | $\ge 90\%$ | **96.5%** (28 / 29) | **100.0%** (3 / 3) |
| **Overall Content Recall** | — | **95.8%** (92 / 96) | **90.0%** (9 / 10) |
| **FPR (Clean Synthetic)** | $\le 2.0\%$ | **0.00%** (0 / 69) | **0.00%** (0 / 9) |
| **FPR (Clean CUAD Commercial)** | $\le 5.0\%$ | **12.5%** (2 / 16) | **0.00%** (0 / 6) |
| **Latency (p50)** | $< 100$ ms | 11.45 ms | 23.21 ms |
| **Latency (p95)** | $< 500$ ms | 138.36 ms | 286.01 ms |
| **1 MB Text Performance** | $< 2.0$ s | **1.21 s** | **1.21 s** |

### 8.4 Known Limitations

- **Both Amount Tampering (`amount_both`)**: When an attacker simultaneously alters both the numerical figure and the written words to identical fraudulent amounts, the contract remains internally consistent and cannot be detected via self-consistency alone (detected upstream via Module 3 forensic byte diffing).
- **Redacted SEC Exhibits**: Historical SEC EDGAR filings containing heavy confidentiality redaction markers (e.g. `Sections 2.3, , 4.4.2 [***]`) may occasionally report dangling references where entire clause sections were redacted prior to regulatory filing.
- **Single-Party Cover Filings**: Bankruptcy court cover sheets preceding the actual agreement where fewer than 2 legal entities are named in the initial header gracefully skip party checking to avoid generating false positives.

---

## 9. Module 5: Clause Classification & Key-Term Extraction

Module 5 provides multi-label clause classification and deterministic key-term attribute extraction across legal agreements. It consumes segmented clauses produced by Module 2, tags each clause across 45 legal categories, extracts critical commercial terms into structured key-value pairs, and persists results into PostgreSQL (`clause_labels` and `document_attributes`).

### 9.1 Architecture & Taxonomy

- **36 Core Contractual Labels**: Mapped from the Atticus Project CUAD v1 benchmark (`governing_law`, `anti_assignment`, `cap_on_liability`, `termination_for_convenience`, `license_grant`, etc.).
- **9 Additional Operational & Risk Labels**: Evaluated via high-precision deterministic rules (`indemnification`, `confidentiality`, `payment_terms`, `unilateral_amendment`, `force_majeure`, `arbitration_or_dispute_resolution`, `waiver_of_rights`, `termination_for_cause`, `auto_renewal`).
- **Character-Offset Alignment**: Ground truth is aligned using exact span character offsets ($\ge 50\%$ span character overlap, or largest overlap when spanning multiple clauses), eliminating the severe inflation caused by legacy token overlap.
- **Hybrid Inference & Long-Clause Sliding Windows**: Combines deterministic regex/keyword pattern matchers with a class-balanced TF-IDF (word 1-2 n-grams + char 3-5 n-grams) LogisticRegression model. Clauses $> 250$ words are chunked into 120-word windows with a stride of 100 words.

### 9.2 Key-Term Attribute Extractors

Deterministic, anti-hallucination extractors located in `clauseguard.clauses.attributes`:
1. `governing_law_jurisdiction`: Normalized jurisdiction name (e.g. Delaware, New York, England and Wales).
2. `termination_notice_days`: Notice timeframe in days for convenience termination.
3. `auto_renews`: Boolean indicating evergreen auto-renewal provisions.
4. `renewal_term_months`: Duration in months of successive renewal periods.
5. `non_renewal_notice_days`: Notice timeframe in days required to prevent contract renewal.
6. `liability_cap`: Structured monetary cap or fee-multiple dictionary.
7. `non_compete_duration_months`: Duration in months of non-compete covenants.
8. `payment_terms_days`: Payment window timeframe in days (e.g. Net 30 -> 30).

### 9.3 Endpoints & CLI Usage

**REST API Endpoints**:
- `GET /v1/documents/{id}/clauses`: Returns segmented clauses with their multi-label classification array, methods (`model`, `rules`, `both`), and scores.
- `GET /v1/documents/{id}/clause-types`: Returns summary frequency counts and highest scores per detected clause type.
- `GET /v1/documents/{id}/attributes`: Returns extracted key-term attributes.

**Standalone CLI Runner**:
```bash
# Analyze any text or PDF file
python -m clauseguard.clauses.run --input /path/to/contract.pdf
python -m clauseguard.clauses.run --text "1. Governing Law. This agreement shall be governed by Delaware law."
```

### 9.4 Official Benchmark (Third Look on Corrected Labels)

> **Notice**: Looks 1 and 2 used inflated token-overlap labels and are void. This official Third Look was evaluated once on the unseen 20% CUAD test split (102 contracts, 2,788 clauses):

| Metric | Test Split Result |
| :--- | :---: |
| **Total Test Samples** | 2,788 clauses |
| **True Positive Test Labels** | 1,052 positive instances |
| **Micro Precision** | **64.89%** |
| **Micro Recall** | **63.59%** |
| **Micro F1** | **64.23%** |
| **Macro Precision** | **49.30%** |
| **Macro Recall** | **49.23%** |
| **Macro F1** | **47.88%** |

*Core High-Support Benchmark Labels*:
- `governing_law`: Precision **96.3%**, Recall **86.5%**, F1 **91.1%** (Support: 89)
- `anti_assignment`: Precision **86.8%**, Recall **83.7%**, F1 **85.2%** (Support: 86)
- `cap_on_liability`: Precision **80.6%**, Recall **81.8%**, F1 **81.2%** (Support: 66)
- `license_grant`: Precision **90.8%**, Recall **71.1%**, F1 **79.7%** (Support: 83)
- `audit_rights`: Precision **71.6%**, Recall **84.2%**, F1 **77.4%** (Support: 57)
- `uncapped_liability`: Precision **68.2%**, Recall **62.5%**, F1 **65.2%** (Support: 24)
- `termination_for_convenience`: Precision **53.7%**, Recall **50.0%**, F1 **51.8%** (Support: 44)

---

## 10. Module 8: Risk Summary, Finding Catalog & Highlight Locator

Module 8 delivers the transparent risk scoring, plain English finding cataloging, and precise visual bounding box resolution required by the ClauseGuard human review workbench.

### 10.1 Finding Catalog (`clauseguard.risk.catalog`)

Every finding type produced by Module 3 (PDF Forensics) and Module 4 (Consistency Engine) is mapped to plain English reviewer guidance:
- **Category**: Classifies findings into `"tampering"` (structural / file-level alterations) or `"inconsistency"` (semantic / internal contract contradictions).
- **Title**: Clear, non-technical title (e.g. `figure_words_mismatch` -> *"Amount in words doesn't match the figure"*).
- **`what_it_means`**: One or two plain-English sentences explaining the issue.
- **`what_to_check`**: One concise, actionable instruction for the human reviewer.
- **Fallback**: Unknown finding types gracefully fall back to formatted string titles rather than raising errors.
- **API Endpoint**: `GET /v1/finding-types` exposes the complete catalog.

### 10.2 Deterministic Risk Aggregator (`clauseguard.risk.aggregate`)

The aggregator computes a pure, deterministic `RiskSummary` without non-deterministic LLM generation:
- **Scoring Function**: `summarize(findings, coverage_inputs, settings) -> RiskSummary`.
- **Weights & Diminishing Returns**:
  - `CRITICAL`: 40 points
  - `HIGH`: 20 points
  - `MEDIUM`: 8 points
  - `LOW` and `uncertain` findings are separated into **minor notes** and never scored.
  - Within each finding type, the first occurrence counts 100%, subsequent occurrences count 25%, and each type is capped at 2x base weight.
  - Overall score is bounded to $[0, 100]$.
- **Risk Band Calibration**:
  - `high`: Any critical finding, forensic tampering escalation, or score $\ge 60$.
  - `medium`: Any high finding or score $\ge 20$.
  - `low`: Otherwise.
- **Coverage & Reliability Warnings**: Evaluates `needs_ocr`, clause count ($< 5$), `analysis_runs` errors, and skipped detectors. Triggers a prominent "Limited analysis" banner and an asterisk on the risk band badge when document structure is degraded.
- **Deterministic Headlines**: Template-based generation combining issue counts and highest-priority findings.
- **Persistence**: Persisted idempotently into the `risk_summaries` table via Alembic migration `0004_risk_summary`, computed during worker execution and lazily computed on API read if missing.

### 10.3 Evidence-Driven Highlight Locator (`clauseguard.risk.highlights`)

Resolves visual bounding box coordinates (`[x0, y0, x1, y1]`) on rendered PDF pages for findings that lack explicit parser bounding boxes:
- **Multi-Tier Resolution**:
  1. Preserves existing finding bounding boxes when already populated.
  2. Searches page span text for distinctive tokens (`figure`, `words`, `party`, `quote`, `target`), sorted longest-first.
  3. Multi-span token matching handles phrases spanning across line and layout breaks, taking the union bounding box.
  4. Heading fallback marks approximate highlights (`approximate=True`) at the clause start position.
- **Coordinate System**: Pure PyMuPDF points with a top-left origin, explicitly accounting for page rotation angles (0, 90, 180, 270 degrees).

### 10.4 REST API Reference

- `GET /v1/documents?limit=20&offset=0&status=succeeded`: Returns document list with risk score, band, and severity counts.
- `GET /v1/documents/{id}/risk`: Detailed deterministic risk summary, band, top reasons, and coverage notes.
- `GET /v1/documents/{id}/file`: Streams the stored PDF inline as `application/pdf` directly from content-addressed storage.
- `DELETE /v1/documents/{id}`: Cascading deletion of document records across all tables and stored file (HTTP 204, idempotent).
- `GET /v1/documents/{id}/findings`: Enriched finding records with category, title, `what_it_means`, `what_to_check`, feedback, and highlights.
- `POST /v1/findings/{id}/feedback`: Records reviewer verdict (`verdict: "confirmed" | "dismissed"`, optional note).
- `DELETE /v1/findings/{id}/feedback`: Clears reviewer verdict.
- `GET /v1/jobs/{id}`: Returns execution stages (`upload`, `parse`, `forensics`, `consistency`, `clauses`, `summary`) with status (`pending`, `running`, `done`, `error`, `skipped`).
- `GET /v1/finding-types`: Complete finding catalog mapping.

### 10.5 Risk Evaluation Benchmark (`eval/risk_eval.py`)

Run the risk aggregator benchmark on generated datasets:
```bash
python eval/risk_eval.py --data data/generated
python eval/risk_eval.py --data data/generated_seed4242
```

Results across 474 contracts in `data/generated_seed4242`:
- `clean_synthetic`: **100.0% Low band** (Target $\ge 98.0\%$) -> **MET**
- `tamper_incremental_edit`: **100.0% High band** (Target $\ge 95.0\%$) -> **MET**
- `tamper_hidden_text`: **100.0% High band** (Target $\ge 95.0\%$) -> **MET**
- `tamper_amount_figure_only`: **100.0% Med/High band** (Target $\ge 90.0\%$) -> **MET**
- `tamper_date_shift`: **100.0% Med/High band** (Target $\ge 90.0\%$) -> **MET**
- `tamper_xref_break`: **100.0% Med/High band** (Target $\ge 90.0\%$) -> **MET**



