"use client";

import React, { useState, useMemo, useEffect } from "react";
import { Check, X, HelpCircle, FileSearch, ChevronDown } from "lucide-react";
import * as Accordion from "@radix-ui/react-accordion";
import type { FindingResponse } from "@/lib/api";
import { SeverityPill } from "./severity-pill";

interface FindingsTabProps {
  findings: FindingResponse[];
  selectedFindingId: string | null;
  onSelectFinding: (findingId: string, page?: number | null) => void;
  onFeedbackChange: (findingId: string, verdict: "confirmed" | "dismissed" | null) => void;
}

const SEVERITY_RANK: Record<string, number> = {
  critical: 4,
  high: 3,
  medium: 2,
  low: 1,
};

export function FindingsTab({
  findings,
  selectedFindingId,
  onSelectFinding,
  onFeedbackChange,
}: FindingsTabProps) {
  const [categoryFilter, setCategoryFilter] = useState<"all" | "tampering" | "inconsistency">("all");
  const [selectedSeverities, setSelectedSeverities] = useState<string[]>([
    "critical",
    "high",
    "medium",
    "low",
  ]);
  const [hideDismissed, setHideDismissed] = useState(false);

  // Split into scored vs minor notes (low or uncertain)
  const { scoredFindings, minorNotes } = useMemo(() => {
    const scored: FindingResponse[] = [];
    const minor: FindingResponse[] = [];

    findings.forEach((f) => {
      const sev = (f.severity || "low").toLowerCase();
      if (sev === "low" || f.uncertain) {
        minor.push(f);
      } else {
        scored.push(f);
      }
    });

    return { scoredFindings: scored, minorNotes: minor };
  }, [findings]);

  // Filter scored findings
  const filteredFindings = useMemo(() => {
    return scoredFindings
      .filter((f) => {
        if (categoryFilter !== "all" && f.category !== categoryFilter) return false;
        const sev = (f.severity || "low").toLowerCase();
        if (!selectedSeverities.includes(sev)) return false;
        if (hideDismissed && f.feedback?.verdict === "dismissed") return false;
        return true;
      })
      .sort((a, b) => {
        const sevA = SEVERITY_RANK[a.severity?.toLowerCase() || "low"] || 0;
        const sevB = SEVERITY_RANK[b.severity?.toLowerCase() || "low"] || 0;
        if (sevB !== sevA) return sevB - sevA; // severity descending
        return (a.page || 0) - (b.page || 0); // then page ascending
      });
  }, [scoredFindings, categoryFilter, selectedSeverities, hideDismissed]);

  // Keyboard navigation: up and down arrows between findings
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Don't capture when typing in an input
      if (
        document.activeElement?.tagName === "INPUT" ||
        document.activeElement?.tagName === "TEXTAREA"
      ) {
        return;
      }

      if (e.key === "ArrowDown" || e.key === "ArrowUp") {
        e.preventDefault();
        const currentIndex = filteredFindings.findIndex((f) => f.id === selectedFindingId);
        if (e.key === "ArrowDown") {
          const nextIndex =
            currentIndex < filteredFindings.length - 1 ? currentIndex + 1 : 0;
          const next = filteredFindings[nextIndex];
          if (next) onSelectFinding(next.id, next.page);
        } else if (e.key === "ArrowUp") {
          const prevIndex =
            currentIndex > 0 ? currentIndex - 1 : filteredFindings.length - 1;
          const prev = filteredFindings[prevIndex];
          if (prev) onSelectFinding(prev.id, prev.page);
        }
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [filteredFindings, selectedFindingId, onSelectFinding]);

  const toggleSeverity = (sev: string) => {
    setSelectedSeverities((prev) =>
      prev.includes(sev) ? prev.filter((s) => s !== sev) : [...prev, sev]
    );
  };

  const handleFeedback = (
    e: React.MouseEvent,
    f: FindingResponse,
    verdict: "confirmed" | "dismissed"
  ) => {
    e.stopPropagation();
    const current = f.feedback?.verdict;
    const nextVerdict = current === verdict ? null : verdict;
    onFeedbackChange(f.id, nextVerdict);
  };

  return (
    <div className="flex h-full flex-col">
      {/* Filter Chips Bar */}
      <div className="border-b border-[var(--border-subtle)] bg-[var(--bg-card)] p-3 space-y-2.5 text-xs">
        {/* Category Filter */}
        <div className="flex items-center gap-1.5 flex-wrap">
          <span className="text-[11px] font-semibold uppercase tracking-wider text-[var(--text-muted)] mr-1">
            Category:
          </span>
          {(["all", "tampering", "inconsistency"] as const).map((cat) => (
            <button
              key={cat}
              onClick={() => setCategoryFilter(cat)}
              className={`rounded-full px-2.5 py-1 text-xs font-medium transition-colors capitalize focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--accent)] ${
                categoryFilter === cat
                  ? "bg-[var(--accent)] text-white"
                  : "bg-[var(--bg-card-muted)] text-[var(--text-secondary)] hover:bg-[var(--border-subtle)]"
              }`}
            >
              {cat === "all" ? "All issues" : cat}
            </button>
          ))}
        </div>

        {/* Severity Toggles & Dismissed Filter */}
        <div className="flex items-center justify-between flex-wrap gap-2 pt-1">
          <div className="flex items-center gap-1.5 flex-wrap">
            <span className="text-[11px] font-semibold uppercase tracking-wider text-[var(--text-muted)] mr-1">
              Severity:
            </span>
            {["critical", "high", "medium", "low"].map((sev) => {
              const active = selectedSeverities.includes(sev);
              return (
                <button
                  key={sev}
                  onClick={() => toggleSeverity(sev)}
                  className={`rounded-md px-2 py-0.5 text-[11px] font-medium border transition-colors capitalize focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--accent)] ${
                    active
                      ? "border-[var(--border-hover)] bg-[var(--bg-card)] text-[var(--text-primary)] font-semibold"
                      : "border-transparent bg-transparent text-[var(--text-muted)] opacity-60"
                  }`}
                >
                  {sev}
                </button>
              );
            })}
          </div>

          <label className="flex items-center gap-1.5 cursor-pointer text-[11px] text-[var(--text-secondary)] select-none">
            <input
              type="checkbox"
              checked={hideDismissed}
              onChange={(e) => setHideDismissed(e.target.checked)}
              className="rounded border-[var(--border-subtle)] text-[var(--accent)] focus:ring-[var(--accent)]"
            />
            <span>Hide dismissed</span>
          </label>
        </div>
      </div>

      {/* Findings List */}
      <div className="flex-1 overflow-y-auto p-4 space-y-3" role="list">
        {filteredFindings.length === 0 && (
          <div className="rounded-xl border border-dashed border-[var(--border-subtle)] p-8 text-center text-xs text-[var(--text-muted)]">
            <FileSearch className="mx-auto h-8 w-8 opacity-40 mb-2" />
            <p className="font-medium text-[var(--text-secondary)]">No issues match the current filter</p>
            <p className="mt-1">Adjust severity or category filters to view other findings.</p>
          </div>
        )}

        {filteredFindings.map((f) => {
          const isSelected = f.id === selectedFindingId;
          const verdict = f.feedback?.verdict;

          return (
            <div
              key={f.id}
              role="listitem"
              tabIndex={0}
              onClick={() => onSelectFinding(f.id, f.page)}
              onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ") {
                  e.preventDefault();
                  onSelectFinding(f.id, f.page);
                }
              }}
              className={`group relative rounded-xl border p-4 transition-all cursor-pointer focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--accent)] ${
                isSelected
                  ? "border-[var(--accent)] bg-[var(--bg-card)] shadow-md ring-1 ring-[var(--accent)]/50"
                  : "border-[var(--border-subtle)] bg-[var(--bg-card)] hover:border-[var(--border-hover)] hover:bg-[var(--bg-card-muted)]/50"
              } ${verdict === "dismissed" ? "opacity-60" : ""}`}
              data-testid="finding-card"
              data-finding-id={f.id}
            >
              {/* Card Header: Severity, Title, Page/Clause Tag */}
              <div className="flex items-start justify-between gap-3">
                <div className="flex items-center gap-2 flex-wrap">
                  <SeverityPill severity={f.severity} size="sm" />
                  <span className="text-xs font-semibold text-[var(--text-primary)]">
                    {f.title || f.type}
                  </span>
                </div>

                <div className="flex items-center gap-1.5 shrink-0">
                  {f.clause_ref && (
                    <span className="rounded bg-[var(--bg-card-muted)] px-1.5 py-0.5 text-[11px] font-mono text-[var(--text-muted)] border border-[var(--border-subtle)]">
                      Clause {f.clause_ref}
                    </span>
                  )}
                  {f.page && (
                    <span className="rounded bg-[var(--bg-card-muted)] px-1.5 py-0.5 text-[11px] font-mono text-[var(--text-muted)] border border-[var(--border-subtle)]">
                      Page {f.page}
                    </span>
                  )}
                </div>
              </div>

              {/* Plain English Explanation */}
              <p className="mt-2 text-xs text-[var(--text-secondary)] leading-relaxed">
                {f.what_it_means || f.explanation}
              </p>

              {/* Evidence Code Block */}
              {f.evidence && (
                <div className="mt-2.5 rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-app)] p-2.5 text-[12.5px] font-mono text-[var(--text-primary)] break-all leading-normal">
                  <span className="select-none text-[10px] uppercase tracking-wider text-[var(--text-muted)] block mb-1">
                    Evidence:
                  </span>
                  <code>{f.evidence}</code>
                </div>
              )}

              {/* What To Check Line */}
              {f.what_to_check && (
                <div className="mt-2 text-[11px] text-amber-700 dark:text-amber-300 bg-amber-50 dark:bg-amber-950/40 border border-amber-200 dark:border-amber-800/60 rounded px-2.5 py-1">
                  <strong>What to check:</strong> {f.what_to_check}
                </div>
              )}

              {/* Uncertain Tag with Tooltip */}
              {f.uncertain && (
                <div className="mt-2 inline-flex items-center gap-1 text-[11px] text-purple-700 dark:text-purple-300">
                  <HelpCircle className="h-3 w-3" />
                  <span>Uncertain / Heuristic signal</span>
                </div>
              )}

              {/* Reviewer Action Buttons (Feedback) */}
              <div className="mt-3.5 flex items-center justify-between border-t border-[var(--border-subtle)] pt-2.5 text-xs">
                <span className="text-[11px] text-[var(--text-muted)]">
                  {verdict === "confirmed" && "Status: Issue confirmed"}
                  {verdict === "dismissed" && "Status: Dismissed (not an issue)"}
                  {!verdict && "Unreviewed"}
                </span>

                <div className="flex items-center gap-1.5">
                  <button
                    type="button"
                    onClick={(e) => handleFeedback(e, f, "confirmed")}
                    className={`inline-flex items-center gap-1 rounded-md px-2 py-1 text-xs font-medium transition-colors border ${
                      verdict === "confirmed"
                        ? "border-emerald-600 bg-emerald-600 text-white"
                        : "border-[var(--border-subtle)] bg-[var(--bg-card)] text-[var(--text-secondary)] hover:bg-emerald-50 hover:text-emerald-700 dark:hover:bg-emerald-950/50"
                    }`}
                  >
                    <Check className="h-3 w-3" />
                    <span>Confirm issue</span>
                  </button>

                  <button
                    type="button"
                    onClick={(e) => handleFeedback(e, f, "dismissed")}
                    className={`inline-flex items-center gap-1 rounded-md px-2 py-1 text-xs font-medium transition-colors border ${
                      verdict === "dismissed"
                        ? "border-zinc-600 bg-zinc-600 text-white dark:bg-zinc-700"
                        : "border-[var(--border-subtle)] bg-[var(--bg-card)] text-[var(--text-secondary)] hover:bg-zinc-100 hover:text-zinc-900 dark:hover:bg-zinc-800"
                    }`}
                  >
                    <X className="h-3 w-3" />
                    <span>Not an issue</span>
                  </button>
                </div>
              </div>
            </div>
          );
        })}

        {/* Minor Notes Accordion */}
        {minorNotes.length > 0 && (
          <Accordion.Root type="single" collapsible className="mt-4">
            <Accordion.Item
              value="minor-notes"
              className="rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-card-muted)]"
            >
              <Accordion.Trigger className="flex w-full items-center justify-between p-3.5 text-xs font-semibold text-[var(--text-secondary)] hover:text-[var(--text-primary)]">
                <span>Minor notes & low-confidence items ({minorNotes.length})</span>
                <ChevronDown className="h-4 w-4 transition-transform duration-200" />
              </Accordion.Trigger>
              <Accordion.Content className="p-3.5 pt-0 space-y-2 border-t border-[var(--border-subtle)]">
                <p className="text-[11px] text-[var(--text-muted)] mb-2">
                  These items are low severity or heuristic notes. They do not impact the risk score.
                </p>
                {minorNotes.map((note) => (
                  <div
                    key={note.id}
                    onClick={() => onSelectFinding(note.id, note.page)}
                    className="cursor-pointer rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-card)] p-2.5 text-xs hover:border-[var(--accent)]"
                  >
                    <div className="flex items-center justify-between">
                      <span className="font-medium text-[var(--text-primary)]">{note.title}</span>
                      <span className="text-[10px] text-[var(--text-muted)] font-mono">
                        Page {note.page || 1}
                      </span>
                    </div>
                    <p className="mt-1 text-[11px] text-[var(--text-secondary)] leading-relaxed">
                      {note.what_it_means || note.explanation}
                    </p>
                  </div>
                ))}
              </Accordion.Content>
            </Accordion.Item>
          </Accordion.Root>
        )}
      </div>
    </div>
  );
}
