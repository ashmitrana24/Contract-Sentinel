/**
 * Pure coordinate transformation functions for PDF highlights.
 * Converts PyMuPDF bounding boxes [x0, y0, x1, y1] with top-left origin
 * into scaled CSS pixel coordinates (left, top, width, height) for viewer overlays,
 * accounting for page rotation (0, 90, 180, 270 degrees).
 */

export interface HighlightBoxInput {
  bbox: number[]; // [x0, y0, x1, y1]
  pageWidth: number;
  pageHeight: number;
  rotation?: number; // 0, 90, 180, 270
  renderedWidth: number;
}

export interface ScaledHighlightStyle {
  left: number;
  top: number;
  width: number;
  height: number;
  scale: number;
}

export function computeHighlightStyle(input: HighlightBoxInput): ScaledHighlightStyle {
  const { bbox, pageWidth, pageHeight, rotation = 0, renderedWidth } = input;
  if (!bbox || bbox.length < 4 || renderedWidth <= 0 || pageWidth <= 0 || pageHeight <= 0) {
    return { left: 0, top: 0, width: 0, height: 0, scale: 1 };
  }

  const [rawX0, rawY0, rawX1, rawY1] = bbox;
  // Ensure bounding box coordinates are min/max ordered
  const x0 = Math.min(rawX0, rawX1);
  const x1 = Math.max(rawX0, rawX1);
  const y0 = Math.min(rawY0, rawY1);
  const y1 = Math.max(rawY0, rawY1);

  const rot = ((rotation % 360) + 360) % 360;

  let transformedX0 = x0;
  let transformedY0 = y0;
  let transformedWidth = x1 - x0;
  let transformedHeight = y1 - y0;
  let baseDimensionForScale = pageWidth;

  if (rot === 90) {
    // 90 deg clockwise: display width corresponds to pageHeight
    baseDimensionForScale = pageHeight;
    transformedX0 = pageHeight - y1;
    transformedY0 = x0;
    transformedWidth = y1 - y0;
    transformedHeight = x1 - x0;
  } else if (rot === 180) {
    baseDimensionForScale = pageWidth;
    transformedX0 = pageWidth - x1;
    transformedY0 = pageHeight - y1;
    transformedWidth = x1 - x0;
    transformedHeight = y1 - y0;
  } else if (rot === 270) {
    baseDimensionForScale = pageHeight;
    transformedX0 = y0;
    transformedY0 = pageWidth - x1;
    transformedWidth = y1 - y0;
    transformedHeight = x1 - x0;
  }

  const scale = renderedWidth / baseDimensionForScale;

  return {
    left: Math.max(0, transformedX0 * scale),
    top: Math.max(0, transformedY0 * scale),
    width: Math.max(2, transformedWidth * scale),
    height: Math.max(2, transformedHeight * scale),
    scale,
  };
}
