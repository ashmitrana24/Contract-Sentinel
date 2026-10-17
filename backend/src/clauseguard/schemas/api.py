"""API request / response schemas."""

from __future__ import annotations

import uuid
from typing import Any

from pydantic import BaseModel, Field

from clauseguard.risk.catalog import FindingTypeInfo


class UploadResponse(BaseModel):
    document_id: uuid.UUID
    job_id: uuid.UUID
    deduplicated: bool = False


class JobStageItem(BaseModel):
    key: str
    label: str
    status: str  # pending|running|done|error|skipped


class JobStatusResponse(BaseModel):
    job_id: uuid.UUID
    document_id: uuid.UUID
    status: str
    attempts: int
    max_attempts: int
    last_error: str | None
    error_kind: str | None
    enqueued_at: str | None
    started_at: str | None
    finished_at: str | None
    next_attempt_at: str | None
    stages: list[JobStageItem] = Field(default_factory=list)


class DocumentRiskSummaryBrief(BaseModel):
    score: int
    band: str


class DocumentListItem(BaseModel):
    id: uuid.UUID
    filename: str
    size: int
    uploaded_at: str
    status: str
    page_count: int | None
    risk: DocumentRiskSummaryBrief | None
    finding_counts_by_severity: dict[str, int] = Field(default_factory=dict)


class PaginatedDocumentsResponse(BaseModel):
    total: int
    limit: int
    offset: int
    items: list[DocumentListItem]


class DocumentResponse(BaseModel):
    document_id: uuid.UUID
    sha256: str
    original_filename: str
    size_bytes: int
    storage_key: str
    page_count: int | None
    needs_ocr: bool
    pdf_metadata: dict | None
    created_at: str
    latest_job_id: uuid.UUID | None
    latest_job_status: str | None
    clause_count: int
    finding_count: int = 0
    finding_counts_by_module: dict[str, int] = Field(default_factory=dict)


class FindingFeedbackItem(BaseModel):
    verdict: str  # confirmed|dismissed
    note: str | None = None
    created_at: str | None = None


class FindingFeedbackRequest(BaseModel):
    verdict: str = Field(description="'confirmed' or 'dismissed'")
    note: str | None = None


class FindingHighlightItem(BaseModel):
    page: int
    bbox: list[float]  # [x0, y0, x1, y1]
    page_width: float
    page_height: float
    rotation: int = 0
    approximate: bool = False


class FindingResponse(BaseModel):
    id: uuid.UUID
    document_id: uuid.UUID
    module: str
    type: str
    severity: str
    category: str = "inconsistency"
    title: str = ""
    what_it_means: str = ""
    what_to_check: str = ""
    uncertain: bool = False
    feedback: FindingFeedbackItem | None = None
    highlights: list[FindingHighlightItem] = Field(default_factory=list)
    page: int | None = None
    clause_ref: str | None = None
    bbox: list[float] | None = None
    evidence: str
    explanation: str
    confidence: float | None = None
    details: dict = Field(default_factory=dict)
    created_at: str


class PaginatedFindings(BaseModel):
    total: int
    limit: int
    offset: int
    items: list[FindingResponse]


class FindingTypeListResponse(BaseModel):
    items: list[FindingTypeInfo]


class AnalysisRunResponse(BaseModel):
    id: uuid.UUID
    document_id: uuid.UUID
    module: str
    version: str
    status: str
    duration_ms: int
    error: str | None
    detector_status: dict
    created_at: str


class PageResponse(BaseModel):
    page_no: int
    width: float
    height: float
    text: str
    char_count: int
    spans: list[dict]


class ClauseLabelItem(BaseModel):
    label: str
    score: float
    method: str
    evidence: str


class ClauseResponse(BaseModel):
    order_idx: int
    clause_id: str
    heading: str
    text: str
    level: int
    parent_clause_id: str | None
    page_start: int
    page_end: int
    kind: str
    labels: list[ClauseLabelItem] = Field(default_factory=list)


class ClauseTypeSummaryItem(BaseModel):
    label: str
    name: str
    count: int
    max_score: float
    clause_ids: list[str] = Field(default_factory=list)


class ClauseTypesResponse(BaseModel):
    document_id: uuid.UUID
    total_types: int
    items: list[ClauseTypeSummaryItem]


class DocumentAttributesResponse(BaseModel):
    document_id: uuid.UUID
    governing_law_jurisdiction: str | None = None
    termination_notice_days: int | None = None
    auto_renews: bool | None = None
    renewal_term_months: int | None = None
    non_renewal_notice_days: int | None = None
    liability_cap: dict[str, Any] | None = None
    limitation_of_liability: dict[str, Any] | None = None
    non_compete_duration_months: int | None = None
    payment_terms_days: int | None = None


class PaginatedPages(BaseModel):
    total: int
    limit: int
    offset: int
    items: list[PageResponse]


class PaginatedClauses(BaseModel):
    total: int
    limit: int
    offset: int
    items: list[ClauseResponse]


class HealthResponse(BaseModel):
    status: str
    postgres: str
    redis: str


class ErrorResponse(BaseModel):
    error: str = Field(description="Machine-readable error code")
    detail: str = Field(description="Human-readable message")


# --- Module 6: Ask ClauseGuard & LLM Schemas ---

class LLMStatusResponse(BaseModel):
    provider: str
    model: str
    available: bool
    streaming: bool
    assistant_name: str = "Aeqi"
    persona: str = "Aeqi"
    consent_required: bool = True
    consent_text: str = "Contract excerpts are processed by the configured AI provider strictly to answer your questions. No contract data is used for model training."
    consent_notice: str = "Contract excerpts are processed by the configured AI provider strictly to answer your questions. No contract data is used for model training."
    disclaimer: str = "Aeqi provides automated contract analysis for informational purposes only and does not provide legal advice."


class AskSuggestion(BaseModel):
    id: str
    question: str
    category: str  # key_terms | risks | obligations | general
    target_clause_id: str | None = None


class AskSuggestionsResponse(BaseModel):
    document_id: uuid.UUID
    suggestions: list[AskSuggestion]


class Citation(BaseModel):
    chunk_id: str
    clause_id: str
    heading: str | None = None
    page: int
    text_snippet: str


class AskRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000, description="User question about the contract")
    conversation_id: uuid.UUID | None = Field(default=None, description="Optional existing conversation UUID")
    stream: bool = Field(default=True, description="Whether to stream response via Server-Sent Events")


class AskAnswerResponse(BaseModel):
    conversation_id: uuid.UUID
    message_id: uuid.UUID
    question: str
    answer: str
    citations: list[Citation]
    status: str = Field(description="'answered' | 'insufficient_evidence' | 'retrieve_only'")
    token_count: int | None = None
    latency_ms: int | None = None
    hidden_text_excluded: bool = False
    verification_kind: str = Field(default="answered", description="'answered' | 'abstention'")


class MessageItem(BaseModel):
    id: uuid.UUID
    role: str  # user | assistant
    content: str
    citations: list[Citation] | None = None
    token_count: int | None = None
    latency_ms: int | None = None
    created_at: str


class ConversationListItem(BaseModel):
    id: uuid.UUID
    document_id: uuid.UUID
    title: str | None = None
    message_count: int = 0
    created_at: str
    updated_at: str


class ConversationDetailResponse(BaseModel):
    id: uuid.UUID
    document_id: uuid.UUID
    title: str | None = None
    created_at: str
    updated_at: str
    messages: list[MessageItem]
