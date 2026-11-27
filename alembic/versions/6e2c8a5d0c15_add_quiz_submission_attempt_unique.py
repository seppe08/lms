"""add unique constraint on quiz submission attempts

Revision ID: 6e2c8a5d0c15
Revises: 5d1b7f4c9b04
Create Date: 2026-11-27 18:50:00.000000

"""

from collections.abc import Sequence

from alembic import op

revision: str = "6e2c8a5d0c15"
down_revision: str | Sequence[str] | None = "5d1b7f4c9b04"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("quiz_submissions") as batch_op:
        batch_op.create_unique_constraint(
            op.f("uq_quiz_submissions_attempt"),
            ["quiz_id", "user_id", "attempt_number"],
        )


def downgrade() -> None:
    with op.batch_alter_table("quiz_submissions") as batch_op:
        batch_op.drop_constraint(
            op.f("uq_quiz_submissions_attempt"),
            type_="unique",
        )
