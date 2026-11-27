from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


# --- Options ---
class QuestionOptionCreate(BaseModel):
    option_text: str = Field(min_length=1, max_length=500)
    is_correct: bool = Field(default=False)
    position: int = Field(default=1, ge=1)


class QuestionOptionUpdate(BaseModel):
    option_text: str | None = Field(default=None, min_length=1, max_length=500)
    is_correct: bool | None = None
    position: int | None = Field(default=None, ge=1)


class QuestionOptionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    option_text: str
    is_correct: bool
    position: int


class QuestionOptionStudentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    option_text: str
    position: int


# --- Questions ---
class QuizQuestionCreate(BaseModel):
    question_text: str = Field(min_length=1)
    question_type: Literal["multiple_choice", "multi_select", "true_false"] = "multiple_choice"
    points: int = Field(default=1, ge=1)
    position: int = Field(default=1, ge=1)
    explanation: str | None = None
    options: list[QuestionOptionCreate] = Field(default_factory=list)


class QuizQuestionUpdate(BaseModel):
    question_text: str | None = Field(default=None, min_length=1)
    question_type: Literal["multiple_choice", "multi_select", "true_false"] | None = None
    points: int | None = Field(default=None, ge=1)
    position: int | None = Field(default=None, ge=1)
    explanation: str | None = None


class QuizQuestionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    quiz_id: int
    question_text: str
    question_type: str
    points: int
    position: int
    explanation: str | None
    options: list[QuestionOptionRead] = Field(default_factory=list)


class QuizQuestionStudentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    quiz_id: int
    question_text: str
    question_type: str
    points: int
    position: int
    options: list[QuestionOptionStudentRead] = Field(default_factory=list)


# --- Quizzes ---
class QuizCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str | None = None
    passing_score: int = Field(default=70, ge=0, le=100)
    max_attempts: int | None = Field(default=None, ge=1)
    position: int = Field(default=1, ge=1)
    is_published: bool = Field(default=True)


class QuizUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
    passing_score: int | None = Field(default=None, ge=0, le=100)
    max_attempts: int | None = Field(default=None, ge=1)
    position: int | None = Field(default=None, ge=1)
    is_published: bool | None = None


class QuizRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    module_id: int
    title: str
    description: str | None
    passing_score: int
    max_attempts: int | None
    position: int
    is_published: bool
    created_at: datetime
    updated_at: datetime
    questions: list[QuizQuestionRead] = Field(default_factory=list)


class QuizStudentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    module_id: int
    title: str
    description: str | None
    passing_score: int
    max_attempts: int | None
    position: int
    questions: list[QuizQuestionStudentRead] = Field(default_factory=list)


# --- Submissions & Answers ---
class AnswerSubmit(BaseModel):
    question_id: int = Field(ge=1)
    selected_option_ids: list[int] = Field(default_factory=list)


class QuizSubmitRequest(BaseModel):
    answers: list[AnswerSubmit] = Field(default_factory=list)


class QuizAnswerRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    question_id: int
    selected_option_ids: list[int]
    is_correct: bool
    points_awarded: int


class QuizSubmissionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    quiz_id: int
    user_id: int
    score: float
    points_scored: int
    total_points: int
    passed: bool
    attempt_number: int
    submitted_at: datetime
    answers: list[QuizAnswerRead] = Field(default_factory=list)
