"""Deterministic PDF renderer using ReportLab.

Design decisions (see DECISIONS.md):
- invariant=1 passed to Canvas for reproducible PDF internals.
- Standard built-in Type-1 fonts only (Helvetica family), no external TTF.
- Fixed PDF metadata (creation date, producer) for clean documents.
- Tampered docs get a later modification date and different producer.
- All measurements in points (72 pt = 1 inch).
"""

from __future__ import annotations

import io
import logging
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import (
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from datagen.config import (
    MARGIN_PT,
    PDF_CREATION_DATE,
    PDF_PRODUCER_CLEAN,
    PDF_PRODUCER_TAMPERED,
)
from datagen.models import Contract

logger = logging.getLogger(__name__)

PAGE_W, PAGE_H = A4  # 595.28 x 841.89 pt
MARGIN = MARGIN_PT


def _styles() -> dict[str, ParagraphStyle]:
    """Build a minimal set of named styles."""
    base = getSampleStyleSheet()
    s: dict[str, ParagraphStyle] = {}

    s["title"] = ParagraphStyle(
        "ContractTitle",
        parent=base["Normal"],
        fontName="Helvetica-Bold",
        fontSize=14,
        leading=18,
        alignment=TA_CENTER,
        spaceAfter=12,
    )
    s["meta"] = ParagraphStyle(
        "ContractMeta",
        parent=base["Normal"],
        fontName="Helvetica",
        fontSize=9,
        leading=13,
        alignment=TA_CENTER,
        spaceAfter=4,
    )
    s["heading"] = ParagraphStyle(
        "ClauseHeading",
        parent=base["Normal"],
        fontName="Helvetica-Bold",
        fontSize=10,
        leading=14,
        spaceBefore=10,
        spaceAfter=4,
        alignment=TA_LEFT,
    )
    s["body"] = ParagraphStyle(
        "ClauseBody",
        parent=base["Normal"],
        fontName="Helvetica",
        fontSize=9,
        leading=13,
        spaceAfter=6,
        alignment=TA_JUSTIFY,
    )
    s["sig_header"] = ParagraphStyle(
        "SigHeader",
        parent=base["Normal"],
        fontName="Helvetica-Bold",
        fontSize=10,
        leading=14,
        spaceBefore=24,
        spaceAfter=8,
        alignment=TA_CENTER,
    )
    s["sig_cell"] = ParagraphStyle(
        "SigCell",
        parent=base["Normal"],
        fontName="Helvetica",
        fontSize=9,
        leading=13,
        alignment=TA_LEFT,
    )
    return s


def _signature_block(contract: Contract, styles: dict[str, ParagraphStyle]) -> list:
    """Build signature table flowable."""
    parties = contract.parties[:4]  # at most 4 parties on sig page
    if not parties:
        return []

    story: list = [Paragraph("IN WITNESS WHEREOF", styles["sig_header"])]

    col_w = (PAGE_W - 2 * MARGIN) / max(len(parties), 1)
    col_w = min(col_w, 200)  # cap column width

    def _cell(label: str, name: str) -> list[Paragraph]:
        return [
            Paragraph(f"<b>{label}</b>", styles["sig_cell"]),
            Paragraph(name, styles["sig_cell"]),
            Paragraph("Signature: _____________________", styles["sig_cell"]),
            Paragraph("Name: _____________________", styles["sig_cell"]),
            Paragraph("Title: _____________________", styles["sig_cell"]),
            Paragraph("Date: _____________________", styles["sig_cell"]),
        ]

    row = [_cell(p.role or f"Party {i + 1}", p.name) for i, p in enumerate(parties)]
    tbl = Table(
        [row],
        colWidths=[col_w] * len(parties),
    )
    tbl.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LINEAFTER", (0, 0), (-2, 0), 0.5, colors.black),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    story.append(tbl)
    return story


def render_contract_to_bytes(
    contract: Contract,
    *,
    is_tampered: bool = False,
) -> bytes:
    """Render a Contract to a PDF byte string.

    Parameters
    ----------
    contract:
        The structured contract model to render.
    is_tampered:
        If True, uses the "tampered" producer string in metadata.

    Returns
    -------
    bytes
        Raw PDF bytes.
    """
    buf = io.BytesIO()
    styles = _styles()

    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=MARGIN,
        rightMargin=MARGIN,
        topMargin=MARGIN,
        bottomMargin=MARGIN,
        title=contract.title,
        author="datagen",
        subject=contract.contract_type,
        creator="datagen",
        # invariant makes IDs / checksums reproducible within one run
        invariant=1,
    )

    story: list = []

    # ----- Title & preamble --------------------------------------------------
    story.append(Paragraph(contract.title.upper(), styles["title"]))

    if contract.parties:
        parts_str = " and ".join(
            f"<b>{p.name}</b> ({p.role})" if p.role else f"<b>{p.name}</b>"
            for p in contract.parties
        )
        story.append(Paragraph(f"Between: {parts_str}", styles["meta"]))

    if contract.effective_date:
        story.append(Paragraph(f"Effective Date: {contract.effective_date}", styles["meta"]))
    if contract.termination_date:
        story.append(Paragraph(f"Termination Date: {contract.termination_date}", styles["meta"]))
    if contract.governing_law:
        story.append(Paragraph(f"Governing Law: {contract.governing_law}", styles["meta"]))

    story.append(Spacer(1, 12))  # 12pt spacer

    # ----- Clauses -----------------------------------------------------------
    for clause in contract.clauses:
        block = [
            Paragraph(
                f"{clause.id}. {clause.heading}",
                styles["heading"],
            ),
            Paragraph(_escape(clause.text), styles["body"]),
        ]
        story.append(KeepTogether(block))

    # ----- Signature block ---------------------------------------------------
    story.append(PageBreak())
    story.extend(_signature_block(contract, styles))

    doc.build(story)
    raw = buf.getvalue()

    # Patch metadata into the PDF byte stream.
    producer = PDF_PRODUCER_TAMPERED if is_tampered else PDF_PRODUCER_CLEAN
    raw = _patch_metadata(raw, PDF_CREATION_DATE, producer, is_tampered=is_tampered)
    return raw


