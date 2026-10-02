"""Global configuration and constants."""

from __future__ import annotations

from pathlib import Path

# ---------------------------------------------------------------------------
# Fixed creation date used for clean-doc PDF metadata (deterministic output).
# ---------------------------------------------------------------------------
PDF_CREATION_DATE = "D:20240101000000+00'00'"
PDF_PRODUCER_CLEAN = "datagen-0.1.0"
PDF_PRODUCER_TAMPERED = "Adobe Acrobat 23.0"

# ---------------------------------------------------------------------------
# Page / rendering constants
# ---------------------------------------------------------------------------
PAGE_WIDTH_PT = 595.0  # A4
PAGE_HEIGHT_PT = 842.0
MARGIN_PT = 72.0  # 1 inch

# ---------------------------------------------------------------------------
# Generator internals
# ---------------------------------------------------------------------------
GENERATOR_VERSION = "datagen-0.1.0"

# ---------------------------------------------------------------------------
# Data directories (relative to the project root; callers resolve them)
# ---------------------------------------------------------------------------
_HERE = Path(__file__).parent


def data_root(base: Path | None = None) -> Path:
    """Return base data directory, defaulting to datagen/data/."""
    if base is not None:
        return base
    return _HERE.parents[2] / "data"


def raw_dir(base: Path | None = None) -> Path:
    return data_root(base) / "raw"


def cuad_dir(base: Path | None = None) -> Path:
    return raw_dir(base) / "cuad"


def generated_dir(base: Path | None = None) -> Path:
    return data_root(base) / "generated"
