"use client";

import React, { useState, useMemo, use } from "react";
import nextDynamic from "next/dynamic";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  ArrowLeft,
  Trash2,
  AlertCircle,
  Loader2,
  FileSearch,
  BookOpen,
  Key,
} from "lucide-react";
import * as Tabs from "@radix-ui/react-tabs";

import {
  api,
  type FindingResponse,
  type FindingHighlightItem,
} from "@/lib/api";
import { formatBytes, formatDate } from "@/lib/utils";
import { ProcessingView } from "@/components/processing-view";
import { SummaryCard } from "@/components/summary-card";
import { FindingsTab } from "@/components/findings-tab";
import { ClausesTab } from "@/components/clauses-tab";
import { KeyTermsTab } from "@/components/key-terms-tab";
import { DeleteDialog } from "@/components/delete-dialog";
import { useToast } from "@/components/toast-context";

export const dynamic = "force-dynamic";

// Dynamic import for PDF viewer with ssr: false
const DynamicPdfViewer = nextDynamic(
  () => import("@/components/pdf-viewer").then((mod) => mod.PdfViewer),
  {
    ssr: false,
    loading: () => (
      <div className="flex h-full min-h-[400px] w-full flex-col items-center justify-center bg-zinc-100 dark:bg-zinc-900 text-xs text-[var(--text-muted)] gap-2">
        <Loader2 className="h-6 w-6 animate-spin text-[var(--accent)]" />
        <span>Loading PDF viewer...</span>
      </div>
    ),
  }
);

interface DocumentPageProps {
  params: Promise<{ id: string }>;
}

