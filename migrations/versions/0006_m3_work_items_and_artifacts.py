"""m3 work items and artifacts

Revision ID: 0006
Revises: 0005
Create Date: 2026-10-09 22:05:55.340142

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0006"
down_revision: str | Sequence[str] | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "work_items",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("run_id", sa.String(length=32), nullable=False),
        sa.Column("engine_key", sa.String(length=64), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("acceptance_criteria_json", sa.JSON(), nullable=False),
        sa.Column(
            "state",
            sa.Enum(
                "PENDING",
                "ACTIVE",
                "COMPLETED",
                "BLOCKED",
                "SKIPPED",
                "UNKNOWN",
                name="work_item_state",
                native_enum=False,
                create_constraint=True,
                length=32,
            ),
            nullable=False,
        ),
        sa.Column("blocker", sa.Text(), nullable=True),
        sa.Column("related_commit", sa.String(length=64), nullable=True),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["run_id"], ["runs.id"], name=op.f("fk_work_items_run_id_runs")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_work_items")),
        sa.UniqueConstraint(
            "run_id", "engine_key", name=op.f("uq_work_items_run_id_engine_key")
        ),
        sa.UniqueConstraint(
            "run_id", "ordinal", name=op.f("uq_work_items_run_id_ordinal")
        ),
    )
    op.create_table(
        "artifacts",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("project_id", sa.String(length=32), nullable=False),
        sa.Column("run_id", sa.String(length=32), nullable=True),
        sa.Column("attempt_id", sa.String(length=32), nullable=True),
        sa.Column(
            "artifact_class",
            sa.Enum(
                "INTENT",
                "INTERVIEW_TRANSCRIPT",
                "SPECIFICATION",
                "PLAN",
                "SOURCE_EXPORT",
                "TEST_EVIDENCE",
                "VERIFICATION_EVIDENCE",
                "ENGINE_CHECKPOINT",
                "CONSULTATION",
                "REVIEW",
                "KNOWLEDGE",
                "LEARNING",
                "RECOVERY",
                "RUNTIME_LOG",
                "ENGINE_LOG",
                "OTHER",
                name="artifact_class",
                native_enum=False,
                create_constraint=True,
                length=32,
            ),
            nullable=False,
        ),
        sa.Column("display_name", sa.String(length=255), nullable=False),
        sa.Column("media_type", sa.String(length=128), nullable=True),
        sa.Column("size_bytes", sa.Integer(), nullable=True),
        sa.Column("content_hash", sa.String(length=128), nullable=True),
        sa.Column(
            "storage_kind",
            sa.Enum(
                "WORKSPACE_REFERENCE",
                "RUN_ENGINE_RUNTIME_REFERENCE",
                "LOG_REFERENCE",
                "OBJECT_REFERENCE",
                "GENERATED_EXPORT",
                name="artifact_storage_kind",
                native_enum=False,
                create_constraint=True,
                length=32,
            ),
            nullable=False,
        ),
        sa.Column("storage_key", sa.String(length=512), nullable=False),
        sa.Column("source_identity_json", sa.JSON(), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["attempt_id"],
            ["execution_attempts.id"],
            name=op.f("fk_artifacts_attempt_id_execution_attempts"),
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name=op.f("fk_artifacts_project_id_projects"),
        ),
        sa.ForeignKeyConstraint(
            ["run_id"], ["runs.id"], name=op.f("fk_artifacts_run_id_runs")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_artifacts")),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("artifacts")
    op.drop_table("work_items")
