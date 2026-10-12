"""m4 pending interactions

Revision ID: 0007
Revises: 0006
Create Date: 2026-10-12 18:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0007"
down_revision: str | Sequence[str] | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "pending_interactions",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("run_id", sa.String(length=32), nullable=False),
        sa.Column("attempt_id", sa.String(length=32), nullable=True),
        sa.Column(
            "kind",
            sa.Enum(
                "QUESTION",
                "FINAL_INTENT_CONFIRMATION",
                name="interaction_kind",
                native_enum=False,
                create_constraint=True,
                length=32,
            ),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum(
                "OPEN",
                "ANSWERED",
                "DELEGATED",
                "CANCELED",
                "SUPERSEDED",
                name="interaction_state",
                native_enum=False,
                create_constraint=True,
                length=32,
            ),
            nullable=False,
        ),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("prompt", sa.Text(), nullable=False),
        sa.Column("recommendation", sa.Text(), nullable=True),
        sa.Column("context_json", sa.JSON(), nullable=False),
        sa.Column("allowed_responses_json", sa.JSON(), nullable=False),
        sa.Column("engine_interaction_token", sa.String(length=128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["run_id"], ["runs.id"], name=op.f("fk_pending_interactions_run_id_runs")
        ),
        sa.ForeignKeyConstraint(
            ["attempt_id"],
            ["execution_attempts.id"],
            name=op.f("fk_pending_interactions_attempt_id_execution_attempts"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_pending_interactions")),
    )
    op.create_index(
        "uq_pending_interactions_open_run",
        "pending_interactions",
        ["run_id"],
        unique=True,
        sqlite_where=sa.text("status = 'OPEN'"),
        postgresql_where=sa.text("status = 'OPEN'"),
    )
    op.create_table(
        "interaction_responses",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("interaction_id", sa.String(length=32), nullable=False),
        sa.Column("run_id", sa.String(length=32), nullable=False),
        sa.Column("actor_principal_id", sa.String(length=32), nullable=False),
        sa.Column(
            "response_type",
            sa.Enum(
                "ANSWER",
                "USE_RECOMMENDATION",
                "CONFIRM",
                "REQUEST_CHANGE",
                "DELEGATE_REMAINING",
                name="interaction_response_type",
                native_enum=False,
                create_constraint=True,
                length=32,
            ),
            nullable=False,
        ),
        sa.Column("answer_text", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("command_id", sa.String(length=32), nullable=True),
        sa.ForeignKeyConstraint(
            ["interaction_id"],
            ["pending_interactions.id"],
            name=op.f("fk_interaction_responses_interaction_id_pending_interactions"),
        ),
        sa.ForeignKeyConstraint(
            ["run_id"], ["runs.id"], name=op.f("fk_interaction_responses_run_id_runs")
        ),
        sa.ForeignKeyConstraint(
            ["actor_principal_id"],
            ["principals.id"],
            name=op.f("fk_interaction_responses_actor_principal_id_principals"),
        ),
        sa.ForeignKeyConstraint(
            ["command_id"],
            ["commands.id"],
            name=op.f("fk_interaction_responses_command_id_commands"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_interaction_responses")),
        sa.UniqueConstraint(
            "interaction_id",
            name=op.f("uq_interaction_responses_interaction_id"),
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("interaction_responses")
    op.drop_index("uq_pending_interactions_open_run", table_name="pending_interactions")
    op.drop_table("pending_interactions")
