"""Add points/bounty system fields.

Revision ID: 0003_add_points_bounty
Revises: 0002_add_admin_fields
Create Date: 2025-12-21
"""
from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0003_add_points_bounty"
down_revision = "0002_add_admin_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Contributor points fields
    op.add_column("contributors", sa.Column("points", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("contributors", sa.Column("level", sa.Integer(), nullable=False, server_default="1"))
    op.add_column("contributors", sa.Column("streak_days", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("contributors", sa.Column("last_contribution_at", sa.DateTime(), nullable=True))

    # Task bounty fields
    op.add_column("tasks", sa.Column("base_points", sa.Integer(), nullable=False, server_default="10"))
    op.add_column("tasks", sa.Column("bonus_points", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("tasks", sa.Column("bonus_reason", sa.Text(), nullable=True))

    # Point transactions table
    op.create_table(
        "point_transactions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("contributor_id", sa.String(36), sa.ForeignKey("contributors.id"), nullable=False),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column("balance_after", sa.Integer(), nullable=False),
        sa.Column("reason", sa.String(50), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("task_id", sa.String(36), sa.ForeignKey("tasks.id"), nullable=True),
        sa.Column("result_id", sa.String(36), sa.ForeignKey("results.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("created_by", sa.String(36), sa.ForeignKey("contributors.id"), nullable=True),
    )
    op.create_index("ix_point_transactions_contributor_id", "point_transactions", ["contributor_id"])
    op.create_index("ix_point_transactions_created_at", "point_transactions", ["created_at"])

    # Remove server defaults (they were only for existing rows)
    op.alter_column("contributors", "points", server_default=None)
    op.alter_column("contributors", "level", server_default=None)
    op.alter_column("contributors", "streak_days", server_default=None)
    op.alter_column("tasks", "base_points", server_default=None)
    op.alter_column("tasks", "bonus_points", server_default=None)


def downgrade() -> None:
    op.drop_index("ix_point_transactions_created_at", "point_transactions")
    op.drop_index("ix_point_transactions_contributor_id", "point_transactions")
    op.drop_table("point_transactions")

    op.drop_column("tasks", "bonus_reason")
    op.drop_column("tasks", "bonus_points")
    op.drop_column("tasks", "base_points")

    op.drop_column("contributors", "last_contribution_at")
    op.drop_column("contributors", "streak_days")
    op.drop_column("contributors", "level")
    op.drop_column("contributors", "points")
