/**
 * API client for ClauseGuard backend.
 * Provides strongly-typed fetch functions for documents, risk summaries,
 * jobs, findings, feedback, and key terms.
 */

import type { components } from "./api-types";

export type DocumentListItem = components["schemas"]["DocumentListItem"];
export type PaginatedDocumentsResponse = components["schemas"]["PaginatedDocumentsResponse"];
export type DocumentResponse = components["schemas"]["DocumentResponse"];
export type DocumentDetail = DocumentResponse;
export type RiskSummary = components["schemas"]["RiskSummary"];
export type TopReason = components["schemas"]["TopReason"];
export type FindingResponse = components["schemas"]["FindingResponse"];
export type FindingHighlightItem = components["schemas"]["FindingHighlightItem"];
export type FindingFeedbackItem = components["schemas"]["FindingFeedbackItem"];
export type JobStatusResponse = components["schemas"]["JobStatusResponse"];
export type JobStageItem = components["schemas"]["JobStageItem"];
export type ClauseResponse = components["schemas"]["ClauseResponse"];
export type DocumentAttributesResponse = components["schemas"]["DocumentAttributesResponse"];
export type FindingTypeInfo = components["schemas"]["FindingTypeInfo"];

export const API_BASE = (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000").replace(/\/$/, "");

export class ApiError extends Error {
  status: number;
  data: unknown;

  constructor(message: string, status: number, data?: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.data = data;
  }
}

async function fetchJson<T>(url: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(url, {
      ...init,
      headers: {
        Accept: "application/json",
        ...init?.headers,
      },
    });
  } catch (err: unknown) {
    const msg = err instanceof Error ? err.message : "Network error";
    throw new ApiError(`Unable to reach ClauseGuard API (${msg}). Is the server running?`, 0);
  }

  if (!res.ok) {
    let detail = `Request failed with status ${res.status}`;
    let data: unknown = null;
    try {
      data = await res.json();
      if (data && typeof data === "object" && "detail" in data) {
        detail = String((data as { detail: unknown }).detail);
      }
    } catch {
      // not JSON
    }
    throw new ApiError(detail, res.status, data);
  }

  if (res.status === 204) {
    return null as unknown as T;
  }

  return res.json() as Promise<T>;
}

export const api = {
  getDocuments: (params?: { limit?: number; offset?: number; status?: string }) => {
    const query = new URLSearchParams();
    if (params?.limit !== undefined) query.set("limit", String(params.limit));
    if (params?.offset !== undefined) query.set("offset", String(params.offset));
    if (params?.status) query.set("status", params.status);
    const qs = query.toString() ? `?${query.toString()}` : "";
    return fetchJson<PaginatedDocumentsResponse>(`${API_BASE}/v1/documents${qs}`);
  },

  getDocument: (id: string) => {
    return fetchJson<DocumentDetail>(`${API_BASE}/v1/documents/${id}`);
  },

  getDocumentRisk: (id: string) => {
    return fetchJson<RiskSummary>(`${API_BASE}/v1/documents/${id}/risk`);
  },

  getDocumentFindings: (id: string) => {
    return fetchJson<{ items: FindingResponse[]; total: number }>(`${API_BASE}/v1/documents/${id}/findings`);
  },

  getDocumentClauses: (id: string) => {
    return fetchJson<{ items: ClauseResponse[]; total: number }>(`${API_BASE}/v1/documents/${id}/clauses`);
  },

  getDocumentAttributes: (id: string) => {
    return fetchJson<DocumentAttributesResponse>(`${API_BASE}/v1/documents/${id}/attributes`);
  },

  getJob: (jobId: string) => {
    return fetchJson<JobStatusResponse>(`${API_BASE}/v1/jobs/${jobId}`);
  },

  getFindingTypes: () => {
    return fetchJson<{ items: FindingTypeInfo[]; total: number }>(`${API_BASE}/v1/finding-types`);
  },

  uploadDocument: async (file: File) => {
    const formData = new FormData();
    formData.append("file", file);

    const res = await fetch(`${API_BASE}/v1/documents`, {
      method: "POST",
      body: formData,
    });

    if (!res.ok) {
      let detail = `Upload failed with status ${res.status}`;
      try {
        const data = await res.json();
        if (data && typeof data === "object" && "detail" in data) {
          detail = String(data.detail);
        }
      } catch {
        // ignore
      }
      throw new ApiError(detail, res.status);
    }

    return res.json() as Promise<{
      document_id: string;
      job_id: string;
      sha256: string;
      status: string;
      deduplicated?: boolean;
    }>;
  },

  deleteDocument: async (id: string) => {
    const res = await fetch(`${API_BASE}/v1/documents/${id}`, {
      method: "DELETE",
    });
    if (!res.ok && res.status !== 204 && res.status !== 404) {
      throw new ApiError(`Delete failed with status ${res.status}`, res.status);
    }
    return true;
  },

  setFindingFeedback: (findingId: string, verdict: "confirmed" | "dismissed", note?: string) => {
    return fetchJson<FindingFeedbackItem>(`${API_BASE}/v1/findings/${findingId}/feedback`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ verdict, note: note || null }),
    });
  },

  deleteFindingFeedback: async (findingId: string) => {
    const res = await fetch(`${API_BASE}/v1/findings/${findingId}/feedback`, {
      method: "DELETE",
    });
    if (!res.ok && res.status !== 204) {
      throw new ApiError(`Failed to delete feedback (${res.status})`, res.status);
    }
    return true;
  },

  getPdfFileUrl: (id: string) => {
    return `${API_BASE}/v1/documents/${id}/file`;
  },
};
