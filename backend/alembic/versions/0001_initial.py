"""Initial schema: documents, jobs, pages, clauses.

Revision ID: 0001_initial
Revises:
Create Date: 2026-10-03
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0001_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # --- documents ---
    op.create_table(
        "documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("original_filename", sa.String(1024), nullable=False),
        sa.Column("size_bytes", sa.Integer, nullable=False),
        sa.Column("storage_key", sa.String(256), nullable=False),
        sa.Column("page_count", sa.Integer, nullable=True),
        sa.Column("pdf_metadata", postgresql.JSONB, nullable=True),
        sa.Column("needs_ocr", sa.Boolean, nullable=False, server_default="false"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_documents_sha256", "documents", ["sha256"], unique=True)

    # --- jobs ---
    op.create_table(
        "jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "document_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("status", sa.String(32), nullable=False, server_default="queued"),
        sa.Column("attempts", sa.Integer, nullable=False, server_default="0"),
        sa.Column("max_attempts", sa.Integer, nullable=False, server_default="5"),
        sa.Column("last_error", sa.Text, nullable=True),
        sa.Column("error_kind", sa.String(32), nullable=True),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("enqueued_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_jobs_document_id", "jobs", ["document_id"])
    op.create_index("ix_jobs_status_next", "jobs", ["status", "next_attempt_at"])

    # --- pages ---
    op.create_table(
        "pages",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "document_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("page_no", sa.Integer, nullable=False),
        sa.Column("width", sa.Float, nullable=False),
        sa.Column("height", sa.Float, nullable=False),
        sa.Column("text", sa.Text, nullable=False),
        sa.Column("char_count", sa.Integer, nullable=False),
        sa.Column("spans", postgresql.JSONB, nullable=False, server_default="[]"),
        sa.UniqueConstraint("document_id", "page_no", name="uq_pages_doc_pageno"),
    )
    op.create_index("ix_pages_document_id", "pages", ["document_id"])

    # --- clauses ---
    op.create_table(
        "clauses",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "document_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("order_idx", sa.Integer, nullable=False),
        sa.Column("clause_id", sa.String(64), nullable=False),
        sa.Column("heading", sa.String(512), nullable=False),
        sa.Column("text", sa.Text, nullable=False),
        sa.Column("level", sa.Integer, nullable=False),
        sa.Column("parent_clause_id", sa.String(64), nullable=True),
        sa.Column("page_start", sa.Integer, nullable=False),
        sa.Column("page_end", sa.Integer, nullable=False),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.UniqueConstraint("document_id", "order_idx", name="uq_clauses_doc_order"),
    )
    op.create_index("ix_clauses_document_id", "clauses", ["document_id"])


def downgrade() -> None:
    op.drop_table("clauses")
    op.drop_table("pages")
    op.drop_table("jobs")
    op.drop_table("documents")
