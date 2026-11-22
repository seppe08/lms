"""create courses modules and lessons tables

Revision ID: 3b9e5d2a7f02
Revises: 2a8f4c1d9e01
Create Date: 2026-11-18 22:36:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "3b9e5d2a7f02"
down_revision: str | Sequence[str] | None = "2a8f4c1d9e01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create courses, modules, and lessons tables."""
    op.create_table(
        "courses",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("slug", sa.String(length=220), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("instructor_id", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            sa.String(length=20),
            server_default="draft",
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('draft', 'published', 'archived')",
            name=op.f("ck_courses_status_valid"),
        ),
        sa.ForeignKeyConstraint(
            ["instructor_id"],
            ["users.id"],
            name=op.f("fk_courses_instructor_id"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_courses")),
    )
    op.create_index(op.f("ix_courses_slug"), "courses", ["slug"], unique=True)
    op.create_index(op.f("ix_courses_instructor_id"), "courses", ["instructor_id"], unique=False)
    op.create_index(op.f("ix_courses_status"), "courses", ["status"], unique=False)

    op.create_table(
        "modules",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("course_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint("position >= 1", name=op.f("ck_modules_position_positive")),
        sa.ForeignKeyConstraint(
            ["course_id"],
            ["courses.id"],
            name=op.f("fk_modules_course_id"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_modules")),
    )
    op.create_index(op.f("ix_modules_course_id"), "modules", ["course_id"], unique=False)
    op.create_index(
        "ix_modules_course_id_position",
        "modules",
        ["course_id", "position"],
        unique=False,
    )

    op.create_table(
        "lessons",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("module_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("content_type", sa.String(length=20), nullable=False),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("content_url", sa.String(length=1000), nullable=True),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("duration_minutes", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "content_type IN ('text', 'video', 'link')",
            name=op.f("ck_lessons_content_type_valid"),
        ),
        sa.CheckConstraint("position >= 1", name=op.f("ck_lessons_position_positive")),
        sa.CheckConstraint(
            "duration_minutes IS NULL OR duration_minutes >= 0",
            name=op.f("ck_lessons_duration_non_negative"),
        ),
        sa.ForeignKeyConstraint(
            ["module_id"],
            ["modules.id"],
            name=op.f("fk_lessons_module_id"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_lessons")),
    )
    op.create_index(op.f("ix_lessons_module_id"), "lessons", ["module_id"], unique=False)
    op.create_index(
        "ix_lessons_module_id_position",
        "lessons",
        ["module_id", "position"],
        unique=False,
    )


def downgrade() -> None:
    """Drop lessons, modules, and courses tables."""
    op.drop_index("ix_lessons_module_id_position", table_name="lessons")
    op.drop_index(op.f("ix_lessons_module_id"), table_name="lessons")
    op.drop_table("lessons")

    op.drop_index("ix_modules_course_id_position", table_name="modules")
    op.drop_index(op.f("ix_modules_course_id"), table_name="modules")
    op.drop_table("modules")

    op.drop_index(op.f("ix_courses_status"), table_name="courses")
    op.drop_index(op.f("ix_courses_instructor_id"), table_name="courses")
    op.drop_index(op.f("ix_courses_slug"), table_name="courses")
    op.drop_table("courses")
