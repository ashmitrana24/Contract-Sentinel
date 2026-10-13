"use client";

import React, { useState, useRef } from "react";
import { useRouter } from "next/navigation";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  UploadCloud,
  FileText,
  AlertCircle,
  MoreVertical,
  Trash2,
  ExternalLink,
  RefreshCw,
  FolderOpen,
} from "lucide-react";
import * as DropdownMenu from "@radix-ui/react-dropdown-menu";
import { api, type DocumentListItem } from "@/lib/api";
import { formatBytes, formatDate } from "@/lib/utils";
import { RiskBadge } from "@/components/risk-badge";
import { DeleteDialog } from "@/components/delete-dialog";

const MAX_FILE_SIZE = 25 * 1024 * 1024; // 25 MB

const SAMPLES = [
  {
    id: "clean",
    name: "Clean Contract",
    filename: "clean_consulting_agreement.pdf",
    description: "Standard consulting contract with zero integrity findings",
  },
  {
    id: "amount_date",
    name: "Amount & Date Discrepancy",
    filename: "amount_and_date_discrepancy.pdf",
    description: "Numeric vs written words mismatch and chronological date conflicts",
  },
  {
    id: "edited",
    name: "Edited PDF Contract",
    filename: "post_creation_edited_contract.pdf",
    description: "Post-creation modification with revisions and hidden text",
  },
];

