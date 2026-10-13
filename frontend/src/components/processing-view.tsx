"use client";

import React from "react";
import Link from "next/link";
import { CheckCircle2, Clock, AlertTriangle, XCircle, ArrowLeft, Loader2 } from "lucide-react";
import type { JobStatusResponse, JobStageItem } from "@/lib/api";

interface ProcessingViewProps {
  job: JobStatusResponse | null | undefined;
  filename?: string;
  onRefresh?: () => void;
}

export function ProcessingView({ job, filename }: ProcessingViewProps) {
  const isDead = job?.status === "dead";
  const stages = job?.stages || [];

  const getFriendlyErrorMessage = (errorMsg?: string | null) => {
    if (!errorMsg) return "Analysis could not be completed for this document.";
    const lower = errorMsg.toLowerCase();
    if (lower.includes("password") || lower.includes("encrypt")) {
      return "This PDF is password-protected or encrypted. Please unlock the file before uploading.";
    }
    if (lower.includes("corrupt") || lower.includes("damaged") || lower.includes("eof marker")) {
      return "The PDF structure is corrupted or unreadable. Please re-export or check the file.";
    }
    if (lower.includes("not a pdf") || lower.includes("magic byte")) {
      return "The uploaded file is not a valid PDF document.";
    }
    if (lower.includes("page limit") || lower.includes("max pages")) {
      return "The document exceeds the safety page limit (maximum 100 pages).";
    }
    return errorMsg;
  };

  return (
    <div className="mx-auto flex min-h-[60vh] max-w-lg flex-col items-center justify-center px-4 py-12">
      <div className="w-full rounded-2xl border border-[var(--border-subtle)] bg-[var(--bg-card)] p-6 sm:p-8 shadow-sm">
        {/* Header */}
        <div className="mb-6 text-center">
          <span className="text-xs font-semibold uppercase tracking-wider text-[var(--text-muted)]">
            Contract Verification Pipeline
          </span>
          <h2 className="mt-1 text-lg font-semibold text-[var(--text-primary)] truncate max-w-md mx-auto">
            {filename || "Analyzing Contract"}
          </h2>
          <p className="mt-1 text-xs text-[var(--text-secondary)]">
            {isDead
              ? "Analysis halted due to an issue with the document"
              : "Running integrity checks, cross-references, and term extraction"}
          </p>
        </div>

        {/* Dead Job Banner */}
        {isDead && (
          <div
            role="alert"
            className="mb-6 rounded-xl border border-red-200 bg-red-50 p-4 text-xs text-red-800 dark:border-red-900/60 dark:bg-red-950/40 dark:text-red-300"
          >
            <div className="flex items-start gap-2.5">
              <XCircle className="h-4 w-4 shrink-0 text-red-600 dark:text-red-400 mt-0.5" />
              <div>
                <p className="font-semibold text-sm">Analysis Failed</p>
                <p className="mt-1 leading-relaxed">{getFriendlyErrorMessage(job?.last_error)}</p>
              </div>
            </div>
            <div className="mt-4 flex justify-end">
              <Link
                href="/"
                className="inline-flex items-center gap-1.5 rounded-lg bg-red-600 px-3.5 py-1.5 text-xs font-medium text-white hover:bg-red-700 transition-colors"
              >
                <ArrowLeft className="h-3.5 w-3.5" />
                <span>Upload another contract</span>
              </Link>
            </div>
          </div>
        )}

        {/* Vertical Stepper */}
        <div className="space-y-4 my-4" role="status" aria-live="polite">
          {stages.map((stage: JobStageItem, index: number) => {
            const isLast = index === stages.length - 1;
            const status = stage.status;

            let icon = (
              <Clock className="h-4 w-4 text-[var(--text-muted)]" />
            );
            let iconBg = "bg-[var(--bg-card-muted)] border-[var(--border-subtle)]";
            let statusText = "Pending";

            if (status === "done") {
              icon = <CheckCircle2 className="h-4 w-4 text-emerald-600 dark:text-emerald-400" />;
              iconBg = "bg-emerald-50 border-emerald-200 dark:bg-emerald-950/50 dark:border-emerald-800";
              statusText = "Completed";
            } else if (status === "running") {
              icon = <Loader2 className="h-4 w-4 text-[var(--accent)] animate-spin" />;
              iconBg = "bg-[var(--accent-subtle)] border-[var(--accent)]/40";
              statusText = "In progress...";
            } else if (status === "error") {
              icon = <XCircle className="h-4 w-4 text-red-600 dark:text-red-400" />;
              iconBg = "bg-red-50 border-red-200 dark:bg-red-950/50 dark:border-red-800";
              statusText = "Failed";
            } else if (status === "skipped") {
              icon = <AlertTriangle className="h-4 w-4 text-amber-500" />;
              iconBg = "bg-amber-50 border-amber-200 dark:bg-amber-950/50 dark:border-amber-800";
              statusText = "Skipped";
            }

            return (
              <div key={stage.key} className="relative flex items-start gap-3.5">
                {!isLast && (
                  <span
                    className={`absolute left-4 top-8 -bottom-4 w-0.5 ${
                      status === "done"
                        ? "bg-emerald-500/50"
                        : "bg-[var(--border-subtle)]"
                    }`}
                    aria-hidden="true"
                  />
                )}

                <div
                  className={`relative z-10 flex h-8 w-8 shrink-0 items-center justify-center rounded-full border ${iconBg}`}
                >
                  {icon}
                </div>

                <div className="flex-1 pt-1">
                  <div className="flex items-center justify-between">
                    <p className="text-sm font-medium text-[var(--text-primary)]">
                      {stage.label}
                    </p>
                    <span className="text-[11px] text-[var(--text-muted)] font-normal">
                      {statusText}
                    </span>
                  </div>
                </div>
              </div>
            );
          })}
        </div>

        {/* Action Link */}
        <div className="mt-8 border-t border-[var(--border-subtle)] pt-4 text-center">
          <Link
            href="/"
            className="inline-flex items-center gap-1.5 text-xs text-[var(--text-secondary)] hover:text-[var(--text-primary)] transition-colors"
          >
            <ArrowLeft className="h-3.5 w-3.5" />
            <span>Return to document list</span>
          </Link>
        </div>
      </div>
    </div>
  );
}
