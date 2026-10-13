"use client";

import React, { useState, useEffect, useRef } from "react";
import { Document, Page, pdfjs } from "react-pdf";
import "react-pdf/dist/Page/AnnotationLayer.css";
import "react-pdf/dist/Page/TextLayer.css";
import { ZoomIn, ZoomOut, Maximize2, Loader2, AlertCircle } from "lucide-react";
import type { FindingHighlightItem } from "@/lib/api";
import { computeHighlightStyle } from "@/lib/pdf-coordinates";

// Configure pdf.js worker locally from /pdf.worker.min.mjs (Zero external CDN calls)
if (typeof window !== "undefined") {
  pdfjs.GlobalWorkerOptions.workerSrc = "/pdf.worker.min.mjs";
}

interface HighlightWithFindingId {
  highlight: FindingHighlightItem;
  findingId: string;
}

interface PdfViewerProps {
  fileUrl: string;
  highlights: HighlightWithFindingId[];
  selectedFindingId: string | null;
  onSelectFinding: (findingId: string) => void;
  targetPage?: number | null;
}

export function PdfViewer({
  fileUrl,
  highlights,
  selectedFindingId,
  onSelectFinding,
  targetPage,
}: PdfViewerProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const pageRefs = useRef<Map<number, HTMLDivElement>>(new Map());

  const [numPages, setNumPages] = useState<number | null>(null);
  const [containerWidth, setContainerWidth] = useState<number>(600);
  const [scale, setScale] = useState<number>(1.0);
  const [pdfLoadError, setPdfLoadError] = useState<string | null>(null);

  // Resize observer to auto-fit container width
  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;

    const updateWidth = () => {
      const w = el.clientWidth;
      if (w > 100) {
        setContainerWidth(w - 32); // padding offset
      }
    };

    updateWidth();
    const observer = new ResizeObserver(updateWidth);
    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  // Scroll to target page when card is clicked
  useEffect(() => {
    if (targetPage && targetPage > 0) {
      const pageEl = pageRefs.current.get(targetPage);
      if (pageEl) {
        pageEl.scrollIntoView({ behavior: "smooth", block: "start" });
      }
    }
  }, [targetPage]);

  const onDocumentLoadSuccess = ({ numPages }: { numPages: number }) => {
    setNumPages(numPages);
    setPdfLoadError(null);
  };

  const onDocumentLoadError = (err: Error) => {
    setPdfLoadError(err.message || "Failed to render PDF document.");
  };

  const handleZoomIn = () => setScale((s) => Math.min(2.5, s + 0.15));
  const handleZoomOut = () => setScale((s) => Math.max(0.6, s - 0.15));
  const handleFitWidth = () => setScale(1.0);

  const baseRenderWidth = Math.max(300, containerWidth * scale);

  return (
    <div className="flex h-full flex-col bg-[var(--bg-card-muted)] lg:border-r border-r-0 border-[var(--border-subtle)]">
      {/* Viewer Toolbar */}
      <div className="flex items-center justify-between border-b border-[var(--border-subtle)] bg-[var(--bg-card)] px-4 py-2 text-xs">
        <div className="flex items-center gap-2 text-[var(--text-secondary)]">
          <span className="font-medium">
            {numPages ? `${numPages} pages` : "Loading pages..."}
          </span>
          <span className="text-[var(--text-muted)]">•</span>
          <span className="tabular-nums font-mono text-[11px]">{Math.round(scale * 100)}%</span>
        </div>

        <div className="flex items-center gap-1.5">
          <button
            onClick={handleZoomOut}
            aria-label="Zoom out"
            className="rounded p-1 text-[var(--text-secondary)] hover:bg-[var(--bg-card-muted)] hover:text-[var(--text-primary)] transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--accent)]"
          >
            <ZoomOut className="h-4 w-4" />
          </button>
          <button
            onClick={handleZoomIn}
            aria-label="Zoom in"
            className="rounded p-1 text-[var(--text-secondary)] hover:bg-[var(--bg-card-muted)] hover:text-[var(--text-primary)] transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--accent)]"
          >
            <ZoomIn className="h-4 w-4" />
          </button>
          <button
            onClick={handleFitWidth}
            aria-label="Fit to width"
            className="rounded p-1 text-[var(--text-secondary)] hover:bg-[var(--bg-card-muted)] hover:text-[var(--text-primary)] transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--accent)]"
          >
            <Maximize2 className="h-4 w-4" />
          </button>
        </div>
      </div>

      {/* PDF Pages Container with Continuous Scroll */}
      <div
        ref={containerRef}
        className="flex-1 overflow-y-auto p-4 flex flex-col items-center gap-6"
        id="pdf-scroll-container"
      >
        {pdfLoadError && (
          <div
            role="alert"
            className="my-auto flex max-w-md items-center gap-3 rounded-xl border border-red-200 bg-red-50 p-4 text-xs text-red-800 dark:border-red-900 dark:bg-red-950 dark:text-red-300"
          >
            <AlertCircle className="h-5 w-5 shrink-0 text-red-600" />
            <div>
              <p className="font-semibold text-sm">Cannot display PDF</p>
              <p className="mt-1">{pdfLoadError}</p>
            </div>
          </div>
        )}

        <Document
          file={fileUrl}
          onLoadSuccess={onDocumentLoadSuccess}
          onLoadError={onDocumentLoadError}
          loading={
            <div className="my-12 flex flex-col items-center gap-2 text-xs text-[var(--text-muted)]">
              <Loader2 className="h-6 w-6 animate-spin text-[var(--accent)]" />
              <span>Rendering PDF pages...</span>
            </div>
          }
        >
          {numPages &&
            Array.from(new Array(numPages), (_, index) => {
              const pageNumber = index + 1;
              const pageHighlights = highlights.filter(
                (h) => (h.highlight.page || 1) === pageNumber
              );

              return (
                <div
                  key={`page_${pageNumber}`}
                  ref={(el) => {
                    if (el) pageRefs.current.set(pageNumber, el);
                    else pageRefs.current.delete(pageNumber);
                  }}
                  className="relative rounded-lg bg-white shadow-md ring-1 ring-zinc-950/5 dark:ring-white/10"
                  style={{ width: baseRenderWidth }}
                  data-page-number={pageNumber}
                >
                  <Page
                    pageNumber={pageNumber}
                    width={baseRenderWidth}
                    renderAnnotationLayer={false}
                    renderTextLayer={true}
                    loading={
                      <div
                        className="flex items-center justify-center bg-zinc-50 dark:bg-zinc-800"
                        style={{ height: baseRenderWidth * 1.3 }}
                      >
                        <Loader2 className="h-5 w-5 animate-spin text-zinc-400" />
                      </div>
                    }
                  />

                  {/* Highlight Overlays Layer */}
                  <div className="absolute inset-0 pointer-events-none overflow-hidden">
                    {pageHighlights.map((item, hIdx) => {
                      const { highlight, findingId } = item;
                      const isSelected = findingId === selectedFindingId;
                      const style = computeHighlightStyle({
                        bbox: highlight.bbox || [0, 0, 0, 0],
                        pageWidth: highlight.page_width || 595,
                        pageHeight: highlight.page_height || 842,
                        rotation: highlight.rotation || 0,
                        renderedWidth: baseRenderWidth,
                      });

                      return (
                        <div
                          key={`hl_${pageNumber}_${findingId}_${hIdx}`}
                          onClick={(e) => {
                            e.stopPropagation();
                            onSelectFinding(findingId);
                          }}
                          tabIndex={0}
                          role="button"
                          aria-label={`Highlight for finding ${findingId}`}
                          className={`pointer-events-auto absolute cursor-pointer rounded-xs transition-colors focus-visible:outline focus-visible:outline-2 ${
                            highlight.approximate
                              ? "border-2 border-dashed border-amber-500 bg-amber-400/20 hover:bg-amber-400/35"
                              : "border border-amber-500/80 bg-amber-300/30 hover:bg-amber-300/50"
                          } ${
                            isSelected
                              ? "highlight-selected z-20 border-indigo-600 bg-indigo-500/35 ring-2 ring-indigo-500/80"
                              : "z-10"
                          }`}
                          style={{
                            left: `${style.left}px`,
                            top: `${style.top}px`,
                            width: `${style.width}px`,
                            height: `${style.height}px`,
                          }}
                          data-testid="finding-highlight"
                          data-finding-id={findingId}
                          data-page={pageNumber}
                        />
                      );
                    })}
                  </div>

                  {/* Page Number Label in Footer */}
                  <div className="absolute -bottom-5 right-2 text-[10px] text-[var(--text-muted)] font-mono">
                    Page {pageNumber} of {numPages}
                  </div>
                </div>
              );
            })}
        </Document>
      </div>
    </div>
  );
}
