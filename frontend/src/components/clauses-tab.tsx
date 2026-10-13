"use client";

import React, { useState, useMemo } from "react";
import { Search, Tag, FileText } from "lucide-react";
import type { ClauseResponse } from "@/lib/api";

interface ClausesTabProps {
  clauses: ClauseResponse[];
  onSelectPage: (page: number) => void;
}

export function ClausesTab({ clauses, onSelectPage }: ClausesTabProps) {
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedLabel, setSelectedLabel] = useState<string | null>(null);

  // Discover all unique labels present across document clauses
  const availableLabels = useMemo(() => {
    const set = new Set<string>();
    clauses.forEach((c) => {
      c.labels?.forEach((l) => {
        if (l.label) set.add(l.label);
      });
    });
    return Array.from(set).sort();
  }, [clauses]);

  // Filter clauses by search query and selected label
  const filteredClauses = useMemo(() => {
    const q = searchQuery.toLowerCase().trim();
    return clauses.filter((c) => {
      if (selectedLabel) {
        const hasLabel = c.labels?.some((l) => l.label === selectedLabel);
        if (!hasLabel) return false;
      }
      if (q) {
        const matchHeading = c.heading?.toLowerCase().includes(q);
        const matchText = c.text?.toLowerCase().includes(q);
        const matchNumber = c.clause_id?.toLowerCase().includes(q);
        if (!matchHeading && !matchText && !matchNumber) return false;
      }
      return true;
    });
  }, [clauses, searchQuery, selectedLabel]);

  return (
    <div className="flex h-full flex-col">
      {/* Search & Label Filter Bar */}
      <div className="border-b border-[var(--border-subtle)] bg-[var(--bg-card)] p-3 space-y-2.5 text-xs">
        {/* Search Input */}
        <div className="relative">
          <Search className="absolute left-2.5 top-2.5 h-3.5 w-3.5 text-[var(--text-muted)]" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search clauses or headings..."
            className="w-full rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-card-muted)] py-1.5 pl-8 pr-3 text-xs text-[var(--text-primary)] placeholder-[var(--text-muted)] focus:border-[var(--accent)] focus:outline-none"
          />
        </div>

        {/* Labels Filter Chips */}
        {availableLabels.length > 0 && (
          <div className="flex items-center gap-1.5 flex-wrap pt-0.5">
            <span className="text-[11px] font-semibold uppercase tracking-wider text-[var(--text-muted)] mr-1">
              Filter:
            </span>
            <button
              onClick={() => setSelectedLabel(null)}
              className={`rounded-full px-2 py-0.5 text-[11px] font-medium transition-colors ${
                selectedLabel === null
                  ? "bg-[var(--accent)] text-white"
                  : "bg-[var(--bg-card-muted)] text-[var(--text-secondary)] hover:bg-[var(--border-subtle)]"
              }`}
            >
              All ({clauses.length})
            </button>
            {availableLabels.map((label) => (
              <button
                key={label}
                onClick={() => setSelectedLabel(selectedLabel === label ? null : label)}
                className={`rounded-full px-2 py-0.5 text-[11px] font-medium transition-colors ${
                  selectedLabel === label
                    ? "bg-[var(--accent)] text-white"
                    : "bg-[var(--bg-card-muted)] text-[var(--text-secondary)] hover:bg-[var(--border-subtle)]"
                }`}
              >
                {label.replace(/_/g, " ")}
              </button>
            ))}
          </div>
        )}
      </div>

      {/* Clauses List */}
      <div className="flex-1 overflow-y-auto p-4 space-y-2.5" role="list">
        {filteredClauses.length === 0 && (
          <div className="rounded-xl border border-dashed border-[var(--border-subtle)] p-8 text-center text-xs text-[var(--text-muted)]">
            <FileText className="mx-auto h-8 w-8 opacity-40 mb-2" />
            <p className="font-medium text-[var(--text-secondary)]">No clauses found</p>
            <p className="mt-1">Try another search query or clear the label filter.</p>
          </div>
        )}

        {filteredClauses.map((c) => {
          const preview = (c.text || "").replace(/\s+/g, " ").slice(0, 140);
          const labelsToShow = (c.labels || []).slice(0, 3);
          const page = c.page_start || 1;

          return (
            <div
              key={c.clause_id || c.order_idx}
              role="listitem"
              tabIndex={0}
              onClick={() => onSelectPage(page)}
              onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ") {
                  e.preventDefault();
                  onSelectPage(page);
                }
              }}
              className="group cursor-pointer rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-card)] p-3 text-xs transition-colors hover:border-[var(--border-hover)] hover:bg-[var(--bg-card-muted)]/50 focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--accent)]"
            >
              <div className="flex items-start justify-between gap-2">
                <div className="flex items-center gap-2">
                  <span className="font-mono font-semibold text-[var(--accent)]">
                    {c.clause_id ? `§ ${c.clause_id}` : `¶ ${c.order_idx + 1}`}
                  </span>
                  <span className="font-semibold text-[var(--text-primary)]">
                    {c.heading || "Untitled Section"}
                  </span>
                </div>

                <span className="text-[10px] text-[var(--text-muted)] font-mono shrink-0">
                  Page {page}
                </span>
              </div>

              {/* Labels Chips */}
              {labelsToShow.length > 0 && (
                <div className="mt-1.5 flex items-center gap-1.5 flex-wrap">
                  {labelsToShow.map((l, i) => (
                    <span
                      key={i}
                      className="inline-flex items-center gap-1 rounded bg-[var(--bg-card-muted)] px-1.5 py-0.5 text-[10px] font-medium text-[var(--text-secondary)] border border-[var(--border-subtle)]"
                    >
                      <Tag className="h-2.5 w-2.5 text-[var(--text-muted)]" />
                      <span>{l.label.replace(/_/g, " ")}</span>
                    </span>
                  ))}
                </div>
              )}

              {/* One-line Preview */}
              <p className="mt-2 text-[11px] text-[var(--text-secondary)] line-clamp-1 leading-normal font-sans">
                {preview}...
              </p>
            </div>
          );
        })}
      </div>
    </div>
  );
}
