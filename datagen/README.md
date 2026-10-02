# datagen – Legal-Document Fraud & Integrity Dataset Generator

Module 1 of the legal-document fraud and integrity analysis platform.
Generates a labeled dataset of clean and tampered contract PDFs.

---

## Quick Setup

```bash
# From the repo root:
cd datagen
pip install -e .
```

> **Python 3.11+ required.** All dependencies are declared in `pyproject.toml`.

---

## CUAD Data (Optional but recommended)

The generator can use contracts from the [CUAD v1](https://www.atticusprojectai.org/cuad)
dataset (Contract Understanding Atticus Dataset, CC BY 4.0).

### Manual Download Steps

1. Go to the CUAD Zenodo page (search "CUAD contract understanding" on https://zenodo.org)
   or the Hugging Face page: https://huggingface.co/datasets/cuad
2. Download the plain-text contract files (`.txt` format).
3. Place all `.txt` files into `datagen/data/raw/cuad/`.

The directory structure should look like:
```
datagen/data/raw/cuad/
├── OFFICEDEPOT_contract.txt
├── AMAZON_MSA.txt
└── ...
```

If CUAD is not present, the generator falls back to 100% synthetic contracts
with no errors.

---

## CLI Usage

All commands are run from the `datagen/` directory.

```bash
# Generate a dataset (synthetic only, 150 source contracts)
python -m datagen generate --seed 42 --n-sources 150 --out data/generated

# Generate with CUAD (if downloaded)
python -m datagen generate --seed 42 --n-sources 150 --out data/generated \
    --cuad-dir data/raw/cuad

# Verify the generated dataset (quality gate)
python -m datagen verify --in data/generated

# Print statistics
python -m datagen stats --in data/generated
```

Exit codes: `0` = success, `1` = failure (any verification check failed).

---

## Running Tests

```bash
cd datagen
pytest
```

Run with coverage:
```bash
pytest --cov=datagen --cov-report=term-missing
```

Lint (zero tolerance):
```bash
ruff check src/ tests/
```

---

## Label Schema

Each document has one line in `labels.jsonl` (and an entry in `labels.json`):

| Field | Type | Description |
|---|---|---|
| `doc_id` | `str` | Unique document identifier |
| `source_id` | `str` | Source contract identifier |
| `source_type` | `"synthetic"\|"cuad"` | Origin of the contract |
| `is_tampered` | `bool` | Whether this doc has been tampered |
| `tamper_types` | `list[str]` | List of tamper type names (empty if clean) |
| `tamper_class` | `"content"\|"file"\|null` | Tamper class |
| `tamper_details` | `list[TamperDetail]` | Per-tamper details |
| `seed` | `int` | Random seed used |
| `generator_version` | `str` | Generator version string |
| `sha256` | `str` | SHA-256 hex digest of the PDF file |
| `split` | `"train"\|"val"\|"test"` | Dataset split |

### TamperDetail fields

| Field | Description |
|---|---|
| `tamper_type` | Name of the tamper operation |
| `page` | 0-indexed page number (file-level tampers) |
| `clause_id` | Affected clause ID (e.g. `"4.2"`) |
| `original_value` | Value before tampering |
| `tampered_value` | Value after tampering |
| `subtype` | Sub-classification of the tamper |
| `dangling_xrefs` | Clause IDs with dangling cross-references (clause_delete only) |

---

## Tamper Types

### Content Tampers (pre-render)

| Type | Description |
|---|---|
| `amount_figure_only` | Change the numeric figure but leave the words → figure/words mismatch |
| `amount_both` | Change figure AND words consistently (hard case for detectors) |
| `date_shift` | Move termination date before effective date, or change one repeated date |
| `party_swap` | Replace exactly one occurrence of a party name with a variant |
| `clause_delete` | Remove a clause without renumbering (may create dangling xrefs) |
| `clause_insert` | Insert a risky clause (unilateral termination, unlimited liability, etc.) |
| `xref_break` | Change one valid cross-reference to a non-existent clause |

### File-Level Tampers (post-render)

| Type | Description |
|---|---|
| `incremental_edit` | Simulate post-signing edit: redact a value, insert replacement, save with `incremental=True`. Produces ≥ 2 `%%EOF` markers |
| `hidden_text` | Insert a clause-like sentence in white/0.5pt text. Extractable but visually invisible |

---

## Dataset Structure

```
data/generated/
├── synth_0000_clean.pdf
├── synth_0000_v0.pdf
├── synth_0000_v1.pdf
├── ...
├── labels.jsonl        (one JSON line per document)
└── labels.json         (full array, for tooling convenience)
```

---

## Split Strategy

Splits are **by source contract** (70% train / 15% val / 15% test).
All variants of one source contract (clean + tampered) always land in the
same split, preventing any information leakage between splits.

---

## Architecture

```
src/datagen/
├── __init__.py          version constant
├── __main__.py          entry point
├── cli.py               Typer CLI (generate / verify / stats)
├── config.py            global constants and path helpers
├── models.py            Pydantic v2: Contract, Clause, KeyFact, DocLabel …
├── pipeline.py          orchestrate source → tamper → render → label
├── split.py             deterministic 70/15/15 split
├── verify.py            quality-gate verifier
├── synth/
│   ├── builder.py       seeded contract generator
│   └── templates.py     clause bank + contract-type metadata
├── sources/
│   └── cuad_loader.py   CUAD .txt heuristic loader
├── render/
│   └── pdf_renderer.py  ReportLab deterministic renderer
└── tamper/
    ├── base.py           abstract Tamper, TamperNotApplicable
    ├── amount.py         amount_figure_only, amount_both
    ├── dates.py          date_shift
    ├── party.py          party_swap
    ├── clauses.py        clause_delete, clause_insert
    ├── xref.py           xref_break
    ├── hidden_text.py    hidden_text (file-level)
    └── incremental.py    incremental_edit (file-level)
```
