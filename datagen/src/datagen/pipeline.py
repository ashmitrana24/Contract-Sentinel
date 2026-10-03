"""Generation pipeline.

Orchestrates:
  1. Load source contracts (synthetic + CUAD).
  2. For each source contract, generate:
     - 1 clean document
     - 2-3 tampered variants (one tamper each; ~10% get two combined)
  3. Assign doc_ids, render PDFs, compute sha256 hashes.
  4. Write labels.jsonl and labels.json.

The pipeline is deterministic for a given (seed, n_sources).
"""

from __future__ import annotations

import hashlib
import json
import logging
import random
from pathlib import Path

from datagen import GENERATOR_VERSION
from datagen.models import (
    CONTENT_TAMPERS,
    FILE_TAMPERS,
    Contract,
    DocLabel,
    SourceType,
    TamperClass,
    TamperDetail,
    TamperType,
)
from datagen.render.pdf_renderer import render_contract_to_bytes
from datagen.tamper.amount import AmountBothTamper, AmountFigureOnlyTamper
from datagen.tamper.base import TamperNotApplicable
from datagen.tamper.clauses import ClauseDeleteTamper, ClauseInsertTamper
from datagen.tamper.dates import DateShiftTamper
from datagen.tamper.hidden_text import HiddenTextTamper
from datagen.tamper.incremental import IncrementalEditTamper
from datagen.tamper.party import PartySwapTamper
from datagen.tamper.xref import XrefBreakTamper

logger = logging.getLogger(__name__)

# All available tampers, instantiated once
_CONTENT_TAMPERS = [
    AmountFigureOnlyTamper(),
    AmountBothTamper(),
    DateShiftTamper(),
    PartySwapTamper(),
    ClauseDeleteTamper(),
    ClauseInsertTamper(),
    XrefBreakTamper(),
]

_FILE_TAMPERS = [
    IncrementalEditTamper(),
    HiddenTextTamper(),
]

_ALL_TAMPERS = _CONTENT_TAMPERS + _FILE_TAMPERS


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _tamper_class(tamper_type: TamperType) -> TamperClass:
    if tamper_type in CONTENT_TAMPERS:
        return TamperClass.CONTENT
    return TamperClass.FILE


def _pick_tampers(
    rng: random.Random,
    combined_prob: float = 0.10,
) -> list[type]:
    """Pick 1 or 2 tamper types for one variant.

    Returns a list of tamper instances (length 1 or 2).
    """
    # Prefer content tampers for most variants; file tampers mixed in
    pool = _CONTENT_TAMPERS + _FILE_TAMPERS
    first = rng.choice(pool)
    if rng.random() < combined_prob:
        # Pick a second tamper of a DIFFERENT class
        remaining = [t for t in pool if t is not first]
        if remaining:
            second = rng.choice(remaining)
            return [first, second]
    return [first]


def _apply_content_tampers(
    contract: Contract,
    tamper_instances: list,
    rng: random.Random,
) -> tuple[Contract, list[TamperDetail]]:
    """Apply all content tampers in sequence, returning modified contract + details."""
    result = contract
    details: list[TamperDetail] = []
    for t in tamper_instances:
        result, detail = t.apply(result, rng)
        details.append(detail)
    return result, details


def _generate_variants(
    source_contract: Contract,
    source_type: SourceType,
    seed: int,
    out_dir: Path,
    n_variants: int,
    expected_clauses_out: dict[str, list[dict[str, str]]] | None = None,
) -> list[DocLabel]:
    """Generate clean + tampered PDFs for one source contract.

    Returns list of DocLabel (including the clean one).
    """
    labels: list[DocLabel] = []

    # ---- Clean document ----
    clean_id = f"{source_contract.id}_clean"
    clean_bytes = render_contract_to_bytes(source_contract, is_tampered=False)
    clean_path = out_dir / f"{clean_id}.pdf"
    clean_path.write_bytes(clean_bytes)

    if expected_clauses_out is not None:
        expected_clauses_out[clean_id] = [
            {"id": c.id, "heading": c.heading} for c in source_contract.clauses
        ]

    labels.append(
        DocLabel(
            doc_id=clean_id,
            source_id=source_contract.id,
            source_type=source_type,
            is_tampered=False,
            tamper_types=[],
            tamper_class=None,
            tamper_details=[],
            seed=seed,
            generator_version=GENERATOR_VERSION,
            sha256=_sha256(clean_bytes),
        )
    )

    # ---- Tampered variants ----
    for variant_idx in range(n_variants):
        variant_rng = random.Random(seed + variant_idx + 1)
        tamper_list = _pick_tampers(variant_rng)

        # Separate content vs file tampers
        content_t = [t for t in tamper_list if type(t) in {type(x) for x in _CONTENT_TAMPERS}]
        file_t = [t for t in tamper_list if type(t) in {type(x) for x in _FILE_TAMPERS}]

        # Work on a fresh deep copy of the contract
        working_contract = source_contract.model_copy_deep()
        all_details: list[TamperDetail] = []
        applicable = True

        # Apply content tampers first
        for tamper in content_t:
            try:
                working_contract, detail = tamper.apply(working_contract, variant_rng)
                all_details.append(detail)
            except TamperNotApplicable as exc:
                logger.debug(
                    "Tamper %s not applicable to %s variant %d: %s",
                    type(tamper).__name__,
                    source_contract.id,
                    variant_idx,
                    exc,
                )
                applicable = False
                break

        if not applicable:
            continue

        # Render after content tampers
        try:
            pdf_bytes = render_contract_to_bytes(working_contract, is_tampered=bool(all_details))
        except Exception as exc:
            logger.warning(
                "Render failed for %s variant %d: %s",
                source_contract.id,
                variant_idx,
                exc,
            )
            continue

        # Apply file-level tampers
        for tamper in file_t:
            try:
                pdf_bytes, detail = tamper.apply(pdf_bytes, variant_rng)
                all_details.append(detail)
            except TamperNotApplicable as exc:
                logger.debug(
                    "File tamper %s not applicable to %s variant %d: %s",
                    type(tamper).__name__,
                    source_contract.id,
                    variant_idx,
                    exc,
                )
                # Still write the partially-tampered version
                break

        if not all_details:
            logger.debug(
                "No tampers applied to %s variant %d, skipping.", source_contract.id, variant_idx
            )
            continue

        variant_id = f"{source_contract.id}_v{variant_idx}"
        variant_path = out_dir / f"{variant_id}.pdf"
        variant_path.write_bytes(pdf_bytes)

        if expected_clauses_out is not None:
            expected_clauses_out[variant_id] = [
                {"id": c.id, "heading": c.heading} for c in working_contract.clauses
            ]

        tamper_types = [d.tamper_type for d in all_details]
        # Determine dominant tamper class
        has_file = any(tt in FILE_TAMPERS for tt in tamper_types)
        has_content = any(tt in CONTENT_TAMPERS for tt in tamper_types)
        if has_file and has_content:
            dom_class = TamperClass.FILE  # file takes precedence for forensics
        elif has_file:
            dom_class = TamperClass.FILE
        else:
            dom_class = TamperClass.CONTENT

        labels.append(
            DocLabel(
                doc_id=variant_id,
                source_id=source_contract.id,
                source_type=source_type,
                is_tampered=True,
                tamper_types=tamper_types,
                tamper_class=dom_class,
                tamper_details=all_details,
                seed=seed,
                generator_version=GENERATOR_VERSION,
                sha256=_sha256(pdf_bytes),
            )
        )

    return labels


