"""Add risk_summaries and finding_feedback tables (Module 8: Risk Summary).

Revision ID: 0004_risk_summary
Revises: 0003_clauses
Create Date: 2026-10-13
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0004_risk_summary"
down_revision: str | None = "0003_clauses"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # --- risk_summaries ---
    op.create_table(
        "risk_summaries",
        sa.Column(
            "document_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("documents.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("score", sa.Integer, nullable=False),
        sa.Column("band", sa.String(16), nullable=False),
        sa.Column("summary", postgresql.JSONB, nullable=False),
        sa.Column("version", sa.String(32), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_risk_summaries_band",
        "risk_summaries",
        ["band"],
    )

    # --- finding_feedback ---
    op.create_table(
        "finding_feedback",
        sa.Column(
            "finding_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("findings.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("verdict", sa.String(32), nullable=False),  # confirmed | dismissed
        sa.Column("note", sa.Text, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_table("finding_feedback")
    op.drop_index("ix_risk_summaries_band", table_name="risk_summaries")
    op.drop_table("risk_summaries")
