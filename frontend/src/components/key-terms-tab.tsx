"use client";

import React from "react";
import { Scale, Clock, RefreshCw, Shield, DollarSign, ExternalLink, Calendar } from "lucide-react";
import type { DocumentAttributesResponse, ClauseResponse } from "@/lib/api";

interface KeyTermsTabProps {
  attributes: DocumentAttributesResponse | null | undefined;
  clauses: ClauseResponse[];
  onSelectPage: (page: number) => void;
}

export function KeyTermsTab({ attributes, clauses, onSelectPage }: KeyTermsTabProps) {
  // Find clause associated with a label
  const findClauseForLabel = (labelPattern: string) => {
    return clauses.find((c) =>
      c.labels?.some((l) => l.label.toLowerCase().includes(labelPattern.toLowerCase()))
    );
  };

  const govLawClause = findClauseForLabel("governing_law");
  const termNoticeClause = findClauseForLabel("termination");
  const renewalClause = findClauseForLabel("renewal");
  const liabilityClause = findClauseForLabel("liability");
  const nonCompeteClause = findClauseForLabel("non_compete");
  const paymentClause = findClauseForLabel("payment");

  const terms = [
    {
      title: "Governing Law",
      icon: <Scale className="h-4 w-4 text-[var(--accent)]" />,
      value: attributes?.governing_law_jurisdiction || "Not found",
      clause: govLawClause,
    },
    {
      title: "Termination Notice",
      icon: <Clock className="h-4 w-4 text-[var(--accent)]" />,
      value:
        attributes?.termination_notice_days !== null && attributes?.termination_notice_days !== undefined
          ? `${attributes.termination_notice_days} days`
          : "Not found",
      clause: termNoticeClause,
    },
    {
      title: "Auto-renews",
      icon: <RefreshCw className="h-4 w-4 text-[var(--accent)]" />,
      value:
        attributes?.auto_renews === true
          ? "Yes (Automatic)"
          : attributes?.auto_renews === false
          ? "No (Fixed term)"
          : "Not found",
      clause: renewalClause,
    },
    {
      title: "Renewal Term",
      icon: <Calendar className="h-4 w-4 text-[var(--accent)]" />,
      value:
        attributes?.renewal_term_months !== null && attributes?.renewal_term_months !== undefined
          ? `${attributes.renewal_term_months} months`
          : "Not found",
      clause: renewalClause,
    },
    {
      title: "Non-renewal Notice",
      icon: <Clock className="h-4 w-4 text-[var(--accent)]" />,
      value:
        attributes?.non_renewal_notice_days !== null && attributes?.non_renewal_notice_days !== undefined
          ? `${attributes.non_renewal_notice_days} days`
          : "Not found",
      clause: renewalClause,
    },
    {
      title: "Liability Cap",
      icon: <Shield className="h-4 w-4 text-[var(--accent)]" />,
      value: attributes?.liability_cap
        ? typeof attributes.liability_cap === "object"
          ? (attributes.liability_cap as { description?: string; amount?: string }).description ||
            (attributes.liability_cap as { amount?: string }).amount ||
            "Specified in contract"
          : String(attributes.liability_cap)
        : "Not found",
      clause: liabilityClause,
    },
    {
      title: "Non-compete Duration",
      icon: <Clock className="h-4 w-4 text-[var(--accent)]" />,
      value:
        attributes?.non_compete_duration_months !== null &&
        attributes?.non_compete_duration_months !== undefined
          ? `${attributes.non_compete_duration_months} months`
          : "Not found",
      clause: nonCompeteClause,
    },
    {
      title: "Payment Terms",
      icon: <DollarSign className="h-4 w-4 text-[var(--accent)]" />,
      value:
        attributes?.payment_terms_days !== null && attributes?.payment_terms_days !== undefined
          ? `Net ${attributes.payment_terms_days} days`
          : "Not found",
      clause: paymentClause,
    },
  ];

  return (
    <div className="flex-1 overflow-y-auto p-4 space-y-3">
      <div className="mb-2">
        <span className="text-[11px] font-semibold uppercase tracking-wider text-[var(--text-muted)]">
          Contractual Terms & Obligations
        </span>
        <p className="text-xs text-[var(--text-secondary)] mt-0.5">
          Extracted standard business parameters and legal provisions.
        </p>
      </div>

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        {terms.map((term, idx) => {
          const isFound = term.value !== "Not found";
          const page = term.clause?.page_start || 1;

          return (
            <div
              key={idx}
              className="rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-card)] p-3.5 text-xs transition-colors hover:border-[var(--border-hover)]"
            >
              <div className="flex items-center justify-between text-[var(--text-muted)]">
                <div className="flex items-center gap-1.5">
                  {term.icon}
                  <span className="font-medium text-[var(--text-secondary)]">{term.title}</span>
                </div>
                {term.clause && (
                  <span className="text-[10px] font-mono">
                    Clause {term.clause.clause_id || term.clause.order_idx + 1}
                  </span>
                )}
              </div>

              <div className="mt-2 flex items-baseline justify-between">
                <span
                  className={`text-sm font-semibold tracking-tight ${
                    isFound ? "text-[var(--text-primary)]" : "text-[var(--text-muted)] font-normal italic"
                  }`}
                >
                  {term.value}
                </span>

                {isFound && term.clause && (
                  <button
                    onClick={() => onSelectPage(page)}
                    className="inline-flex items-center gap-1 text-[11px] font-medium text-[var(--accent)] hover:underline focus-visible:outline focus-visible:outline-1"
                  >
                    <span>View in contract</span>
                    <ExternalLink className="h-3 w-3" />
                  </button>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
