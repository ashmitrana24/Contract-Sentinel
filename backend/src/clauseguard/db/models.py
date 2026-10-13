"""SQLAlchemy ORM models for ClauseGuard.

Uses SQLAlchemy 2.0 mapped_column / Mapped style throughout.
UUID primary keys, JSONB columns via psycopg native driver.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from clauseguard.db.base import Base


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    sha256: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    original_filename: Mapped[str] = mapped_column(String(1024), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    storage_key: Mapped[str] = mapped_column(String(256), nullable=False)
    page_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    pdf_metadata: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    needs_ocr: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    jobs: Mapped[list[Job]] = relationship(
        "Job", back_populates="document", cascade="all, delete-orphan", passive_deletes=True, lazy="select"
    )
    pages: Mapped[list[Page]] = relationship(
        "Page", back_populates="document", cascade="all, delete-orphan", passive_deletes=True, lazy="select"
    )
    clauses: Mapped[list[Clause]] = relationship(
        "Clause", back_populates="document", cascade="all, delete-orphan", passive_deletes=True, lazy="select"
    )
    findings: Mapped[list[FindingRow]] = relationship(
        "FindingRow", back_populates="document", cascade="all, delete-orphan", passive_deletes=True, lazy="select"
    )
    analysis_runs: Mapped[list[AnalysisRun]] = relationship(
        "AnalysisRun", back_populates="document", cascade="all, delete-orphan", passive_deletes=True, lazy="select"
    )
    clause_labels: Mapped[list[ClauseLabelRow]] = relationship(
        "ClauseLabelRow", back_populates="document", cascade="all, delete-orphan", passive_deletes=True, lazy="select"
    )
    attributes: Mapped[DocumentAttributeRow | None] = relationship(
        "DocumentAttributeRow", back_populates="document", uselist=False, cascade="all, delete-orphan", passive_deletes=True, lazy="select"
    )
    risk_summary: Mapped[RiskSummaryRow | None] = relationship(
        "RiskSummaryRow", back_populates="document", uselist=False, cascade="all, delete-orphan", passive_deletes=True, lazy="select"
    )


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="queued"
    )  # queued|processing|retry_wait|succeeded|dead
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_kind: Mapped[str | None] = mapped_column(
        String(32), nullable=True
    )  # permanent|transient_exhausted
    next_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    enqueued_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    lease_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    document: Mapped[Document] = relationship("Document", back_populates="jobs")

    __table_args__ = (
        Index("ix_jobs_status_next", "status", "next_attempt_at"),
        Index("ix_jobs_document_id", "document_id"),
    )


class Page(Base):
    __tablename__ = "pages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    page_no: Mapped[int] = mapped_column(Integer, nullable=False)
    width: Mapped[float] = mapped_column(nullable=False)
    height: Mapped[float] = mapped_column(nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    char_count: Mapped[int] = mapped_column(Integer, nullable=False)
    spans: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)

    document: Mapped[Document] = relationship("Document", back_populates="pages")

    __table_args__ = (
        UniqueConstraint("document_id", "page_no", name="uq_pages_doc_pageno"),
        Index("ix_pages_document_id", "document_id"),
    )


class Clause(Base):
    __tablename__ = "clauses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    order_idx: Mapped[int] = mapped_column(Integer, nullable=False)
    clause_id: Mapped[str] = mapped_column(String(64), nullable=False)
    heading: Mapped[str] = mapped_column(String(512), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    level: Mapped[int] = mapped_column(Integer, nullable=False)
    parent_clause_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    page_start: Mapped[int] = mapped_column(Integer, nullable=False)
    page_end: Mapped[int] = mapped_column(Integer, nullable=False)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)  # preamble|clause|unsegmented

    document: Mapped[Document] = relationship("Document", back_populates="clauses")

    __table_args__ = (
        UniqueConstraint("document_id", "order_idx", name="uq_clauses_doc_order"),
        Index("ix_clauses_document_id", "document_id"),
    )


class FindingRow(Base):
    """One forensics finding stored in the database."""

    __tablename__ = "findings"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    module: Mapped[str] = mapped_column(String(64), nullable=False)
    type: Mapped[str] = mapped_column(String(64), nullable=False)
    severity: Mapped[str] = mapped_column(String(16), nullable=False)
    page: Mapped[int | None] = mapped_column(Integer, nullable=True)
    clause_ref: Mapped[str | None] = mapped_column(String(64), nullable=True)
    bbox: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    evidence: Mapped[str] = mapped_column(Text, nullable=False)
    explanation: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    details: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    document: Mapped[Document] = relationship("Document", back_populates="findings")
    feedback: Mapped[FindingFeedbackRow | None] = relationship(
        "FindingFeedbackRow",
        back_populates="finding",
        uselist=False,
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="select",
    )

    __table_args__ = (
        Index("ix_findings_document_id", "document_id"),
        Index("ix_findings_document_module", "document_id", "module"),
        Index("ix_findings_document_severity", "document_id", "severity"),
    )


class AnalysisRun(Base):
    """Record of one forensics analysis run for a document."""

    __tablename__ = "analysis_runs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    module: Mapped[str] = mapped_column(String(64), nullable=False)
    version: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)  # ok|partial|error
    duration_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    detector_status: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    document: Mapped[Document] = relationship("Document", back_populates="analysis_runs")

    __table_args__ = (
        UniqueConstraint("document_id", "module", "version", name="uq_analysis_runs_doc_mod_ver"),
        Index("ix_analysis_runs_document_id", "document_id"),
    )


class ClauseLabelRow(Base):
    """One multi-label classification tag assigned to a clause."""

    __tablename__ = "clause_labels"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    clause_id: Mapped[str] = mapped_column(String(64), nullable=False)
    label: Mapped[str] = mapped_column(String(64), nullable=False)
    score: Mapped[float] = mapped_column(Float, nullable=False)
    method: Mapped[str] = mapped_column(String(32), nullable=False)  # rules|model|both
    evidence: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    document: Mapped[Document] = relationship("Document", back_populates="clause_labels")

    __table_args__ = (
        Index("ix_clause_labels_doc_clause", "document_id", "clause_id"),
        Index("ix_clause_labels_doc_label", "document_id", "label"),
    )


class DocumentAttributeRow(Base):
    """Document-level structured key-term attributes."""

    __tablename__ = "document_attributes"

    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), primary_key=True
    )
    governing_law_jurisdiction: Mapped[str | None] = mapped_column(String(128), nullable=True)
    termination_notice_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    auto_renews: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    renewal_term_months: Mapped[int | None] = mapped_column(Integer, nullable=True)
    non_renewal_notice_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    liability_cap: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    non_compete_duration_months: Mapped[int | None] = mapped_column(Integer, nullable=True)
    payment_terms_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    document: Mapped[Document] = relationship("Document", back_populates="attributes")


class RiskSummaryRow(Base):
    """Document-level aggregated risk summary."""

    __tablename__ = "risk_summaries"

    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), primary_key=True
    )
    score: Mapped[int] = mapped_column(Integer, nullable=False)
    band: Mapped[str] = mapped_column(String(16), nullable=False)
    summary: Mapped[dict] = mapped_column(JSONB, nullable=False)
    version: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    document: Mapped[Document] = relationship("Document", back_populates="risk_summary")


class FindingFeedbackRow(Base):
    """User verification feedback on an individual finding."""

    __tablename__ = "finding_feedback"

    finding_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("findings.id", ondelete="CASCADE"), primary_key=True
    )
    verdict: Mapped[str] = mapped_column(String(32), nullable=False)  # confirmed|dismissed
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    finding: Mapped[FindingRow] = relationship("FindingRow", back_populates="feedback")
