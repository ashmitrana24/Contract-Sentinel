"""Add clause_labels and document_attributes tables (Module 5: Clause Classification).

Revision ID: 0003_clause_labels_and_attributes
Revises: 0002_forensics
Create Date: 2026-10-13
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0003_clauses"
down_revision: str | None = "0002_forensics"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # --- clause_labels ---
    op.create_table(
        "clause_labels",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "document_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("clause_id", sa.String(64), nullable=False),
        sa.Column("label", sa.String(64), nullable=False),
        sa.Column("score", sa.Float, nullable=False),
        sa.Column("method", sa.String(32), nullable=False),
        sa.Column("evidence", sa.Text, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_clause_labels_doc_clause",
        "clause_labels",
        ["document_id", "clause_id"],
    )
    op.create_index(
        "ix_clause_labels_doc_label",
        "clause_labels",
        ["document_id", "label"],
    )

    # --- document_attributes ---
    op.create_table(
        "document_attributes",
        sa.Column(
            "document_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("documents.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("governing_law_jurisdiction", sa.String(128), nullable=True),
        sa.Column("termination_notice_days", sa.Integer, nullable=True),
        sa.Column("auto_renews", sa.Boolean, nullable=True),
        sa.Column("renewal_term_months", sa.Integer, nullable=True),
        sa.Column("non_renewal_notice_days", sa.Integer, nullable=True),
        sa.Column("liability_cap", postgresql.JSONB, nullable=True),
        sa.Column("non_compete_duration_months", sa.Integer, nullable=True),
        sa.Column("payment_terms_days", sa.Integer, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_table("document_attributes")
    op.drop_index("ix_clause_labels_doc_label", table_name="clause_labels")
    op.drop_index("ix_clause_labels_doc_clause", table_name="clause_labels")
    op.drop_table("clause_labels")
