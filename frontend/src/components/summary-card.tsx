"use client";

import React, { useState } from "react";
import { AlertTriangle, ChevronDown, ChevronUp, ArrowRight } from "lucide-react";
import type { RiskSummary, TopReason } from "@/lib/api";
import { RiskBadge } from "./risk-badge";
import { RiskGauge } from "./risk-gauge";
import { SeverityPill } from "./severity-pill";

interface SummaryCardProps {
  summary: RiskSummary | null | undefined;
  onSelectFinding: (findingId: string, page?: number | null) => void;
}

export function SummaryCard({ summary, onSelectFinding }: SummaryCardProps) {
  const [coverageExpanded, setCoverageExpanded] = useState(false);

  if (!summary) return null;

  const coverageNotes = summary.coverage_notes || [];
  const coverageWarnings = coverageNotes.filter((n) => n.level === "warning");
  const hasWarnings = coverageWarnings.length > 0;

  const countsCat = summary.counts_by_category || {};
  const tamperingCount = countsCat.tampering || 0;
  const inconsistencyCount = countsCat.inconsistency || 0;
  const minorCount = summary.minor_notes_count || 0;

  const topReasons = summary.top_reasons || [];

  return (
    <div className="rounded-2xl border border-[var(--border-subtle)] bg-[var(--bg-card)] p-5 sm:p-6 shadow-xs">
      {/* Limited Analysis Banner (Coverage Warnings) */}
      {hasWarnings && (
        <div
          role="region"
          aria-label="Analysis coverage caveats"
          className="mb-5 rounded-xl border border-amber-200 bg-amber-50 p-3.5 text-xs text-amber-900 dark:border-amber-900/60 dark:bg-amber-950/40 dark:text-amber-300"
        >
          <div className="flex items-start justify-between gap-3">
            <div className="flex items-center gap-2">
              <AlertTriangle className="h-4 w-4 shrink-0 text-amber-600 dark:text-amber-400" />
              <span className="font-semibold text-sm">Limited analysis</span>
              <span className="text-[11px] opacity-80">
                ({coverageWarnings.length} coverage warning{coverageWarnings.length > 1 ? "s" : ""})
              </span>
            </div>
            <button
              onClick={() => setCoverageExpanded(!coverageExpanded)}
              className="inline-flex items-center gap-1 font-medium hover:underline focus:outline-none"
            >
              <span>{coverageExpanded ? "Hide caveats" : "View caveats"}</span>
              {coverageExpanded ? (
                <ChevronUp className="h-3.5 w-3.5" />
              ) : (
                <ChevronDown className="h-3.5 w-3.5" />
              )}
            </button>
          </div>

          {coverageExpanded && (
            <ul className="mt-3 space-y-1.5 border-t border-amber-200/60 dark:border-amber-800/40 pt-2.5 list-disc pl-5">
              {coverageWarnings.map((w, idx) => (
                <li key={idx} className="leading-relaxed">
                  {w.message}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}

      {/* Main Grid: Score Gauge + Badge & Headline + 3 Category Tiles */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-12 lg:items-center">
        {/* Left: Gauge and Risk Band */}
        <div className="flex flex-col items-center justify-center border-b border-[var(--border-subtle)] pb-6 lg:col-span-4 lg:border-b-0 lg:border-r lg:pr-6 lg:pb-0">
          <RiskGauge score={summary.score} size={140} />
          <div className="mt-3">
            <RiskBadge
              band={summary.band}
              score={summary.score}
              hasWarning={hasWarnings}
              size="lg"
              showLabelText={true}
            />
          </div>
        </div>

        {/* Center: Headline & Top Reasons */}
        <div className="lg:col-span-5 flex flex-col justify-center">
          <h2 className="text-base font-semibold text-[var(--text-primary)] leading-snug sm:text-lg">
            {summary.headline}
          </h2>

          {topReasons.length > 0 && (
            <div className="mt-3 space-y-1.5">
              <span className="text-[10px] font-semibold uppercase tracking-wider text-[var(--text-muted)] block">
                Primary Review Items:
              </span>
              <div className="space-y-1">
                {topReasons.slice(0, 3).map((reason: TopReason, idx: number) => (
                  <button
                    key={idx}
                    onClick={() =>
                      reason.finding_id && onSelectFinding(reason.finding_id, reason.page)
                    }
                    className="flex w-full items-center justify-between rounded-lg p-1.5 text-left text-xs text-[var(--text-secondary)] hover:bg-[var(--bg-card-muted)] hover:text-[var(--text-primary)] transition-colors group focus-visible:outline focus-visible:outline-1"
                  >
                    <div className="flex items-center gap-2 truncate">
                      <SeverityPill severity={reason.severity} size="sm" />
                      <span className="truncate font-medium">{reason.title}</span>
                      {reason.clause_ref && (
                        <span className="text-[10px] font-mono text-[var(--text-muted)]">
                          cl. {reason.clause_ref}
                        </span>
                      )}
                    </div>
                    <ArrowRight className="h-3 w-3 text-[var(--text-muted)] group-hover:text-[var(--accent)] shrink-0 ml-1 transition-colors" />
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Right: Three Category Count Tiles */}
        <div className="grid grid-cols-3 gap-2.5 lg:col-span-3">
          <div className="rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-card-muted)] p-3 text-center">
            <span className="text-xl font-bold tracking-tight text-[var(--text-primary)] tabular-nums block">
              {tamperingCount}
            </span>
            <span className="text-[11px] font-medium text-[var(--text-secondary)] mt-0.5 block">
              Tampering
            </span>
          </div>

          <div className="rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-card-muted)] p-3 text-center">
            <span className="text-xl font-bold tracking-tight text-[var(--text-primary)] tabular-nums block">
              {inconsistencyCount}
            </span>
            <span className="text-[11px] font-medium text-[var(--text-secondary)] mt-0.5 block">
              Contradictions
            </span>
          </div>

          <div className="rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-card-muted)] p-3 text-center">
            <span className="text-xl font-bold tracking-tight text-[var(--text-primary)] tabular-nums block">
              {minorCount}
            </span>
            <span className="text-[11px] font-medium text-[var(--text-secondary)] mt-0.5 block">
              Minor Notes
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}