def _escape(text: str) -> str:
    """Escape characters that confuse ReportLab's Paragraph XML parser."""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _patch_metadata(
    pdf_bytes: bytes,
    creation_date: str,
    producer: str,
    *,
    is_tampered: bool,
) -> bytes:
    """Set PDF metadata (producer, creation date) using pikepdf for correctness.

    Using pikepdf avoids the byte-level regex fragility of patching the raw
    ReportLab output. pikepdf reads/writes the Info dict properly.
    """
    import io

    import pikepdf

    with pikepdf.open(io.BytesIO(pdf_bytes)) as pdf:
        with pdf.open_metadata() as meta:
            # Set producer
            meta["pdf:Producer"] = producer
            meta["xmp:CreatorTool"] = "datagen"

        # Also set Info dict directly
        pdf.docinfo["/Producer"] = producer
        pdf.docinfo["/Creator"] = "datagen"
        pdf.docinfo["/CreationDate"] = creation_date

        if is_tampered:
            mod_date = "D:20241231235959+00'00'"
            pdf.docinfo["/ModDate"] = mod_date

        buf = io.BytesIO()
        pdf.save(buf)
        return buf.getvalue()


def render_contract_to_file(
    contract: Contract,
    out_path: Path,
    *,
    is_tampered: bool = False,
) -> None:
    """Render a Contract to a PDF file at *out_path*."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    pdf_bytes = render_contract_to_bytes(contract, is_tampered=is_tampered)
    out_path.write_bytes(pdf_bytes)
    logger.debug("Rendered %s -> %s (%d bytes)", contract.id, out_path, len(pdf_bytes))
