"""m3 run engine runtime

Revision ID: 0005
Revises: 0004
Create Date: 2026-10-09 21:50:57.780337

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0005"
down_revision: str | Sequence[str] | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "run_engine_runtimes",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("run_id", sa.String(length=32), nullable=False),
        sa.Column("storage_driver", sa.String(length=64), nullable=False),
        sa.Column("storage_key", sa.String(length=512), nullable=False),
        sa.Column(
            "state",
            sa.Enum(
                "INITIALIZING",
                "READY",
                "ERROR",
                name="engine_runtime_state",
                native_enum=False,
                create_constraint=True,
                length=32,
            ),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("validated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(
            ["run_id"],
            ["runs.id"],
            name=op.f("fk_run_engine_runtimes_run_id_runs"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_run_engine_runtimes")),
        sa.UniqueConstraint("run_id", name=op.f("uq_run_engine_runtimes_run_id")),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("run_engine_runtimes")
