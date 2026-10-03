"""Text normalisation utilities.

Rules:
- Unicode NFC normalisation.
- Replace non-breaking spaces (U+00A0) and narrow no-break spaces (U+202F)
  with regular spaces.
- Replace zero-width spaces (U+200B), zero-width no-break spaces (U+FEFF),
  and other invisible Unicode with nothing.
- Collapse runs of spaces/tabs within a line to a single space.
- Preserve newlines (do not dehyphenate).
- Strip trailing whitespace from every line.
- Strip leading/trailing blank lines from the result.
- Span text is NOT normalised (spans keep raw text for forensic purposes).
"""

from __future__ import annotations

import re
import unicodedata

# Characters to remove entirely (zero-width, etc.)
_REMOVE = re.compile(
    r"[\u200b\u200c\u200d\u200e\u200f\ufeff\u00ad]",
)

# Non-breaking space variants → regular space
_NBS = re.compile(r"[\u00a0\u202f\u2007\u2060]")

# Collapse runs of space/tab (but not newline) to single space
_SPACES = re.compile(r"[ \t]+")


def normalize_text(text: str) -> str:
    """Return *text* with Unicode NFC, invisible chars removed, spaces collapsed."""
    # 1. NFC
    text = unicodedata.normalize("NFC", text)
    # 2. Remove zero-width and soft-hyphen characters
    text = _REMOVE.sub("", text)
    # 3. Non-breaking spaces → regular space
    text = _NBS.sub(" ", text)
    # 4. Collapse intra-line whitespace
    lines = text.split("\n")
    lines = [_SPACES.sub(" ", line).rstrip() for line in lines]
    # 5. Strip leading/trailing blank lines
    result = "\n".join(lines).strip()
    return result
