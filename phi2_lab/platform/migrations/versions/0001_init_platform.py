"""init platform schema

Revision ID: 0001_init_platform
Revises: None
Create Date: 2025-12-19 00:00:00
"""
from alembic import op
import sqlalchemy as sa


revision = "0001_init_platform"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "contributors",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("username", sa.String(length=255), nullable=False, unique=True),
        sa.Column("api_key_hash", sa.String(length=64), nullable=False, unique=True),
        sa.Column("api_key_prefix", sa.String(length=16), nullable=False),
        sa.Column("email", sa.String(length=255)),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("runs_completed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("compute_donated_seconds", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("banned", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("banned_at", sa.DateTime()),
        sa.Column("ban_reason", sa.Text()),
    )

    op.create_table(
        "tasks",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("hypothesis", sa.Text()),
        sa.Column("spec_yaml", sa.Text(), nullable=False),
        sa.Column("spec_hash", sa.String(length=64), nullable=False),
        sa.Column("dataset_name", sa.String(length=255)),
        sa.Column("dataset_hash", sa.String(length=64)),
        sa.Column("created_by", sa.String(length=36), sa.ForeignKey("contributors.id")),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("status", sa.String(length=50), nullable=False, server_default="open"),
        sa.Column("runs_needed", sa.Integer(), nullable=False, server_default="50"),
        sa.Column("runs_completed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="0"),
    )

    op.create_table(
        "results",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("task_id", sa.String(length=36), sa.ForeignKey("tasks.id"), nullable=False),
        sa.Column("contributor_id", sa.String(length=36), sa.ForeignKey("contributors.id"), nullable=False),
        sa.Column("submitted_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("preset_used", sa.String(length=50)),
        sa.Column("hardware_info", sa.JSON()),
        sa.Column("duration_seconds", sa.Integer()),
        sa.Column("result_summary", sa.JSON()),
        sa.Column("result_full", sa.JSON()),
        sa.Column("telemetry_data", sa.JSON()),
        sa.Column("telemetry_run_id", sa.String(length=128)),
        sa.Column("spec_hash", sa.String(length=64)),
        sa.Column("is_valid", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("validation_notes", sa.Text()),
    )

    op.create_table(
        "findings",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("task_id", sa.String(length=36), sa.ForeignKey("tasks.id"), nullable=False),
        sa.Column("finding_type", sa.String(length=100), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("confidence", sa.Float()),
        sa.Column("supporting_runs", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("data", sa.JSON()),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "dataset_releases",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("slug", sa.String(length=64), nullable=False, unique=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("owner_id", sa.String(length=36), sa.ForeignKey("contributors.id"), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="draft"),
        sa.Column("visibility", sa.String(length=32), nullable=False, server_default="auth"),
        sa.Column("membership_mode", sa.String(length=32), nullable=False, server_default="static"),
        sa.Column("membership_query", sa.JSON()),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "dataset_release_runs",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("dataset_id", sa.String(length=36), sa.ForeignKey("dataset_releases.id"), nullable=False),
        sa.Column("result_id", sa.String(length=36), sa.ForeignKey("results.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("dataset_id", "result_id", name="uq_dataset_release_run"),
    )

    op.create_table(
        "dataset_verifications",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("dataset_id", sa.String(length=36), sa.ForeignKey("dataset_releases.id"), nullable=False),
        sa.Column("verifier_id", sa.String(length=36), sa.ForeignKey("contributors.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("dataset_id", "verifier_id", name="uq_dataset_verification"),
    )

    op.create_table(
        "dataset_flags",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("dataset_id", sa.String(length=36), sa.ForeignKey("dataset_releases.id"), nullable=False),
        sa.Column("flagger_id", sa.String(length=36), sa.ForeignKey("contributors.id"), nullable=False),
        sa.Column("result_id", sa.String(length=36), sa.ForeignKey("results.id"), nullable=False),
        sa.Column("spec_hash", sa.String(length=64), nullable=False),
        sa.Column("result_hash", sa.String(length=64), nullable=False),
        sa.Column("reason", sa.String(length=64), nullable=False),
        sa.Column("notes", sa.Text()),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("dataset_id", "flagger_id", "result_id", name="uq_dataset_flag"),
    )

    op.create_index("idx_results_task", "results", ["task_id"])
    op.create_index("idx_results_contributor", "results", ["contributor_id"])
    op.create_index("idx_tasks_status", "tasks", ["status"])


def downgrade() -> None:
    op.drop_index("idx_tasks_status", table_name="tasks")
    op.drop_index("idx_results_contributor", table_name="results")
    op.drop_index("idx_results_task", table_name="results")
    op.drop_table("dataset_flags")
    op.drop_table("dataset_verifications")
    op.drop_table("dataset_release_runs")
    op.drop_table("dataset_releases")
    op.drop_table("findings")
    op.drop_table("results")
    op.drop_table("tasks")
    op.drop_table("contributors")
