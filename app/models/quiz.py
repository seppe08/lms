from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
    true,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.mixins import TimestampMixin

if TYPE_CHECKING:
    from app.models.course import Module
    from app.models.user import User


class Quiz(TimestampMixin, Base):
    __tablename__ = "quizzes"
    __table_args__ = (
        CheckConstraint("passing_score >= 0 AND passing_score <= 100", name="passing_score_valid"),
        CheckConstraint("position >= 1", name="quiz_position_positive"),
        CheckConstraint("max_attempts IS NULL OR max_attempts >= 1", name="max_attempts_valid"),
        Index("ix_quizzes_module_id_position", "module_id", "position"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    module_id: Mapped[int] = mapped_column(
        ForeignKey("modules.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    passing_score: Mapped[int] = mapped_column(
        Integer, default=70, server_default="70", nullable=False
    )
    max_attempts: Mapped[int | None] = mapped_column(Integer, nullable=True)
    position: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    is_published: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default=true(), nullable=False
    )

    module: Mapped["Module"] = relationship(back_populates="quizzes")
    questions: Mapped[list["QuizQuestion"]] = relationship(
        back_populates="quiz",
        order_by="QuizQuestion.position",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    submissions: Mapped[list["QuizSubmission"]] = relationship(
        back_populates="quiz",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class QuizQuestion(TimestampMixin, Base):
    __tablename__ = "quiz_questions"
    __table_args__ = (
        CheckConstraint("points >= 1", name="points_positive"),
        CheckConstraint("position >= 1", name="question_position_positive"),
        CheckConstraint(
            "question_type IN ('multiple_choice', 'multi_select', 'true_false')",
            name="question_type_valid",
        ),
        Index("ix_quiz_questions_quiz_id_position", "quiz_id", "position"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    quiz_id: Mapped[int] = mapped_column(
        ForeignKey("quizzes.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    question_text: Mapped[str] = mapped_column(Text, nullable=False)
    question_type: Mapped[str] = mapped_column(
        String(20),
        default="multiple_choice",
        server_default="multiple_choice",
        nullable=False,
    )
    points: Mapped[int] = mapped_column(Integer, default=1, server_default="1", nullable=False)
    position: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    explanation: Mapped[str | None] = mapped_column(Text, nullable=True)

    quiz: Mapped["Quiz"] = relationship(back_populates="questions")
    options: Mapped[list["QuestionOption"]] = relationship(
        back_populates="question",
        order_by="QuestionOption.position",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    answers: Mapped[list["QuizAnswer"]] = relationship(
        back_populates="question",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class QuestionOption(Base):
    __tablename__ = "quiz_question_options"
    __table_args__ = (
        CheckConstraint("position >= 1", name="option_position_positive"),
        Index("ix_question_options_question_id_position", "question_id", "position"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    question_id: Mapped[int] = mapped_column(
        ForeignKey("quiz_questions.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    option_text: Mapped[str] = mapped_column(String(500), nullable=False)
    is_correct: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    position: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    question: Mapped["QuizQuestion"] = relationship(back_populates="options")


class QuizSubmission(Base):
    __tablename__ = "quiz_submissions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    quiz_id: Mapped[int] = mapped_column(
        ForeignKey("quizzes.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    score: Mapped[float] = mapped_column(Float, nullable=False)  # Percentage (e.g. 80.0)
    points_scored: Mapped[int] = mapped_column(Integer, nullable=False)
    total_points: Mapped[int] = mapped_column(Integer, nullable=False)
    passed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    attempt_number: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    submitted_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        nullable=False,
    )

    quiz: Mapped["Quiz"] = relationship(back_populates="submissions")
    user: Mapped["User"] = relationship(back_populates="quiz_submissions")
    answers: Mapped[list["QuizAnswer"]] = relationship(
        back_populates="submission",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class QuizAnswer(Base):
    __tablename__ = "quiz_answers"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    submission_id: Mapped[int] = mapped_column(
        ForeignKey("quiz_submissions.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    question_id: Mapped[int] = mapped_column(
        ForeignKey("quiz_questions.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    selected_option_ids: Mapped[list[int]] = mapped_column(JSON, default=list, nullable=False)
    is_correct: Mapped[bool] = mapped_column(Boolean, nullable=False)
    points_awarded: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    submission: Mapped["QuizSubmission"] = relationship(back_populates="answers")
    question: Mapped["QuizQuestion"] = relationship(back_populates="answers")
