from fastapi import APIRouter, status

from app.api.deps import CurrentUser, DbSession, InstructorOrAdminUser
from app.models.enums import UserRole
from app.schemas.quiz import (
    QuizCreate,
    QuizQuestionCreate,
    QuizQuestionRead,
    QuizQuestionUpdate,
    QuizRead,
    QuizStudentRead,
    QuizSubmissionRead,
    QuizSubmitRequest,
    QuizUpdate,
)
from app.services import quiz_service

router = APIRouter(tags=["quizzes"])


@router.post(
    "/modules/{module_id}/quizzes",
    response_model=QuizRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create quiz for module (Instructor/Admin)",
    description="Creates a new quiz within a course module.",
)
async def create_quiz(
    module_id: int,
    payload: QuizCreate,
    db: DbSession,
    actor: InstructorOrAdminUser,
) -> QuizRead:
    quiz = await quiz_service.create_quiz(
        db,
        module_id=module_id,
        actor=actor,
        payload=payload,
    )
    return QuizRead.model_validate(quiz)


@router.patch(
    "/quizzes/{quiz_id}",
    response_model=QuizRead,
    summary="Update quiz (Instructor/Admin)",
    description="Updates quiz settings (title, passing score, max attempts).",
)
async def update_quiz(
    quiz_id: int,
    payload: QuizUpdate,
    db: DbSession,
    actor: InstructorOrAdminUser,
) -> QuizRead:
    quiz = await quiz_service.update_quiz(
        db,
        quiz_id=quiz_id,
        actor=actor,
        payload=payload,
    )
    return QuizRead.model_validate(quiz)


@router.delete(
    "/quizzes/{quiz_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete quiz (Instructor/Admin)",
    description="Deletes a quiz and all associated questions and submissions.",
)
async def delete_quiz(
    quiz_id: int,
    db: DbSession,
    actor: InstructorOrAdminUser,
) -> None:
    await quiz_service.delete_quiz(db, quiz_id=quiz_id, actor=actor)


@router.post(
    "/quizzes/{quiz_id}/questions",
    response_model=QuizQuestionRead,
    status_code=status.HTTP_201_CREATED,
    summary="Add question to quiz (Instructor/Admin)",
    description="Adds a new question and its options to a quiz.",
)
async def add_question(
    quiz_id: int,
    payload: QuizQuestionCreate,
    db: DbSession,
    actor: InstructorOrAdminUser,
) -> QuizQuestionRead:
    question = await quiz_service.add_question(
        db,
        quiz_id=quiz_id,
        actor=actor,
        payload=payload,
    )
    return QuizQuestionRead.model_validate(question)


@router.patch(
    "/quizzes/questions/{question_id}",
    response_model=QuizQuestionRead,
    summary="Update question (Instructor/Admin)",
    description="Updates a quiz question.",
)
async def update_question(
    question_id: int,
    payload: QuizQuestionUpdate,
    db: DbSession,
    actor: InstructorOrAdminUser,
) -> QuizQuestionRead:
    question = await quiz_service.update_question(
        db,
        question_id=question_id,
        actor=actor,
        payload=payload,
    )
    return QuizQuestionRead.model_validate(question)


@router.delete(
    "/quizzes/questions/{question_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete question (Instructor/Admin)",
    description="Deletes a question from a quiz.",
)
async def delete_question(
    question_id: int,
    db: DbSession,
    actor: InstructorOrAdminUser,
) -> None:
    await quiz_service.delete_question(db, question_id=question_id, actor=actor)


@router.get(
    "/quizzes/{quiz_id}",
    response_model=QuizRead | QuizStudentRead,
    summary="Get quiz details",
    description="Returns quiz and questions. Correct answers are hidden for enrolled students.",
)
async def get_quiz(
    quiz_id: int,
    db: DbSession,
    actor: CurrentUser,
) -> QuizRead | QuizStudentRead:
    quiz = await quiz_service.get_quiz(db, quiz_id=quiz_id, actor=actor)
    if actor.role in (UserRole.INSTRUCTOR.value, UserRole.ADMIN.value):
        return QuizRead.model_validate(quiz)
    return QuizStudentRead.model_validate(quiz)


@router.post(
    "/quizzes/{quiz_id}/submit",
    response_model=QuizSubmissionRead,
    status_code=status.HTTP_201_CREATED,
    summary="Submit quiz attempt",
    description=(
        "Evaluates answers, records student attempt, and returns auto-graded "
        "score and pass/fail result."
    ),
)
async def submit_quiz(
    quiz_id: int,
    payload: QuizSubmitRequest,
    db: DbSession,
    current_user: CurrentUser,
) -> QuizSubmissionRead:
    submission = await quiz_service.submit_quiz(
        db,
        quiz_id=quiz_id,
        actor=current_user,
        payload=payload,
    )
    return QuizSubmissionRead.model_validate(submission)


@router.get(
    "/quizzes/{quiz_id}/submissions",
    response_model=list[QuizSubmissionRead],
    summary="List quiz submissions",
    description=(
        "Returns student submissions for a quiz. Instructors see all; students see their own."
    ),
)
async def list_quiz_submissions(
    quiz_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> list[QuizSubmissionRead]:
    subs = await quiz_service.list_quiz_submissions(
        db,
        quiz_id=quiz_id,
        actor=current_user,
    )
    return [QuizSubmissionRead.model_validate(s) for s in subs]
