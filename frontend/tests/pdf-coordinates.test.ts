import { describe, it, expect } from "vitest";
import { computeHighlightStyle } from "../src/lib/pdf-coordinates";

describe("computeHighlightStyle", () => {
  const pageWidth = 600;
  const pageHeight = 800;
  const renderedWidth = 1200; // scale factor = 2.0 for 0 and 180 deg

  it("scales standard 0-degree bounding box correctly", () => {
    const res = computeHighlightStyle({
      bbox: [50, 100, 250, 200],
      pageWidth,
      pageHeight,
      rotation: 0,
      renderedWidth,
    });

    expect(res.scale).toBe(2);
    expect(res.left).toBe(100);
    expect(res.top).toBe(200);
    expect(res.width).toBe(400);
    expect(res.height).toBe(200);
  });

  it("handles 90-degree clockwise rotated pages", () => {
    // When rotated 90 deg clockwise:
    // display width corresponds to pageHeight (800)
    // scale = renderedWidth (1200) / 800 = 1.5
    // transformedX0 = pageHeight - y1 = 800 - 200 = 600
    // transformedY0 = x0 = 50
    // transformedWidth = y1 - y0 = 100
    // transformedHeight = x1 - x0 = 200
    const res = computeHighlightStyle({
      bbox: [50, 100, 250, 200],
      pageWidth,
      pageHeight,
      rotation: 90,
      renderedWidth,
    });

    expect(res.scale).toBe(1.5);
    expect(res.left).toBe(600 * 1.5);
    expect(res.top).toBe(50 * 1.5);
    expect(res.width).toBe(100 * 1.5);
    expect(res.height).toBe(200 * 1.5);
  });

  it("handles 180-degree rotated pages", () => {
    // scale = 1200 / 600 = 2.0
    // transformedX0 = pageWidth - x1 = 600 - 250 = 350
    // transformedY0 = pageHeight - y1 = 800 - 200 = 600
    const res = computeHighlightStyle({
      bbox: [50, 100, 250, 200],
      pageWidth,
      pageHeight,
      rotation: 180,
      renderedWidth,
    });

    expect(res.scale).toBe(2);
    expect(res.left).toBe(350 * 2);
    expect(res.top).toBe(600 * 2);
    expect(res.width).toBe(400);
    expect(res.height).toBe(200);
  });

  it("handles 270-degree rotated pages", () => {
    // display width corresponds to pageHeight (800)
    // scale = 1200 / 800 = 1.5
    // transformedX0 = y0 = 100
    // transformedY0 = pageWidth - x1 = 600 - 250 = 350
    const res = computeHighlightStyle({
      bbox: [50, 100, 250, 200],
      pageWidth,
      pageHeight,
      rotation: 270,
      renderedWidth,
    });

    expect(res.scale).toBe(1.5);
    expect(res.left).toBe(100 * 1.5);
    expect(res.top).toBe(350 * 1.5);
    expect(res.width).toBe(100 * 1.5);
    expect(res.height).toBe(200 * 1.5);
  });

  it("handles inverted bounding box coordinates gracefully", () => {
    const res = computeHighlightStyle({
      bbox: [250, 200, 50, 100], // inverted
      pageWidth,
      pageHeight,
      rotation: 0,
      renderedWidth,
    });

    expect(res.left).toBe(100);
    expect(res.top).toBe(200);
    expect(res.width).toBe(400);
    expect(res.height).toBe(200);
  });

  it("returns zero dimensions for invalid or missing inputs", () => {
    const res = computeHighlightStyle({
      bbox: [],
      pageWidth: 0,
      pageHeight: 0,
      renderedWidth: 0,
    });

    expect(res.width).toBe(0);
    expect(res.height).toBe(0);
  });
});