export default function DocumentReportPage({ params }: DocumentPageProps) {
  const router = useRouter();
  const queryClient = useQueryClient();
  const { showToast } = useToast();

  const resolvedParams = use(params);
  const docId = resolvedParams.id;

  // Selected finding state for bi-directional highlight synchronization
  const [selectedFindingId, setSelectedFindingId] = useState<string | null>(null);
  const [targetPage, setTargetPage] = useState<number | null>(null);

  // Active right-panel tab
  const [activeTab, setActiveTab] = useState<"findings" | "clauses" | "key-terms">("findings");

  // Mobile / tablet viewport tabs: "pdf" vs "panel"
  const [mobileTab, setMobileTab] = useState<"pdf" | "panel">("pdf");

  // Resizable split divider state (percentage for left pane on desktop)
  const [splitRatio, setSplitRatio] = useState<number>(55);
  const [isResizing, setIsResizing] = useState<boolean>(false);

  // Delete dialog state
  const [showDeleteDialog, setShowDeleteDialog] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);

  // 1. Query Document details
  const {
    data: doc,
    isLoading: isDocLoading,
    isError: isDocError,
    error: docError,
  } = useQuery({
    queryKey: ["document", docId],
    queryFn: () => api.getDocument(docId),
    retry: 1,
  });

  // 2. Query Job details (polled if job not yet succeeded/dead)
  const jobId = doc?.latest_job_id;

  const { data: job } = useQuery({
    queryKey: ["job", jobId],
    queryFn: () => (jobId ? api.getJob(jobId) : null),
    enabled: Boolean(jobId),
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status === "succeeded" || status === "dead" ? false : 1500;
    },
  });

  const isJobDead = job?.status === "dead" || doc?.latest_job_status === "dead";
  const isJobSucceeded =
    !isJobDead && (job?.status === "succeeded" || doc?.latest_job_status === "succeeded");

  React.useEffect(() => {
    if (job?.status === "succeeded" && doc?.latest_job_status !== "succeeded") {
      queryClient.invalidateQueries({ queryKey: ["document", docId] });
    }
  }, [job?.status, doc?.latest_job_status, queryClient, docId]);

  // 3. Query Risk Summary
  const { data: riskSummary } = useQuery({
    queryKey: ["document-risk", docId],
    queryFn: () => api.getDocumentRisk(docId),
    enabled: isJobSucceeded,
  });

  // 4. Query Findings with highlights & feedback
  const { data: findingsData } = useQuery({
    queryKey: ["document-findings", docId],
    queryFn: () => api.getDocumentFindings(docId),
    enabled: isJobSucceeded,
  });

  // 5. Query Clauses
  const { data: clausesData } = useQuery({
    queryKey: ["document-clauses", docId],
    queryFn: () => api.getDocumentClauses(docId),
    enabled: isJobSucceeded,
  });

  // 6. Query Attributes (Key Terms)
  const { data: attributesData } = useQuery({
    queryKey: ["document-attributes", docId],
    queryFn: () => api.getDocumentAttributes(docId),
    enabled: isJobSucceeded,
  });

  // Feedback mutation with optimistic updates
  const feedbackMutation = useMutation({
    mutationFn: async ({
      findingId,
      verdict,
    }: {
      findingId: string;
      verdict: "confirmed" | "dismissed" | null;
    }) => {
      if (verdict === null) {
        return api.deleteFindingFeedback(findingId);
      }
      return api.setFindingFeedback(findingId, verdict);
    },
    onMutate: async ({ findingId, verdict }) => {
      await queryClient.cancelQueries({ queryKey: ["document-findings", docId] });
      const prevData = queryClient.getQueryData<{ items: FindingResponse[]; total: number }>([
        "document-findings",
        docId,
      ]);

      if (prevData) {
        queryClient.setQueryData(["document-findings", docId], {
          ...prevData,
          items: prevData.items.map((f) =>
            f.id === findingId
              ? {
                  ...f,
                  feedback: verdict ? { verdict, note: null, created_at: new Date().toISOString() } : null,
                }
              : f
          ),
        });
      }

      return { prevData };
    },
    onError: (_err, _vars, context) => {
      if (context?.prevData) {
        queryClient.setQueryData(["document-findings", docId], context.prevData);
      }
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ["document-findings", docId] });
    },
  });

  const handleFeedbackChange = (findingId: string, verdict: "confirmed" | "dismissed" | null) => {
    const finding = findingsData?.items.find((f) => f.id === findingId);
    const findingTitle = finding?.title || "Issue";
    const oldVerdict = (finding?.feedback?.verdict as "confirmed" | "dismissed" | undefined) || null;

    feedbackMutation.mutate({ findingId, verdict });

    if (verdict) {
      showToast(
        `${verdict === "confirmed" ? "Confirmed" : "Dismissed"}: ${findingTitle}`,
        () => {
          // Undo handler restores oldVerdict
          feedbackMutation.mutate({ findingId, verdict: oldVerdict });
        }
      );
    } else {
      showToast(`Reset review status for: ${findingTitle}`);
    }
  };

  const handleSelectFinding = (findingId: string, page?: number | null) => {
    setSelectedFindingId(findingId);
    if (page && page > 0) {
      setTargetPage(page);
    }
    // On small screens, switch to PDF tab when finding is selected
    if (window.innerWidth < 1024) {
      setMobileTab("pdf");
    }
  };

  const handleSelectPage = (page: number) => {
    setTargetPage(page);
    if (window.innerWidth < 1024) {
      setMobileTab("pdf");
    }
  };

  const handleDelete = async () => {
    setIsDeleting(true);
    try {
      await api.deleteDocument(docId);
      queryClient.invalidateQueries({ queryKey: ["documents"] });
      router.push("/");
    } catch {
      setIsDeleting(false);
    }
  };

  // Compile all highlights across findings for the PDF viewer
  const highlightsList = useMemo(() => {
    const list: { highlight: FindingHighlightItem; findingId: string }[] = [];
    (findingsData?.items || []).forEach((f) => {
      (f.highlights || []).forEach((h) => {
        list.push({ highlight: h, findingId: f.id });
      });
    });
    return list;
  }, [findingsData]);

  // Handle divider drag resizing
  const handleMouseDownResize = (e: React.MouseEvent) => {
    e.preventDefault();
    setIsResizing(true);

    const onMouseMove = (moveEvent: MouseEvent) => {
      const container = document.getElementById("split-workbench-container");
      if (!container) return;
      const rect = container.getBoundingClientRect();
      const currentX = moveEvent.clientX - rect.left;
      const pct = Math.max(30, Math.min(75, (currentX / rect.width) * 100));
      setSplitRatio(pct);
    };

    const onMouseUp = () => {
      setIsResizing(false);
      window.removeEventListener("mousemove", onMouseMove);
      window.removeEventListener("mouseup", onMouseUp);
    };

    window.addEventListener("mousemove", onMouseMove);
    window.addEventListener("mouseup", onMouseUp);
  };

  // Loading Document Skeleton
  if (isDocLoading) {
    return (
      <div className="mx-auto flex min-h-[60vh] w-full max-w-5xl flex-col items-center justify-center p-8">
        <Loader2 className="h-8 w-8 animate-spin text-[var(--accent)] mb-3" />
        <p className="text-sm font-medium text-[var(--text-secondary)]">Loading contract report...</p>
      </div>
    );
  }

  // Not Found / Error State
  if (isDocError || !doc) {
    return (
      <div className="mx-auto flex min-h-[60vh] max-w-md flex-col items-center justify-center px-4 text-center">
        <AlertCircle className="h-10 w-10 text-red-500 mb-3" />
        <h1 className="text-lg font-semibold text-[var(--text-primary)]">Contract not found</h1>
        <p className="mt-1 text-xs text-[var(--text-secondary)] max-w-sm">
          {docError instanceof Error
            ? docError.message
            : "The document you are looking for does not exist or may have been deleted."}
        </p>
        <div className="mt-6">
          <Link
            href="/"
            className="inline-flex items-center gap-1.5 rounded-lg bg-[var(--accent)] px-4 py-2 text-xs font-medium text-white hover:opacity-90"
          >
            <ArrowLeft className="h-3.5 w-3.5" />
            <span>Return to document list</span>
          </Link>
        </div>
      </div>
    );
  }

  // If job is still queued/running or failed (dead), show the processing stepper
  if (!isJobSucceeded || isJobDead) {
    return <ProcessingView job={job} filename={doc.original_filename} />;
  }

  const findings = findingsData?.items || [];
  const clauses = clausesData?.items || [];
  const attributes = attributesData;

  return (
    <div className="flex flex-1 flex-col overflow-hidden">
      {/* Sticky Top Bar */}
      <div className="sticky top-14 z-20 flex h-13 items-center justify-between border-b border-[var(--border-subtle)] bg-[var(--bg-card)] px-4 sm:px-6">
        <div className="flex items-center gap-3 truncate">
          <Link
            href="/"
            className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border border-[var(--border-subtle)] text-[var(--text-secondary)] hover:bg-[var(--bg-card-muted)] hover:text-[var(--text-primary)] transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--accent)]"
            aria-label="Back to document list"
          >
            <ArrowLeft className="h-4 w-4" />
          </Link>

          <div className="truncate">
            <h1 className="truncate text-sm font-semibold text-[var(--text-primary)]">
              {doc.original_filename}
            </h1>
            <div className="flex items-center gap-2 text-[11px] text-[var(--text-muted)]">
              <span>{formatDate(doc.created_at)}</span>
              <span>•</span>
              <span>{formatBytes(doc.size_bytes)}</span>
              {doc.page_count && (
                <>
                  <span>•</span>
                  <span>{doc.page_count} pages</span>
                </>
              )}
            </div>
          </div>
        </div>

        <div className="flex items-center gap-2 shrink-0">
          <button
            onClick={() => setShowDeleteDialog(true)}
            aria-label="Delete document"
            className="flex h-8 items-center gap-1.5 rounded-lg border border-[var(--border-subtle)] px-2.5 text-xs font-medium text-red-600 hover:bg-red-50 dark:hover:bg-red-950/40 transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-red-600"
          >
            <Trash2 className="h-3.5 w-3.5" />
            <span className="hidden sm:inline">Delete</span>
          </button>
        </div>
      </div>

      {/* Main Content Area */}
      <div className="flex-1 overflow-y-auto">
        <div className="mx-auto max-w-7xl p-4 sm:p-6 space-y-6">
          {/* Summary Card */}
          <SummaryCard
            summary={riskSummary}
            onSelectFinding={handleSelectFinding}
          />

          {/* Mobile & Tablet Mode Tabs (below 1024px) */}
          <div className="flex lg:hidden border-b border-[var(--border-subtle)] mb-4">
            <button
              onClick={() => setMobileTab("pdf")}
              className={`flex-1 py-2.5 text-xs font-semibold border-b-2 text-center transition-colors ${
                mobileTab === "pdf"
                  ? "border-[var(--accent)] text-[var(--accent)]"
                  : "border-transparent text-[var(--text-muted)] hover:text-[var(--text-primary)]"
              }`}
            >
              PDF Document
            </button>
            <button
              onClick={() => setMobileTab("panel")}
              className={`flex-1 py-2.5 text-xs font-semibold border-b-2 text-center transition-colors ${
                mobileTab === "panel"
                  ? "border-[var(--accent)] text-[var(--accent)]"
                  : "border-transparent text-[var(--text-muted)] hover:text-[var(--text-primary)]"
              }`}
            >
              Analysis & Tabs
            </button>
          </div>

          {/* Split View Container (Desktop 55/45 Resizable) */}
          <div
            id="split-workbench-container"
            style={
              {
                "--split-left": `${splitRatio}%`,
                "--split-right": `${100 - splitRatio}%`,
              } as React.CSSProperties
            }
            className={`relative flex h-[780px] w-full overflow-hidden rounded-2xl border border-[var(--border-subtle)] bg-[var(--bg-card)] shadow-xs ${
              isResizing ? "select-none cursor-col-resize" : ""
            }`}
          >
            {/* Left Pane: PDF Viewer */}
            <div
              className={`h-full overflow-hidden w-full lg:w-[var(--split-left)] ${
                mobileTab === "panel" ? "hidden lg:block" : "block"
              }`}
            >
              <DynamicPdfViewer
                fileUrl={api.getPdfFileUrl(docId)}
                highlights={highlightsList}
                selectedFindingId={selectedFindingId}
                onSelectFinding={(fid) => handleSelectFinding(fid)}
                targetPage={targetPage}
              />
            </div>

            {/* Resizable Divider (Desktop only) */}
            <div
              onMouseDown={handleMouseDownResize}
              className="hidden lg:flex w-2 cursor-col-resize items-center justify-center bg-transparent hover:bg-[var(--accent)]/30 transition-colors z-20 select-none group"
              title="Drag to resize split view"
            >
              <div className="h-8 w-1 rounded-full bg-[var(--border-hover)] group-hover:bg-[var(--accent)] transition-colors" />
            </div>

            {/* Right Pane: Tabs (Findings | Clauses | Key terms) */}
            <div
              className={`h-full overflow-hidden flex flex-col w-full lg:w-[var(--split-right)] ${
                mobileTab === "pdf" ? "hidden lg:flex" : "flex"
              }`}
            >
              <Tabs.Root
                value={activeTab}
                onValueChange={(val) => setActiveTab(val as typeof activeTab)}
                className="flex h-full flex-col"
              >
                {/* Tab Navigation Header */}
                <Tabs.List className="flex border-b border-[var(--border-subtle)] bg-[var(--bg-card)] px-3 text-xs">
                  <Tabs.Trigger
                    value="findings"
                    className={`flex items-center gap-1.5 py-3 px-3 font-medium border-b-2 transition-colors focus-visible:outline-none ${
                      activeTab === "findings"
                        ? "border-[var(--accent)] text-[var(--text-primary)] font-semibold"
                        : "border-transparent text-[var(--text-muted)] hover:text-[var(--text-primary)]"
                    }`}
                  >
                    <FileSearch className="h-3.5 w-3.5" />
                    <span>Findings</span>
                    <span className="ml-1 rounded-full bg-[var(--bg-card-muted)] px-1.5 py-0.2 text-[10px] font-mono border border-[var(--border-subtle)]">
                      {findings.length}
                    </span>
                  </Tabs.Trigger>

                  <Tabs.Trigger
                    value="clauses"
                    className={`flex items-center gap-1.5 py-3 px-3 font-medium border-b-2 transition-colors focus-visible:outline-none ${
                      activeTab === "clauses"
                        ? "border-[var(--accent)] text-[var(--text-primary)] font-semibold"
                        : "border-transparent text-[var(--text-muted)] hover:text-[var(--text-primary)]"
                    }`}
                  >
                    <BookOpen className="h-3.5 w-3.5" />
                    <span>Clauses</span>
                    <span className="ml-1 rounded-full bg-[var(--bg-card-muted)] px-1.5 py-0.2 text-[10px] font-mono border border-[var(--border-subtle)]">
                      {clauses.length}
                    </span>
                  </Tabs.Trigger>

                  <Tabs.Trigger
                    value="key-terms"
                    className={`flex items-center gap-1.5 py-3 px-3 font-medium border-b-2 transition-colors focus-visible:outline-none ${
                      activeTab === "key-terms"
                        ? "border-[var(--accent)] text-[var(--text-primary)] font-semibold"
                        : "border-transparent text-[var(--text-muted)] hover:text-[var(--text-primary)]"
                    }`}
                  >
                    <Key className="h-3.5 w-3.5" />
                    <span>Key Terms</span>
                  </Tabs.Trigger>
                </Tabs.List>

                {/* Tab 1: Findings Content */}
                <Tabs.Content value="findings" className="flex-1 overflow-hidden focus:outline-none">
                  <FindingsTab
                    findings={findings}
                    selectedFindingId={selectedFindingId}
                    onSelectFinding={handleSelectFinding}
                    onFeedbackChange={handleFeedbackChange}
                  />
                </Tabs.Content>

                {/* Tab 2: Clauses Content */}
                <Tabs.Content value="clauses" className="flex-1 overflow-hidden focus:outline-none">
                  <ClausesTab
                    clauses={clauses}
                    onSelectPage={handleSelectPage}
                  />
                </Tabs.Content>

                {/* Tab 3: Key Terms Content */}
                <Tabs.Content value="key-terms" className="flex-1 overflow-hidden focus:outline-none">
                  <KeyTermsTab
                    attributes={attributes}
                    clauses={clauses}
                    onSelectPage={handleSelectPage}
                  />
                </Tabs.Content>
              </Tabs.Root>
            </div>
          </div>
        </div>
      </div>

      {/* Delete Dialog */}
      <DeleteDialog
        open={showDeleteDialog}
        onOpenChange={setShowDeleteDialog}
        onConfirm={handleDelete}
        documentTitle={doc.original_filename}
        isDeleting={isDeleting}
      />
    </div>
  );
}
