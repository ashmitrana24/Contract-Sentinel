"""Add findings and analysis_runs tables (Module 3: PDF Forensics).

Revision ID: 0002_forensics
Revises: 0001_initial
Create Date: 2026-10-04
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002_forensics"
down_revision: Union[str, None] = "0001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- findings ---
    op.create_table(
        "findings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "document_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("module", sa.String(64), nullable=False),
        sa.Column("type", sa.String(64), nullable=False),
        sa.Column("severity", sa.String(16), nullable=False),
        sa.Column("page", sa.Integer, nullable=True),
        sa.Column("clause_ref", sa.String(64), nullable=True),
        sa.Column("bbox", postgresql.JSONB, nullable=True),
        sa.Column("evidence", sa.Text, nullable=False),
        sa.Column("explanation", sa.Text, nullable=False),
        sa.Column("confidence", sa.Float, nullable=True),
        sa.Column("details", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_findings_document_id", "findings", ["document_id"])
    op.create_index("ix_findings_document_module", "findings", ["document_id", "module"])
    op.create_index("ix_findings_document_severity", "findings", ["document_id", "severity"])

    # --- analysis_runs ---
    op.create_table(
        "analysis_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "document_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("module", sa.String(64), nullable=False),
        sa.Column("version", sa.String(32), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("duration_ms", sa.Integer, nullable=False),
        sa.Column("error", sa.Text, nullable=True),
        sa.Column("detector_status", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("document_id", "module", "version", name="uq_analysis_runs_doc_mod_ver"),
    )
    op.create_index("ix_analysis_runs_document_id", "analysis_runs", ["document_id"])


def downgrade() -> None:
    op.drop_index("ix_analysis_runs_document_id", table_name="analysis_runs")
    op.drop_table("analysis_runs")
    op.drop_index("ix_findings_document_severity", table_name="findings")
    op.drop_index("ix_findings_document_module", table_name="findings")
    op.drop_index("ix_findings_document_id", table_name="findings")
    op.drop_table("findings")
