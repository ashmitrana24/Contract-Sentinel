"""CLI for the datagen package.

Commands:
  generate  - produce a labeled dataset from source contracts
  verify    - quality-gate: check all PDFs against their labels
  stats     - print split and tamper-type statistics
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Annotated

import typer

app = typer.Typer(
    name="datagen",
    help="Legal-document fraud & integrity dataset generator.",
    add_completion=False,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("datagen.cli")


@app.command()
def generate(
    seed: Annotated[int, typer.Option("--seed", help="Master random seed.")] = 42,
    n_sources: Annotated[
        int, typer.Option("--n-sources", help="Number of source contracts to use.")
    ] = 150,
    out: Annotated[
        Path,
        typer.Option("--out", help="Output directory for generated PDFs and labels."),
    ] = Path("data/generated"),
    cuad_dir: Annotated[
        Path | None,
        typer.Option("--cuad-dir", help="Directory containing CUAD plain-text .txt files."),
    ] = None,
) -> None:
    """Generate a labeled dataset of clean and tampered contract PDFs."""
    from datagen.pipeline import run_pipeline
    from datagen.split import assign_splits

    logger.info("Generating dataset: seed=%d, n_sources=%d, out=%s", seed, n_sources, out)

    out.mkdir(parents=True, exist_ok=True)

    labels = run_pipeline(
        seed=seed,
        n_sources=n_sources,
        out_dir=out,
        cuad_dir=cuad_dir,
    )

    labels = assign_splits(labels, seed=seed)

    # Re-write labels with split assignments
    from datagen.pipeline import _write_labels

    _write_labels(labels, out)

    typer.echo(f"\nGenerated {len(labels)} documents in {out}")
    typer.echo(f"  clean:    {sum(1 for lbl in labels if not lbl.is_tampered)}")
    typer.echo(f"  tampered: {sum(1 for lbl in labels if lbl.is_tampered)}")


@app.command()
def verify(
    inp: Annotated[
        Path,
        typer.Option(
            "--in",
            help="Directory containing generated PDFs and labels.jsonl.",
        ),
    ] = Path("data/generated"),
) -> None:
    """Verify all generated PDFs against their ground-truth labels."""
    from datagen.verify import verify_dataset

    ok = verify_dataset(inp)
    if not ok:
        raise typer.Exit(code=1)


@app.command()
def stats(
    inp: Annotated[
        Path,
        typer.Option(
            "--in",
            help="Directory containing generated PDFs and labels.jsonl.",
        ),
    ] = Path("data/generated"),
) -> None:
    """Print dataset statistics (counts by split, source type, tamper type)."""
    from datagen.models import DocLabel
    from datagen.split import split_stats

    labels_path = inp / "labels.jsonl"
    if not labels_path.exists():
        typer.echo(f"ERROR: labels.jsonl not found in {inp}", err=True)
        raise typer.Exit(code=1)

    labels: list[DocLabel] = []
    with labels_path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                labels.append(DocLabel.model_validate_json(line))

    stats_data = split_stats(labels)

    typer.echo("\n=== Dataset Statistics ===")
    typer.echo(f"Total documents: {len(labels)}")
    typer.echo(f"  Clean:    {sum(1 for lbl in labels if not lbl.is_tampered)}")
    typer.echo(f"  Tampered: {sum(1 for lbl in labels if lbl.is_tampered)}")
    typer.echo("")

    for split in ["train", "val", "test"]:
        s = stats_data[split]
        typer.echo(f"[{split.upper()}]")
        typer.echo(f"  Documents : {s['n_docs']}  (sources: {s['n_sources']})")
        typer.echo(f"  Clean / Tampered: {s['n_clean']} / {s['n_tampered']}")
        typer.echo(f"  Source types : {s['source_types']}")
        typer.echo("  Tamper distribution:")
        for ttype, count in sorted(s["tamper_distribution"].items()):
            typer.echo(f"    {ttype:30s}: {count}")
        typer.echo("")


if __name__ == "__main__":
    app()
