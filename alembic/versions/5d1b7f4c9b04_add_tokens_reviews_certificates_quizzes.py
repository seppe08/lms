"""add revoked_tokens, reviews, certificates, and quizzes tables

Revision ID: 5d1b7f4c9b04
Revises: 4c0a6e3b8a03
Create Date: 2026-11-23 23:35:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "5d1b7f4c9b04"
down_revision: str | Sequence[str] | None = "4c0a6e3b8a03"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. revoked_tokens
    op.create_table(
        "revoked_tokens",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("jti", sa.String(length=64), nullable=False),
        sa.Column("token_type", sa.String(length=20), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_revoked_tokens_user_id"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_revoked_tokens")),
    )
    op.create_index(op.f("ix_revoked_tokens_jti"), "revoked_tokens", ["jti"], unique=True)
    op.create_index(op.f("ix_revoked_tokens_user_id"), "revoked_tokens", ["user_id"])
    op.create_index(op.f("ix_revoked_tokens_expires_at"), "revoked_tokens", ["expires_at"])

    # 2. reviews
    op.create_table(
        "reviews",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("course_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("rating", sa.Integer(), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
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
        sa.CheckConstraint("rating >= 1 AND rating <= 5", name=op.f("ck_reviews_rating_range")),
        sa.ForeignKeyConstraint(
            ["course_id"],
            ["courses.id"],
            name=op.f("fk_reviews_course_id"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_reviews_user_id"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_reviews")),
        sa.UniqueConstraint("user_id", "course_id", name=op.f("uq_reviews_user_course")),
    )
    op.create_index(op.f("ix_reviews_course_id"), "reviews", ["course_id"])
    op.create_index(op.f("ix_reviews_user_id"), "reviews", ["user_id"])

    # 3. certificates
    op.create_table(
        "certificates",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("certificate_code", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("course_id", sa.Integer(), nullable=False),
        sa.Column(
            "issued_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["course_id"],
            ["courses.id"],
            name=op.f("fk_certificates_course_id"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_certificates_user_id"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_certificates")),
        sa.UniqueConstraint("user_id", "course_id", name=op.f("uq_certificates_user_course")),
    )
    op.create_index(
        op.f("ix_certificates_certificate_code"),
        "certificates",
        ["certificate_code"],
        unique=True,
    )
    op.create_index(op.f("ix_certificates_user_id"), "certificates", ["user_id"])
    op.create_index(op.f("ix_certificates_course_id"), "certificates", ["course_id"])

    # 4. quizzes
    op.create_table(
        "quizzes",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("module_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("passing_score", sa.Integer(), server_default="70", nullable=False),
        sa.Column("max_attempts", sa.Integer(), nullable=True),
        sa.Column("position", sa.Integer(), server_default="1", nullable=False),
        sa.Column("is_published", sa.Boolean(), server_default=sa.text("true"), nullable=False),
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
            "passing_score >= 0 AND passing_score <= 100",
            name=op.f("ck_quizzes_passing_score_valid"),
        ),
        sa.CheckConstraint("position >= 1", name=op.f("ck_quizzes_position_positive")),
        sa.CheckConstraint(
            "max_attempts IS NULL OR max_attempts >= 1",
            name=op.f("ck_quizzes_max_attempts_valid"),
        ),
        sa.ForeignKeyConstraint(
            ["module_id"],
            ["modules.id"],
            name=op.f("fk_quizzes_module_id"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_quizzes")),
    )
    op.create_index(op.f("ix_quizzes_module_id"), "quizzes", ["module_id"])
    op.create_index(
        "ix_quizzes_module_id_position",
        "quizzes",
        ["module_id", "position"],
    )

    # 5. quiz_questions
    op.create_table(
        "quiz_questions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("quiz_id", sa.Integer(), nullable=False),
        sa.Column("question_text", sa.Text(), nullable=False),
        sa.Column(
            "question_type",
            sa.String(length=20),
            server_default="multiple_choice",
            nullable=False,
        ),
        sa.Column("points", sa.Integer(), server_default="1", nullable=False),
        sa.Column("position", sa.Integer(), server_default="1", nullable=False),
        sa.Column("explanation", sa.Text(), nullable=True),
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
        sa.CheckConstraint("points >= 1", name=op.f("ck_quiz_questions_points_positive")),
        sa.CheckConstraint("position >= 1", name=op.f("ck_quiz_questions_position_positive")),
        sa.CheckConstraint(
            "question_type IN ('multiple_choice', 'multi_select', 'true_false')",
            name=op.f("ck_quiz_questions_question_type_valid"),
        ),
        sa.ForeignKeyConstraint(
            ["quiz_id"],
            ["quizzes.id"],
            name=op.f("fk_quiz_questions_quiz_id"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_quiz_questions")),
    )
    op.create_index(op.f("ix_quiz_questions_quiz_id"), "quiz_questions", ["quiz_id"])
    op.create_index(
        "ix_quiz_questions_quiz_id_position",
        "quiz_questions",
        ["quiz_id", "position"],
    )

    # 6. quiz_question_options
    op.create_table(
        "quiz_question_options",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("question_id", sa.Integer(), nullable=False),
        sa.Column("option_text", sa.String(length=500), nullable=False),
        sa.Column("is_correct", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("position", sa.Integer(), server_default="1", nullable=False),
        sa.CheckConstraint(
            "position >= 1",
            name=op.f("ck_quiz_question_options_position_positive"),
        ),
        sa.ForeignKeyConstraint(
            ["question_id"],
            ["quiz_questions.id"],
            name=op.f("fk_quiz_question_options_question_id"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_quiz_question_options")),
    )
    op.create_index(
        op.f("ix_quiz_question_options_question_id"),
        "quiz_question_options",
        ["question_id"],
    )
    op.create_index(
        "ix_quiz_question_options_question_id_position",
        "quiz_question_options",
        ["question_id", "position"],
    )

    # 7. quiz_submissions
    op.create_table(
        "quiz_submissions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("quiz_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("points_scored", sa.Integer(), nullable=False),
        sa.Column("total_points", sa.Integer(), nullable=False),
        sa.Column("passed", sa.Boolean(), nullable=False),
        sa.Column("attempt_number", sa.Integer(), server_default="1", nullable=False),
        sa.Column(
            "submitted_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["quiz_id"],
            ["quizzes.id"],
            name=op.f("fk_quiz_submissions_quiz_id"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_quiz_submissions_user_id"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_quiz_submissions")),
    )
    op.create_index(op.f("ix_quiz_submissions_quiz_id"), "quiz_submissions", ["quiz_id"])
    op.create_index(op.f("ix_quiz_submissions_user_id"), "quiz_submissions", ["user_id"])

    # 8. quiz_answers
    op.create_table(
        "quiz_answers",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("submission_id", sa.Integer(), nullable=False),
        sa.Column("question_id", sa.Integer(), nullable=False),
        sa.Column("selected_option_ids", sa.JSON(), nullable=False),
        sa.Column("is_correct", sa.Boolean(), nullable=False),
        sa.Column("points_awarded", sa.Integer(), server_default="0", nullable=False),
        sa.ForeignKeyConstraint(
            ["question_id"],
            ["quiz_questions.id"],
            name=op.f("fk_quiz_answers_question_id"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["submission_id"],
            ["quiz_submissions.id"],
            name=op.f("fk_quiz_answers_submission_id"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_quiz_answers")),
    )
    op.create_index(op.f("ix_quiz_answers_submission_id"), "quiz_answers", ["submission_id"])
    op.create_index(op.f("ix_quiz_answers_question_id"), "quiz_answers", ["question_id"])


def downgrade() -> None:
    op.drop_table("quiz_answers")
    op.drop_table("quiz_submissions")
    op.drop_table("quiz_question_options")
    op.drop_table("quiz_questions")
    op.drop_table("quizzes")
    op.drop_table("certificates")
    op.drop_table("reviews")
    op.drop_table("revoked_tokens")