def run_pipeline(
    seed: int,
    n_sources: int,
    out_dir: Path,
    cuad_dir: Path | None = None,
) -> list[DocLabel]:
    """Run the full generation pipeline.

    Parameters
    ----------
    seed:
        Master random seed.
    n_sources:
        Number of source contracts to generate/load.
    out_dir:
        Directory to write generated PDFs and labels.
    cuad_dir:
        Optional path to CUAD plain-text files.

    Returns
    -------
    list[DocLabel]
        All generated document labels.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    master_rng = random.Random(seed)

    # --- Load sources ---
    from datagen.sources.cuad_loader import load_cuad_contracts
    from datagen.synth.builder import build_synthetic_contract

    cuad_contracts: list[Contract] = []
    if cuad_dir and cuad_dir.exists():
        # Load up to 60% of n_sources from CUAD
        max_cuad = int(n_sources * 0.60)
        cuad_contracts = load_cuad_contracts(cuad_dir, max_contracts=max_cuad)
        logger.info("Loaded %d CUAD contracts.", len(cuad_contracts))

    n_cuad = len(cuad_contracts)
    n_synthetic = n_sources - n_cuad
    logger.info(
        "Generating %d synthetic + %d CUAD = %d source contracts.", n_synthetic, n_cuad, n_sources
    )

    # Build synthetic contracts
    used_names: set[str] = set()
    synthetic_contracts: list[Contract] = []
    for i in range(n_synthetic):
        contract_seed = master_rng.randint(0, 2**31)
        synth_rng = random.Random(contract_seed)
        contract = build_synthetic_contract(
            contract_id=f"synth_{i:04d}",
            rng=synth_rng,
            used_names=used_names,
        )
        synthetic_contracts.append(contract)

    all_sources: list[tuple[Contract, SourceType]] = [
        (c, SourceType.SYNTHETIC) for c in synthetic_contracts
    ] + [(c, SourceType.CUAD) for c in cuad_contracts]

    # --- Generate PDFs ---
    all_labels: list[DocLabel] = []
    all_expected_clauses: dict[str, list[dict[str, str]]] = {}

    for contract, source_type in all_sources:
        contract_seed = master_rng.randint(0, 2**31)
        n_variants = master_rng.randint(2, 3)
        try:
            labels = _generate_variants(
                contract,
                source_type,
                seed=contract_seed,
                out_dir=out_dir,
                n_variants=n_variants,
                expected_clauses_out=all_expected_clauses,
            )
            all_labels.extend(labels)
        except Exception as exc:
            logger.warning("Failed to generate variants for %s: %s", contract.id, exc)

    logger.info(
        "Generated %d total documents (%d source contracts).",
        len(all_labels),
        n_sources,
    )

    # --- Write labels ---
    _write_labels(all_labels, out_dir, all_expected_clauses)
    return all_labels


def _write_labels(
    labels: list[DocLabel],
    out_dir: Path,
    expected_clauses: dict[str, list[dict[str, str]]] | None = None,
) -> None:
    """Write labels.jsonl, labels.json, and optional expected_clauses.json sidecar."""
    jsonl_path = out_dir / "labels.jsonl"
    json_path = out_dir / "labels.json"

    with jsonl_path.open("w", encoding="utf-8") as f:
        for label in labels:
            f.write(label.model_dump_json() + "\n")

    with json_path.open("w", encoding="utf-8") as f:
        json.dump([label.model_dump() for label in labels], f, indent=2, default=str)

    if expected_clauses:
        expected_path = out_dir / "expected_clauses.json"
        with expected_path.open("w", encoding="utf-8") as f:
            json.dump(expected_clauses, f, indent=2)

    logger.info("Labels written to %s", out_dir)
