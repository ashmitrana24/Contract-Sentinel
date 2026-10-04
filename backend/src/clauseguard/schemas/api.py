"""API request / response schemas."""

from __future__ import annotations

import uuid

from pydantic import BaseModel, Field


class UploadResponse(BaseModel):
    document_id: uuid.UUID
    job_id: uuid.UUID
    deduplicated: bool = False


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


class FindingResponse(BaseModel):
    id: uuid.UUID
    document_id: uuid.UUID
    module: str
    type: str
    severity: str
    page: int | None
    clause_ref: str | None
    bbox: list[float] | None
    evidence: str
    explanation: str
    confidence: float | None
    details: dict
    created_at: str


class PaginatedFindings(BaseModel):
    total: int
    limit: int
    offset: int
    items: list[FindingResponse]


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
