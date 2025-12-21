"""Add admin flag to contributors.

Revision ID: 0002_add_admin_fields
Revises: 0001_init_platform
Create Date: 2025-12-20
"""
from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0002_add_admin_fields"
down_revision = "0001_init_platform"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("contributors", sa.Column("is_admin", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.alter_column("contributors", "is_admin", server_default=None)


def downgrade() -> None:
    op.drop_column("contributors", "is_admin")