export default function HomePage() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [dragActive, setDragActive] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState<string | null>(null);

  // Delete modal state
  const [deleteDoc, setDeleteDoc] = useState<DocumentListItem | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);

  // Query recent documents
  const {
    data: docsData,
    isLoading: isDocsLoading,
    isError: isDocsError,
    error: docsError,
    refetch: refetchDocs,
  } = useQuery({
    queryKey: ["documents"],
    queryFn: () => api.getDocuments({ limit: 50 }),
    refetchInterval: (query) => {
      // Poll while any document is queued or running
      const items = query.state.data?.items || [];
      const hasPending = items.some((it) => it.status === "queued" || it.status === "running");
      return hasPending ? 2000 : false;
    },
  });

  const uploadMutation = useMutation({
    mutationFn: (file: File) => api.uploadDocument(file),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ["documents"] });
      setIsUploading(false);
      setUploadProgress(null);
      router.push(`/documents/${data.document_id}`);
    },
    onError: (err: unknown) => {
      setIsUploading(false);
      setUploadProgress(null);
      const msg = err instanceof Error ? err.message : "Failed to upload file";
      setUploadError(msg);
    },
  });

  const handleFile = async (file: File) => {
    setUploadError(null);

    // Client-side validation
    if (!file.name.toLowerCase().endsWith(".pdf") && file.type !== "application/pdf") {
      setUploadError("Only PDF documents are supported (.pdf).");
      return;
    }

    if (file.size > MAX_FILE_SIZE) {
      setUploadError(`File exceeds maximum size limit of 25 MB (${formatBytes(file.size)}).`);
      return;
    }

    setIsUploading(true);
    setUploadProgress(`Uploading ${file.name}...`);
    uploadMutation.mutate(file);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);

    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      handleFile(e.dataTransfer.files[0]);
    }
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(true);
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
  };

  const loadSample = async (sampleFilename: string) => {
    setUploadError(null);
    setIsUploading(true);
    setUploadProgress(`Loading sample: ${sampleFilename}...`);

    try {
      const res = await fetch(`/samples/${sampleFilename}`);
      if (!res.ok) {
        throw new Error(`Failed to load sample asset (${res.status})`);
      }
      const blob = await res.blob();
      const file = new File([blob], sampleFilename, { type: "application/pdf" });
      uploadMutation.mutate(file);
    } catch (err: unknown) {
      setIsUploading(false);
      setUploadProgress(null);
      const msg = err instanceof Error ? err.message : "Error loading sample contract";
      setUploadError(msg);
    }
  };

  const confirmDelete = async () => {
    if (!deleteDoc) return;
    setIsDeleting(true);
    try {
      await api.deleteDocument(deleteDoc.id);
      queryClient.invalidateQueries({ queryKey: ["documents"] });
      setDeleteDoc(null);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Error deleting document";
      setUploadError(msg);
    } finally {
      setIsDeleting(false);
    }
  };

  const items = docsData?.items || [];

  return (
    <div className="mx-auto w-full max-w-5xl px-4 py-8 sm:px-6 sm:py-12">
      {/* Page Title & Mission */}
      <div className="mb-8 text-center sm:mb-10">
        <h1 className="text-2xl font-semibold tracking-tight text-[var(--text-primary)] sm:text-3xl">
          Review contracts for tampering, contradictions and key terms
        </h1>
        <p className="mt-2 text-sm text-[var(--text-secondary)] sm:text-base max-w-2xl mx-auto">
          An evidence-based workbench that flags structural tampering, internal contradictions,
          and contractual terms for human verification.
        </p>
      </div>

      {/* API Unreachable Banner */}
      {isDocsError && (
        <div
          role="alert"
          className="mb-8 flex items-center justify-between rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-800 dark:border-red-900/60 dark:bg-red-950/40 dark:text-red-300"
        >
          <div className="flex items-center gap-3">
            <AlertCircle className="h-5 w-5 shrink-0 text-red-600 dark:text-red-400" />
            <div>
              <p className="font-semibold">ClauseGuard API is unreachable</p>
              <p className="text-xs opacity-90">
                {docsError instanceof Error ? docsError.message : "Cannot connect to server."}
              </p>
            </div>
          </div>
          <button
            onClick={() => refetchDocs()}
            className="inline-flex items-center gap-1.5 rounded-lg border border-red-300 bg-white px-3 py-1.5 text-xs font-medium text-red-900 shadow-sm hover:bg-red-50 dark:border-red-800 dark:bg-red-900/50 dark:text-red-200"
          >
            <RefreshCw className="h-3.5 w-3.5" />
            <span>Retry</span>
          </button>
        </div>
      )}

      {/* Drag & Drop Upload Zone */}
      <div className="mb-6">
        <div
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
          onClick={() => fileInputRef.current?.click()}
          role="button"
          tabIndex={0}
          onKeyDown={(e) => {
            if (e.key === "Enter" || e.key === " ") {
              e.preventDefault();
              fileInputRef.current?.click();
            }
          }}
          className={`group relative flex flex-col items-center justify-center rounded-2xl border-2 border-dashed p-8 sm:p-12 text-center transition-all cursor-pointer focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--accent)] ${
            dragActive
              ? "border-[var(--accent)] bg-[var(--accent-subtle)]"
              : "border-[var(--border-subtle)] bg-[var(--bg-card)] hover:border-[var(--border-hover)] hover:bg-[var(--bg-card-muted)]"
          }`}
        >
          <input
            ref={fileInputRef}
            type="file"
            accept="application/pdf,.pdf"
            className="hidden"
            onChange={(e) => {
              if (e.target.files && e.target.files[0]) {
                handleFile(e.target.files[0]);
              }
            }}
          />

          <div className="mb-4 flex h-14 w-14 items-center justify-center rounded-2xl bg-[var(--accent-subtle)] text-[var(--accent)] transition-transform group-hover:scale-105">
            <UploadCloud className="h-7 w-7" />
          </div>

          <p className="text-base font-semibold text-[var(--text-primary)]">
            {isUploading ? uploadProgress : "Upload a contract for review"}
          </p>
          <p className="mt-1 text-sm text-[var(--text-secondary)]">
            Drag and drop your PDF here, or click to browse
          </p>
          <span className="mt-3 inline-flex items-center rounded-md bg-[var(--bg-card-muted)] px-2.5 py-1 text-xs text-[var(--text-muted)] border border-[var(--border-subtle)]">
            PDF only • Maximum 25 MB
          </span>
        </div>

        {uploadError && (
          <div
            role="alert"
            className="mt-3 flex items-start gap-2.5 rounded-lg border border-red-200 bg-red-50 p-3 text-xs text-red-800 dark:border-red-900/60 dark:bg-red-950/40 dark:text-red-300"
          >
            <AlertCircle className="h-4 w-4 shrink-0 text-red-600 dark:text-red-400 mt-0.5" />
            <p className="flex-1">{uploadError}</p>
          </div>
        )}
      </div>

      {/* Try a Sample Contract Control */}
      <div className="mb-10 rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-card)] p-4 sm:p-5">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <FolderOpen className="h-4 w-4 text-[var(--text-muted)]" />
            <h2 className="text-xs font-semibold uppercase tracking-wider text-[var(--text-secondary)]">
              Try a sample contract
            </h2>
          </div>
          <span className="text-[11px] text-[var(--text-muted)]">
            Synthetic datasets • zero confidential data
          </span>
        </div>

        <div className="grid grid-cols-1 gap-2.5 sm:grid-cols-3">
          {SAMPLES.map((sample) => (
            <button
              key={sample.id}
              disabled={isUploading}
              onClick={() => loadSample(sample.filename)}
              className="flex flex-col items-start rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-card)] p-3 text-left transition-colors hover:border-[var(--accent)] hover:bg-[var(--bg-card-muted)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--accent)] disabled:opacity-50"
            >
              <div className="flex items-center justify-between w-full">
                <span className="text-sm font-medium text-[var(--text-primary)]">
                  {sample.name}
                </span>
                <ExternalLink className="h-3.5 w-3.5 text-[var(--text-muted)]" />
              </div>
              <p className="mt-1 text-xs text-[var(--text-secondary)] line-clamp-2 leading-relaxed">
                {sample.description}
              </p>
            </button>
          ))}
        </div>
      </div>

      {/* Recent Documents Section */}
      <div>
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-xs font-semibold uppercase tracking-wider text-[var(--text-secondary)]">
            Recent documents
          </h2>
          <span className="text-xs text-[var(--text-muted)] tabular-nums" role="status">
            {items.length} {items.length === 1 ? "document" : "documents"}
          </span>
        </div>

        {isDocsLoading && (
          <div className="space-y-3">
            {[1, 2, 3].map((n) => (
              <div
                key={n}
                className="h-16 w-full animate-pulse rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-card)]"
              />
            ))}
          </div>
        )}

        {!isDocsLoading && items.length === 0 && (
          <div className="flex flex-col items-center justify-center rounded-2xl border border-[var(--border-subtle)] bg-[var(--bg-card)] py-12 px-4 text-center">
            {/* Inline SVG empty state illustration */}
            <svg
              className="h-16 w-16 text-[var(--text-muted)] opacity-60 mb-3"
              viewBox="0 0 64 64"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
              aria-hidden="true"
            >
              <path d="M40 8H16a4 4 0 0 0-4 4v40a4 4 0 0 0 4 4h32a4 4 0 0 0 4-4V20z" />
              <polyline points="40 8 40 20 52 20" />
              <line x1="24" y1="32" x2="40" y2="32" />
              <line x1="24" y1="40" x2="36" y2="40" />
            </svg>
            <h3 className="text-sm font-semibold text-[var(--text-primary)]">
              No contracts uploaded yet
            </h3>
            <p className="mt-1 text-xs text-[var(--text-secondary)] max-w-sm">
              Upload a PDF contract above or click one of the sample agreements to review the
              analysis workbench.
            </p>
          </div>
        )}

        {!isDocsLoading && items.length > 0 && (
          <div className="overflow-hidden rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-card)] shadow-xs">
            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse">
                <thead>
                  <tr className="border-b border-[var(--border-subtle)] bg-[var(--bg-card-muted)] text-[11px] uppercase tracking-wider font-semibold text-[var(--text-muted)]">
                    <th scope="col" className="py-3 px-4">Document</th>
                    <th scope="col" className="py-3 px-3">Uploaded</th>
                    <th scope="col" className="py-3 px-3">Status</th>
                    <th scope="col" className="py-3 px-3">Risk Assessment</th>
                    <th scope="col" className="py-3 px-3">Issues by Severity</th>
                    <th scope="col" className="py-3 px-4 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[var(--border-subtle)] text-sm">
                  {items.map((doc) => {
                    const isProcessing = doc.status === "queued" || doc.status === "running";
                    return (
                      <tr
                        key={doc.id}
                        onClick={() => router.push(`/documents/${doc.id}`)}
                        className="group cursor-pointer hover:bg-[var(--bg-card-muted)] transition-colors"
                      >
                        <td className="py-3 px-4 font-medium text-[var(--text-primary)]">
                          <div className="flex items-center gap-2.5">
                            <FileText className="h-4 w-4 text-[var(--text-muted)] group-hover:text-[var(--accent)] shrink-0 transition-colors" />
                            <div className="truncate max-w-xs sm:max-w-md">
                              <span className="block truncate">{doc.filename}</span>
                              <span className="text-[11px] text-[var(--text-muted)] font-normal">
                                {formatBytes(doc.size)} • {doc.page_count ? `${doc.page_count} pages` : "Pages unknown"}
                              </span>
                            </div>
                          </div>
                        </td>

                        <td className="py-3 px-3 text-xs text-[var(--text-secondary)] whitespace-nowrap">
                          {formatDate(doc.uploaded_at)}
                        </td>

                        <td className="py-3 px-3 whitespace-nowrap">
                          <span
                            className={`inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-xs font-medium ${
                              doc.status === "succeeded"
                                ? "bg-emerald-50 text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-300"
                                : doc.status === "dead"
                                ? "bg-red-50 text-red-700 dark:bg-red-950/40 dark:text-red-300"
                                : "bg-amber-50 text-amber-700 dark:bg-amber-950/40 dark:text-amber-300 animate-pulse"
                            }`}
                          >
                            <span className="h-1.5 w-1.5 rounded-full bg-current" />
                            <span className="capitalize">{doc.status}</span>
                          </span>
                        </td>

                        <td className="py-3 px-3 whitespace-nowrap">
                          {doc.risk ? (
                            <RiskBadge
                              band={doc.risk.band}
                              score={doc.risk.score}
                              size="sm"
                              hasWarning={false}
                            />
                          ) : (
                            <span className="text-xs text-[var(--text-muted)]">
                              {isProcessing ? "Analyzing..." : "Pending"}
                            </span>
                          )}
                        </td>

                        <td className="py-3 px-3 whitespace-nowrap">
                          {doc.finding_counts_by_severity ? (
                            <div className="flex items-center gap-2 text-xs tabular-nums text-[var(--text-secondary)]">
                              <span title="Critical" className="inline-flex items-center gap-1">
                                <span className="h-2 w-2 rounded-full bg-red-600" />
                                {doc.finding_counts_by_severity.critical || 0}
                              </span>
                              <span title="High" className="inline-flex items-center gap-1">
                                <span className="h-2 w-2 rounded-full bg-orange-500" />
                                {doc.finding_counts_by_severity.high || 0}
                              </span>
                              <span title="Medium" className="inline-flex items-center gap-1">
                                <span className="h-2 w-2 rounded-full bg-amber-500" />
                                {doc.finding_counts_by_severity.medium || 0}
                              </span>
                              <span title="Low" className="inline-flex items-center gap-1">
                                <span className="h-2 w-2 rounded-full bg-slate-400" />
                                {doc.finding_counts_by_severity.low || 0}
                              </span>
                            </div>
                          ) : (
                            <span className="text-xs text-[var(--text-muted)]">—</span>
                          )}
                        </td>

                        <td className="py-3 px-4 text-right whitespace-nowrap" onClick={(e) => e.stopPropagation()}>
                          <DropdownMenu.Root>
                            <DropdownMenu.Trigger asChild>
                              <button
                                aria-label="Open document options"
                                className="rounded-lg p-1.5 text-[var(--text-muted)] hover:bg-[var(--border-subtle)] hover:text-[var(--text-primary)] transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--accent)]"
                              >
                                <MoreVertical className="h-4 w-4" />
                              </button>
                            </DropdownMenu.Trigger>
                            <DropdownMenu.Portal>
                              <DropdownMenu.Content
                                align="end"
                                className="z-40 min-w-[140px] rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-card)] p-1 shadow-lg text-xs"
                              >
                                <DropdownMenu.Item
                                  onClick={() => router.push(`/documents/${doc.id}`)}
                                  className="flex cursor-pointer items-center gap-2 rounded-md px-2.5 py-1.5 text-[var(--text-primary)] hover:bg-[var(--bg-card-muted)] focus:outline-none"
                                >
                                  <ExternalLink className="h-3.5 w-3.5" />
                                  <span>Open report</span>
                                </DropdownMenu.Item>
                                <DropdownMenu.Separator className="my-1 h-px bg-[var(--border-subtle)]" />
                                <DropdownMenu.Item
                                  onClick={() => setDeleteDoc(doc)}
                                  className="flex cursor-pointer items-center gap-2 rounded-md px-2.5 py-1.5 text-red-600 hover:bg-red-50 dark:hover:bg-red-950/40 focus:outline-none"
                                >
                                  <Trash2 className="h-3.5 w-3.5" />
                                  <span>Delete</span>
                                </DropdownMenu.Item>
                              </DropdownMenu.Content>
                            </DropdownMenu.Portal>
                          </DropdownMenu.Root>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>

      {/* Delete Confirmation Modal */}
      <DeleteDialog
        open={Boolean(deleteDoc)}
        onOpenChange={(open) => !open && setDeleteDoc(null)}
        onConfirm={confirmDelete}
        documentTitle={deleteDoc?.filename}
        isDeleting={isDeleting}
      />
    </div>
  );
}
