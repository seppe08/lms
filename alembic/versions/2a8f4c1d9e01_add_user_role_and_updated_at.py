"""add user role and updated_at

Revision ID: 2a8f4c1d9e01
Revises: bcb073ef043a
Create Date: 2026-11-18 22:35:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "2a8f4c1d9e01"
down_revision: str | Sequence[str] | None = "bcb073ef043a"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add role, updated_at, check constraint, and indexes to users table."""
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "role",
                sa.String(length=20),
                server_default="student",
                nullable=False,
            )
        )
        batch_op.add_column(
            sa.Column(
                "updated_at",
                sa.DateTime(),
                server_default=sa.text("CURRENT_TIMESTAMP"),
                nullable=False,
            )
        )
        batch_op.create_check_constraint(
            "ck_users_role_valid",
            "role IN ('student', 'instructor', 'admin')",
        )
        batch_op.create_index("ix_users_role", ["role"], unique=False)
        batch_op.create_index("ix_users_is_active", ["is_active"], unique=False)


def downgrade() -> None:
    """Remove role, updated_at, check constraint, and indexes from users table."""
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.drop_index("ix_users_is_active")
        batch_op.drop_index("ix_users_role")
        batch_op.drop_constraint("ck_users_role_valid", type_="check")
        batch_op.drop_column("updated_at")
        batch_op.drop_column("role")
