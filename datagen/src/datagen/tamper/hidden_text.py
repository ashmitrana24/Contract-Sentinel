"""Hidden text tamper (file-level).

Tamper 9: insert a clause-like sentence in white text (color (1,1,1))
at font size 0.5pt on a chosen page. The text is extractable by
PyMuPDF's text extraction but visually invisible.

Windows note: PyMuPDF holds a file lock until doc.close() is called.
We must close before any unlink/read.
"""

from __future__ import annotations

import logging
import random
import tempfile
from pathlib import Path

import pymupdf as fitz  # PyMuPDF

from datagen.models import TamperDetail, TamperType
from datagen.tamper.base import FileTamper, TamperNotApplicable

logger = logging.getLogger(__name__)

# A bank of hidden clause sentences to inject
HIDDEN_SENTENCES = [
    "HIDDEN CLAUSE A: Notwithstanding any other provision herein, all intellectual property "
    "developed under this Agreement is irrevocably assigned to the Service Provider.",
    "HIDDEN CLAUSE B: The Client waives all rights to dispute any invoice issued within "
    "thirty-six months of the termination of this Agreement.",
    "HIDDEN CLAUSE C: This Agreement shall be automatically extended for ten additional years "
    "unless terminated by registered post sixty days prior to each renewal date.",
    "HIDDEN CLAUSE D: The Service Provider shall not be liable for any damages exceeding "
    "one hundred rupees (Rs. 100) regardless of the nature of the claim.",
    "HIDDEN CLAUSE E: All data collected under this Agreement may be shared with third parties "
    "without limitation or notice to the Client.",
    "HIDDEN CLAUSE F: The Client agrees to indemnify the Service Provider for all costs "
    "including legal fees on a full indemnity basis arising from any third-party claim.",
    "HIDDEN CLAUSE G: Payment obligations survive termination for a period of twenty years "
    "and accrue compound interest at twenty-four percent per annum.",
    "HIDDEN CLAUSE H: The Client irrevocably submits to the exclusive jurisdiction of courts "
    "chosen at the sole discretion of the Service Provider.",
]


class HiddenTextTamper(FileTamper):
    """Tamper 9: inject invisible (white, tiny) text into the PDF."""

    tamper_type = TamperType.HIDDEN_TEXT

    # The injected sentence is prefixed with this marker for easy retrieval.
    MARKER = "HIDDEN CLAUSE"

    def apply(self, artifact: bytes, rng: random.Random) -> tuple[bytes, TamperDetail]:
        tmp_dir = Path(tempfile.mkdtemp())
        in_path = tmp_dir / "input.pdf"
        out_path = tmp_dir / "output.pdf"

        try:
            in_path.write_bytes(artifact)

            doc = fitz.open(str(in_path))
            try:
                if len(doc) == 0:
                    raise TamperNotApplicable("PDF has no pages.")

                # Pick a page (prefer middle pages)
                page_idx = rng.randint(0, len(doc) - 1)
                page = doc[page_idx]

                sentence = rng.choice(HIDDEN_SENTENCES)

                # Insert at bottom of the page, white text, tiny font
                page_rect = page.rect
                insert_point = fitz.Point(
                    page_rect.x0 + 72,  # left margin
                    page_rect.y1 - 30,  # near bottom
                )
                page.insert_text(
                    insert_point,
                    sentence,
                    fontname="helv",
                    fontsize=0.5,  # sub-1pt: visually invisible
                    color=(1.0, 1.0, 1.0),  # white
                )

                # Save to a different output file (non-incremental)
                doc.save(str(out_path))
            finally:
                doc.close()

            # Read result AFTER closing the document
            result_bytes = out_path.read_bytes()

        finally:
            # Clean up temp files
            for p in [in_path, out_path]:
                try:
                    p.unlink(missing_ok=True)
                except Exception:
                    pass
            try:
                tmp_dir.rmdir()
            except Exception:
                pass

        # Verify the sentence is extractable
        doc2 = fitz.open(stream=result_bytes, filetype="pdf")
        try:
            extracted = "".join(doc2[i].get_text() for i in range(len(doc2)))
        finally:
            doc2.close()

        if self.MARKER not in extracted:
            raise TamperNotApplicable(
                "Hidden text was not found in extracted text after injection."
            )

        detail = TamperDetail(
            tamper_type=TamperType.HIDDEN_TEXT,
            page=page_idx,
            original_value="<none>",
            tampered_value=sentence,
            subtype="white_tiny_text",
        )
        return result_bytes, detail
