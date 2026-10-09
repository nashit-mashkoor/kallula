"""m3 engine installation

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-09 21:37:57.241803

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0004"
down_revision: str | Sequence[str] | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "engine_installations",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("engine_family", sa.String(length=32), nullable=False),
        sa.Column("engine_revision", sa.String(length=64), nullable=False),
        sa.Column("adapter_version", sa.String(length=32), nullable=False),
        sa.Column("installation_digest", sa.String(length=128), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "CANDIDATE",
                "SUPPORTED",
                "DEPRECATED",
                "BLOCKED",
                name="engine_installation_status",
                native_enum=False,
                create_constraint=True,
                length=32,
            ),
            nullable=False,
        ),
        sa.Column("default_for_new_runs", sa.Boolean(), nullable=False),
        sa.Column(
            "compatibility_launch",
            sa.Enum(
                "SUPPORTED",
                "UNSUPPORTED",
                "UNKNOWN",
                name="compatibility_status_launch",
                native_enum=False,
                create_constraint=True,
                length=16,
            ),
            nullable=False,
        ),
        sa.Column(
            "compatibility_state_format",
            sa.Enum(
                "SUPPORTED",
                "UNSUPPORTED",
                "UNKNOWN",
                name="compatibility_status_state_format",
                native_enum=False,
                create_constraint=True,
                length=16,
            ),
            nullable=False,
        ),
        sa.Column(
            "compatibility_resume",
            sa.Enum(
                "SUPPORTED",
                "UNSUPPORTED",
                "UNKNOWN",
                name="compatibility_status_resume",
                native_enum=False,
                create_constraint=True,
                length=16,
            ),
            nullable=False,
        ),
        sa.Column(
            "compatibility_security",
            sa.Enum(
                "SUPPORTED",
                "UNSUPPORTED",
                "UNKNOWN",
                name="compatibility_status_security",
                native_enum=False,
                create_constraint=True,
                length=16,
            ),
            nullable=False,
        ),
        sa.Column(
            "compatibility_runtime",
            sa.Enum(
                "SUPPORTED",
                "UNSUPPORTED",
                "UNKNOWN",
                name="compatibility_status_runtime",
                native_enum=False,
                create_constraint=True,
                length=16,
            ),
            nullable=False,
        ),
        sa.Column("capability_manifest_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_engine_installations")),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("engine_installations")
