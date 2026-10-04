"""Text hiding detector.

Detects text that is invisible or barely visible in a PDF using PyMuPDF's
get_texttrace() API and get_drawings() for background analysis.

Flags:
- hidden_text: fill color contrast ratio vs effective background < threshold
- tiny_text: font size < threshold (default 2 pt)
- offpage_text: bbox outside the page rectangle
- occluded_text: text covered by an opaque filled rectangle drawn AFTER it

Does NOT flag:
- Invisible text (render mode 3) overlaid on images (OCR layer pattern)
- Text on genuinely dark backgrounds (white text on dark bg is legitimate)
- Small footnotes >= 6 pt
- render-mode-3 text when page has significant image coverage
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import pymupdf

from clauseguard.forensics.models import (
    FORENSICS_MODULE,
    MAX_FINDINGS_PER_TYPE,
    ForensicsSettings,
)
from clauseguard.schemas.findings import Finding, Severity

logger = logging.getLogger(__name__)

_EVIDENCE_CAP = 300
_TEXT_RENDER_INVISIBLE = 3  # PDF render mode 3 = invisible (used for OCR)

# Legal / financial keywords that escalate hidden text to HIGH
_HIGH_SEVERITY_RE = __import__("re").compile(
    r"\b(indemnif|warrant|liabilit|terminat|confidential|arbitrat|jurisdict|governing|"
    r"intellectual|property|assign|license|royalt|penalty|damages|waiv|forfeit|"
    r"payment|amount|rupees|clause|agreement|obligation|exclusive)\b",
    __import__("re").IGNORECASE,
)
_DIGIT_RE = __import__("re").compile(r"\d")
_CURRENCY_RE = __import__("re").compile(r"(Rs\.?|INR|\$|€|£)")


@dataclass
class _Span:
    """One text span from get_texttrace()."""

    text: str
    color: tuple[float, ...]
    size: float
    render_type: int  # 'type' field in texttrace
    bbox: tuple[float, float, float, float]
    seqno: int
    opacity: float


@dataclass
class _Drawing:
    """One drawing from get_drawings()."""

    fill: tuple[float, ...] | None
    fill_opacity: float
    rect: tuple[float, float, float, float]
    seqno: int


def _relative_luminance(r: float, g: float, b: float) -> float:
    """Compute WCAG 2.0 relative luminance from linear RGB [0,1]."""

    def _lin(c: float) -> float:
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4

    return 0.2126 * _lin(r) + 0.7152 * _lin(g) + 0.0722 * _lin(b)


def _wcag_contrast(
    fg: tuple[float, float, float],
    bg: tuple[float, float, float],
) -> float:
    """Return the WCAG contrast ratio between two RGB colors."""
    l1 = _relative_luminance(*fg) + 0.05
    l2 = _relative_luminance(*bg) + 0.05
    if l1 >= l2:
        return l1 / l2
    return l2 / l1


def _color_to_rgb(color: tuple[float, ...]) -> tuple[float, float, float]:
    """Convert a PDF color (gray, RGB, or CMYK) to RGB [0,1]."""
    if len(color) == 1:
        # Grayscale
        g = color[0]
        return (g, g, g)
    if len(color) == 3:
        return (color[0], color[1], color[2])
    if len(color) == 4:
        # CMYK
        c, m, y, k = color
        r = 1.0 - min(1.0, c + k)
        g = 1.0 - min(1.0, m + k)
        b = 1.0 - min(1.0, y + k)
        return (r, g, b)
    # Unknown: default to black
    return (0.0, 0.0, 0.0)


def _rect_overlaps(a: tuple[float, float, float, float], b: tuple[float, float, float, float]) -> bool:
    """Return True if two bounding boxes overlap."""
    ax0, ay0, ax1, ay1 = a
    bx0, by0, bx1, by1 = b
    return ax0 < bx1 and ax1 > bx0 and ay0 < by1 and ay1 > by0


def _is_inside_page(
    bbox: tuple[float, float, float, float],
    page_rect: tuple[float, float, float, float],
) -> bool:
    """Return True if bbox is inside (or touching) the page rectangle."""
    px0, py0, px1, py1 = page_rect
    bx0, by0, bx1, by1 = bbox
    return bx0 >= px0 - 2 and by0 >= py0 - 2 and bx1 <= px1 + 2 and by1 <= py1 + 2


def _page_has_image_coverage(page: pymupdf.Page) -> bool:
    """Return True if page has significant image content (OCR-like pattern)."""
    try:
        images = page.get_images()
        if not images:
            return False
        # If there's at least one image that's reasonably large relative to page
        page_area = page.rect.width * page.rect.height
        if page_area <= 0:
            return False
        for img in images:
            # img is (xref, smask, width, height, bpc, colorspace, alt_colorspace, name, filter, referencer)
            if len(img) >= 4:
                w, h = img[2], img[3]
                img_area = w * h
                if img_area > page_area * 0.1:
                    return True
    except Exception:
        pass
    return False


def _extract_spans(page: pymupdf.Page) -> list[_Span]:
    """Extract text spans from page using get_texttrace()."""
    spans: list[_Span] = []
    try:
        trace = page.get_texttrace()
    except Exception as exc:
        logger.warning("get_texttrace failed on page %s: %s", page.number + 1, exc)
        return spans

    for entry in trace:
        chars = entry.get("chars", ())
        if not chars:
            continue

        # Assemble text from chars: each char is (glyph, unicode, origin, bbox)
        text_parts: list[str] = []
        for char in chars:
            if len(char) >= 2:
                ucode = char[1]
                if ucode > 0:
                    try:
                        text_parts.append(chr(ucode))
                    except (ValueError, OverflowError):
                        pass

        text = "".join(text_parts).strip()
        if not text:
            continue

        color_raw = entry.get("color", (0.0,))
        if not isinstance(color_raw, (tuple, list)):
            color_raw = (float(color_raw),)
        color = tuple(float(c) for c in color_raw)

        size = float(entry.get("size", 0.0))
        render_type = int(entry.get("type", 0))
        bbox_raw = entry.get("bbox", (0, 0, 0, 0))
        bbox = (
            float(bbox_raw[0]),
            float(bbox_raw[1]),
            float(bbox_raw[2]),
            float(bbox_raw[3]),
        )
        seqno = int(entry.get("seqno", 0))
        opacity = float(entry.get("opacity", 1.0))

        spans.append(
            _Span(
                text=text,
                color=color,
                size=size,
                render_type=render_type,
                bbox=bbox,
                seqno=seqno,
                opacity=opacity,
            )
        )

    return spans


def _extract_drawings(page: pymupdf.Page) -> list[_Drawing]:
    """Extract filled rectangle drawings from a page."""
    drawings: list[_Drawing] = []
    try:
        raw_drawings = page.get_drawings()
    except Exception as exc:
        logger.warning("get_drawings failed on page %s: %s", page.number + 1, exc)
        return drawings

    for d in raw_drawings:
        fill = d.get("fill")
        if fill is None:
            continue
        fill_opacity = float(d.get("fill_opacity", 1.0))
        if fill_opacity < 0.9:
            # Semi-transparent: not a solid cover
            continue
        rect_raw = d.get("rect")
        if rect_raw is None:
            continue
        try:
            rect = (
                float(rect_raw[0]),
                float(rect_raw[1]),
                float(rect_raw[2]),
                float(rect_raw[3]),
            )
        except Exception:
            continue
        seqno = int(d.get("seqno", 0))
        fill_tuple = tuple(float(c) for c in fill)
        drawings.append(
            _Drawing(fill=fill_tuple, fill_opacity=fill_opacity, rect=rect, seqno=seqno)
        )

    return drawings


def _find_effective_bg(
    span: _Span,
    drawings: list[_Drawing],
    default_bg: tuple[float, float, float] = (1.0, 1.0, 1.0),
) -> tuple[float, float, float]:
    """Return the effective background color under a text span.

    Finds the filled drawing with the highest seqno that:
    1. Overlaps the span bbox
    2. Has seqno < span seqno (drawn BEFORE the text)

    Falls back to default_bg (white) if none found.
    """
    best_seqno = -1
    best_color = default_bg

    for drawing in drawings:
        if drawing.seqno >= span.seqno:
            continue
        if not _rect_overlaps(span.bbox, drawing.rect):
            continue
        if drawing.fill is None:
            continue
        if drawing.seqno > best_seqno:
            best_seqno = drawing.seqno
            best_color = _color_to_rgb(drawing.fill)

    return best_color


def _is_occluded(
    span: _Span,
    drawings: list[_Drawing],
) -> tuple[bool, tuple[float, float, float] | None]:
    """Return (True, rect_color) if a white-out rectangle covers the span.

    A span is occluded if there is a filled drawing with seqno > span.seqno
    that overlaps the span bbox (drawn AFTER the text).
    """
    for drawing in drawings:
        if drawing.seqno <= span.seqno:
            continue
        if not _rect_overlaps(span.bbox, drawing.rect):
            continue
        if drawing.fill is None:
            continue
        color_rgb = _color_to_rgb(drawing.fill)
        # White-out pattern: an opaque white or near-white rectangle drawn over text
        if drawing.fill_opacity >= 0.9 and all(c >= 0.9 for c in color_rgb):
            return True, color_rgb
    return False, None


def _severity_for_text(text: str) -> Severity:
    """Determine severity for a hidden text span."""
    if (
        len(text) >= 20
        or _DIGIT_RE.search(text)
        or _CURRENCY_RE.search(text)
        or _HIGH_SEVERITY_RE.search(text)
    ):
        return Severity.HIGH
    return Severity.MEDIUM


def _make_finding(
    finding_type: str,
    text: str,
    page_no: int,
    bbox: tuple[float, float, float, float],
    evidence: str,
    explanation: str,
    details: dict[str, Any],
) -> Finding:
    sev = _severity_for_text(text)
    return Finding(
        module=FORENSICS_MODULE,
        type=finding_type,
        severity=sev,
        page=page_no,
        bbox=bbox,
        evidence=evidence[:_EVIDENCE_CAP],
        explanation=explanation,
        details=details,
    )


def detect_text_hiding(
    pdf_bytes: bytes,
    settings: ForensicsSettings,
) -> list[Finding]:
    """Detect hidden, tiny, off-page, and occluded text in ``pdf_bytes``."""
    findings: list[Finding] = []
    type_counts: dict[str, int] = {}

    try:
        doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    except Exception as exc:
        return [
            Finding(
                module=FORENSICS_MODULE,
                type="hidden_text",
                severity=Severity.LOW,
                evidence=str(exc)[:_EVIDENCE_CAP],
                explanation=f"Could not open PDF for text hiding analysis: {exc!s}",
                details={"error": str(exc)},
            )
        ]

    try:
        for page_idx in range(doc.page_count):
            page = doc[page_idx]
            page_no = page_idx + 1
            page_rect = (
                float(page.rect.x0),
                float(page.rect.y0),
                float(page.rect.x1),
                float(page.rect.y1),
            )

            has_images = _page_has_image_coverage(page)
            spans = _extract_spans(page)
            drawings = _extract_drawings(page)

            for span in spans:
                # ---- 1. Invisible render mode (type == 3) ----
                if span.render_type == _TEXT_RENDER_INVISIBLE:
                    # If the page has images, this is very likely an OCR layer -> skip
                    if has_images:
                        continue
                    finding_type = "hidden_text"
                    tc = type_counts.get(finding_type, 0)
                    if tc >= MAX_FINDINGS_PER_TYPE:
                        continue
                    type_counts[finding_type] = tc + 1
                    snippet = span.text[:100]
                    findings.append(
                        _make_finding(
                            finding_type=finding_type,
                            text=span.text,
                            page_no=page_no,
                            bbox=span.bbox,
                            evidence=f"Invisible render mode (type=3) on page {page_no}: '{snippet}'",
                            explanation=(
                                f"Text on page {page_no} has PDF render mode 3 (invisible). "
                                "This text does not appear visually but is present in the document. "
                                "Invisible text is sometimes used to hide information."
                            ),
                            details={
                                "render_type": span.render_type,
                                "text_preview": snippet,
                                "font_size": span.size,
                            },
                        )
                    )
                    continue

                # ---- 2. Tiny font size ----
                # Note: 6pt and above is NOT flagged (footnotes); 2pt threshold
                if 0 < span.size < settings.min_font_size_pt:
                    finding_type = "hidden_text"
                    tc = type_counts.get(finding_type, 0)
                    if tc >= MAX_FINDINGS_PER_TYPE:
                        continue
                    type_counts[finding_type] = tc + 1
                    snippet = span.text[:100]
                    findings.append(
                        _make_finding(
                            finding_type=finding_type,
                            text=span.text,
                            page_no=page_no,
                            bbox=span.bbox,
                            evidence=(
                                f"Font size {span.size:.2f}pt (threshold: {settings.min_font_size_pt}pt) "
                                f"on page {page_no}: '{snippet}'"
                            ),
                            explanation=(
                                f"Text on page {page_no} has a font size of {span.size:.2f}pt, "
                                f"which is below the {settings.min_font_size_pt}pt threshold. "
                                "Such tiny text is not readable and may be used to hide content."
                            ),
                            details={
                                "subtype": "tiny_text",
                                "font_size": span.size,
                                "threshold_pt": settings.min_font_size_pt,
                                "text_preview": snippet,
                            },
                        )
                    )
                    continue

                # ---- 3. Off-page text ----
                if not _is_inside_page(span.bbox, page_rect):
                    finding_type = "hidden_text"
                    tc = type_counts.get(finding_type, 0)
                    if tc >= MAX_FINDINGS_PER_TYPE:
                        continue
                    type_counts[finding_type] = tc + 1
                    snippet = span.text[:100]
                    findings.append(
                        _make_finding(
                            finding_type=finding_type,
                            text=span.text,
                            page_no=page_no,
                            bbox=span.bbox,
                            evidence=(
                                f"Text bbox {span.bbox} is outside page rect {page_rect} "
                                f"on page {page_no}: '{snippet}'"
                            ),
                            explanation=(
                                f"Text on page {page_no} is positioned outside the page boundaries "
                                f"(page rect: {page_rect[0]:.0f},{page_rect[1]:.0f},{page_rect[2]:.0f},{page_rect[3]:.0f}). "
                                "Off-page text is not visible when the document is rendered or printed."
                            ),
                            details={
                                "subtype": "offpage_text",
                                "bbox": list(span.bbox),
                                "page_rect": list(page_rect),
                                "text_preview": snippet,
                            },
                        )
                    )
                    continue

                # ---- 4. Occluded by a white-out rectangle drawn AFTER ----
                is_occl, rect_color = _is_occluded(span, drawings)
                if is_occl:
                    finding_type = "hidden_text"
                    tc = type_counts.get(finding_type, 0)
                    if tc >= MAX_FINDINGS_PER_TYPE:
                        continue
                    type_counts[finding_type] = tc + 1
                    snippet = span.text[:100]
                    color_str = f"rgb({rect_color[0]:.2f},{rect_color[1]:.2f},{rect_color[2]:.2f})" if rect_color else "unknown"
                    findings.append(
                        _make_finding(
                            finding_type=finding_type,
                            text=span.text,
                            page_no=page_no,
                            bbox=span.bbox,
                            evidence=(
                                f"Text covered by opaque rectangle (color: {color_str}) "
                                f"on page {page_no}: '{snippet}'"
                            ),
                            explanation=(
                                f"Text on page {page_no} is covered by an opaque filled rectangle "
                                f"(white-out pattern). The text '{snippet}' exists in the PDF "
                                "content streams but is hidden under the rectangle."
                            ),
                            details={
                                "subtype": "occluded_text",
                                "cover_color": list(rect_color) if rect_color else None,
                                "text_preview": snippet,
                            },
                        )
                    )
                    continue

                # ---- 5. Low contrast (hidden text via color) ----
                # Skip if render mode is 0 but color has zero opacity
                if span.opacity < 0.01:
                    finding_type = "hidden_text"
                    tc = type_counts.get(finding_type, 0)
                    if tc >= MAX_FINDINGS_PER_TYPE:
                        continue
                    type_counts[finding_type] = tc + 1
                    snippet = span.text[:100]
                    findings.append(
                        _make_finding(
                            finding_type=finding_type,
                            text=span.text,
                            page_no=page_no,
                            bbox=span.bbox,
                            evidence=f"Opacity {span.opacity:.3f} (nearly transparent) on page {page_no}: '{snippet}'",
                            explanation=(
                                f"Text on page {page_no} has near-zero opacity ({span.opacity:.3f}), "
                                "making it effectively invisible."
                            ),
                            details={"opacity": span.opacity, "text_preview": snippet},
                        )
                    )
                    continue

                # Compute effective background color
                bg_rgb = _find_effective_bg(span, drawings)
                fg_rgb = _color_to_rgb(span.color)
                contrast = _wcag_contrast(fg_rgb, bg_rgb)

                # Check if background is genuinely dark
                bg_luminance = _relative_luminance(*bg_rgb)
                is_dark_bg = bg_luminance < 0.18  # dark background (roughly < #444)

                # Only flag if background is NOT dark (white text on dark bg is legitimate)
                if not is_dark_bg and contrast < settings.min_contrast_ratio:
                    finding_type = "hidden_text"
                    tc = type_counts.get(finding_type, 0)
                    if tc >= MAX_FINDINGS_PER_TYPE:
                        continue
                    type_counts[finding_type] = tc + 1
                    snippet = span.text[:100]
                    fg_str = f"rgb({fg_rgb[0]:.2f},{fg_rgb[1]:.2f},{fg_rgb[2]:.2f})"
                    bg_str = f"rgb({bg_rgb[0]:.2f},{bg_rgb[1]:.2f},{bg_rgb[2]:.2f})"
                    findings.append(
                        _make_finding(
                            finding_type=finding_type,
                            text=span.text,
                            page_no=page_no,
                            bbox=span.bbox,
                            evidence=(
                                f"Low contrast {contrast:.2f} (fg: {fg_str}, bg: {bg_str}) "
                                f"on page {page_no}: '{snippet}'"
                            ),
                            explanation=(
                                f"Text on page {page_no} has a very low contrast ratio of {contrast:.2f} "
                                f"(text color: {fg_str}, background: {bg_str}). "
                                f"The WCAG threshold is {settings.min_contrast_ratio}. "
                                "This text is effectively invisible to a reader."
                            ),
                            details={
                                "contrast_ratio": contrast,
                                "fg_color": list(fg_rgb),
                                "bg_color": list(bg_rgb),
                                "threshold": settings.min_contrast_ratio,
                                "text_preview": snippet,
                            },
                        )
                    )

        # Add cap exceeded summary for any type that hit the cap
        for finding_type, count in type_counts.items():
            if count >= MAX_FINDINGS_PER_TYPE:
                findings.append(
                    Finding(
                        module=FORENSICS_MODULE,
                        type=finding_type,
                        severity=Severity.LOW,
                        evidence=f"Cap of {MAX_FINDINGS_PER_TYPE} reached for {finding_type}; document has {count}+ instances",
                        explanation=(
                            f"More than {MAX_FINDINGS_PER_TYPE} '{finding_type}' issues were found. "
                            "Only the first instances are shown."
                        ),
                        details={"cap": MAX_FINDINGS_PER_TYPE, "type": finding_type},
                    )
                )

    finally:
        doc.close()

    return findings
