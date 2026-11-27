from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.common.errors import BadRequestError, ForbiddenError, NotFoundError
from app.models.course import Course, Module
from app.models.enrollment import Enrollment
from app.models.enums import EnrollmentStatus, UserRole
from app.models.quiz import (
    QuestionOption,
    Quiz,
    QuizAnswer,
    QuizQuestion,
    QuizSubmission,
)
from app.models.user import User
from app.schemas.quiz import (
    QuizCreate,
    QuizQuestionCreate,
    QuizQuestionUpdate,
    QuizSubmitRequest,
    QuizUpdate,
)


def _can_manage_course(course: Course, user: User) -> bool:
    return user.role == UserRole.ADMIN.value or course.instructor_id == user.id


async def create_quiz(
    db: AsyncSession,
    *,
    module_id: int,
    actor: User,
    payload: QuizCreate,
) -> Quiz:
    module = await db.scalar(
        select(Module).options(selectinload(Module.course)).where(Module.id == module_id)
    )
    if not module:
        raise NotFoundError("Module not found", code="MODULE_NOT_FOUND")

    if not _can_manage_course(module.course, actor):
        raise ForbiddenError("Only the course instructor or an administrator can add quizzes")

    quiz = Quiz(
        module_id=module_id,
        title=payload.title,
        description=payload.description,
        passing_score=payload.passing_score,
        max_attempts=payload.max_attempts,
        position=payload.position,
        is_published=payload.is_published,
    )
    db.add(quiz)
    await db.commit()
    loaded_quiz = await db.scalar(
        select(Quiz)
        .options(selectinload(Quiz.questions).selectinload(QuizQuestion.options))
        .where(Quiz.id == quiz.id)
    )
    return loaded_quiz or quiz


async def update_quiz(
    db: AsyncSession,
    *,
    quiz_id: int,
    actor: User,
    payload: QuizUpdate,
) -> Quiz:
    quiz = await db.scalar(
        select(Quiz)
        .options(selectinload(Quiz.module).selectinload(Module.course))
        .where(Quiz.id == quiz_id)
    )
    if not quiz:
        raise NotFoundError("Quiz not found", code="QUIZ_NOT_FOUND")

    if not _can_manage_course(quiz.module.course, actor):
        raise ForbiddenError("Only the course instructor or an administrator can modify this quiz")

    for field, val in payload.model_dump(exclude_unset=True).items():
        setattr(quiz, field, val)

    await db.commit()
    loaded_quiz = await db.scalar(
        select(Quiz)
        .options(selectinload(Quiz.questions).selectinload(QuizQuestion.options))
        .where(Quiz.id == quiz.id)
    )
    return loaded_quiz or quiz


async def delete_quiz(db: AsyncSession, *, quiz_id: int, actor: User) -> None:
    quiz = await db.scalar(
        select(Quiz)
        .options(selectinload(Quiz.module).selectinload(Module.course))
        .where(Quiz.id == quiz_id)
    )
    if not quiz:
        raise NotFoundError("Quiz not found", code="QUIZ_NOT_FOUND")

    if not _can_manage_course(quiz.module.course, actor):
        raise ForbiddenError("Only the course instructor or an administrator can delete this quiz")

    await db.delete(quiz)
    await db.commit()


async def add_question(
    db: AsyncSession,
    *,
    quiz_id: int,
    actor: User,
    payload: QuizQuestionCreate,
) -> QuizQuestion:
    quiz = await db.scalar(
        select(Quiz)
        .options(selectinload(Quiz.module).selectinload(Module.course))
        .where(Quiz.id == quiz_id)
    )
    if not quiz:
        raise NotFoundError("Quiz not found", code="QUIZ_NOT_FOUND")

    if not _can_manage_course(quiz.module.course, actor):
        raise ForbiddenError("Only the course instructor or an administrator can modify this quiz")

    question = QuizQuestion(
        quiz_id=quiz_id,
        question_text=payload.question_text,
        question_type=payload.question_type,
        points=payload.points,
        position=payload.position,
        explanation=payload.explanation,
    )
    db.add(question)
    await db.flush()

    for opt_payload in payload.options:
        opt = QuestionOption(
            question_id=question.id,
            option_text=opt_payload.option_text,
            is_correct=opt_payload.is_correct,
            position=opt_payload.position,
        )
        db.add(opt)

    await db.commit()
    # Refresh with options loaded
    question_full = await db.scalar(
        select(QuizQuestion)
        .options(selectinload(QuizQuestion.options))
        .where(QuizQuestion.id == question.id)
    )
    return question_full or question


async def update_question(
    db: AsyncSession,
    *,
    question_id: int,
    actor: User,
    payload: QuizQuestionUpdate,
) -> QuizQuestion:
    question = await db.scalar(
        select(QuizQuestion)
        .options(
            selectinload(QuizQuestion.quiz).selectinload(Quiz.module).selectinload(Module.course),
            selectinload(QuizQuestion.options),
        )
        .where(QuizQuestion.id == question_id)
    )
    if not question:
        raise NotFoundError("Question not found", code="QUESTION_NOT_FOUND")

    if not _can_manage_course(question.quiz.module.course, actor):
        raise ForbiddenError(
            "Only the course instructor or an administrator can modify this question"
        )

    for field, val in payload.model_dump(exclude_unset=True).items():
        setattr(question, field, val)

    await db.commit()
    loaded_question = await db.scalar(
        select(QuizQuestion)
        .options(selectinload(QuizQuestion.options))
        .where(QuizQuestion.id == question.id)
    )
    return loaded_question or question


async def delete_question(db: AsyncSession, *, question_id: int, actor: User) -> None:
    question = await db.scalar(
        select(QuizQuestion)
        .options(
            selectinload(QuizQuestion.quiz).selectinload(Quiz.module).selectinload(Module.course),
        )
        .where(QuizQuestion.id == question_id)
    )
    if not question:
        raise NotFoundError("Question not found", code="QUESTION_NOT_FOUND")

    if not _can_manage_course(question.quiz.module.course, actor):
        raise ForbiddenError(
            "Only the course instructor or an administrator can delete this question"
        )

    await db.delete(question)
    await db.commit()


async def get_quiz(
    db: AsyncSession,
    *,
    quiz_id: int,
    actor: User,
) -> Quiz:
    quiz = await db.scalar(
        select(Quiz)
        .options(
            selectinload(Quiz.module).selectinload(Module.course),
            selectinload(Quiz.questions).selectinload(QuizQuestion.options),
        )
        .where(Quiz.id == quiz_id)
    )
    if not quiz:
        raise NotFoundError("Quiz not found", code="QUIZ_NOT_FOUND")

    # If actor is not instructor/admin, they must be actively enrolled
    if not _can_manage_course(quiz.module.course, actor):
        enrollment = await db.scalar(
            select(Enrollment).where(
                Enrollment.course_id == quiz.module.course_id,
                Enrollment.user_id == actor.id,
                Enrollment.status == EnrollmentStatus.ACTIVE.value,
            )
        )
        if not enrollment:
            raise ForbiddenError("You must be enrolled to view this quiz", code="NOT_ENROLLED")

    return quiz


async def submit_quiz(
    db: AsyncSession,
    *,
    quiz_id: int,
    actor: User,
    payload: QuizSubmitRequest,
) -> QuizSubmission:
    quiz = await db.scalar(
        select(Quiz)
        .options(
            selectinload(Quiz.module).selectinload(Module.course),
            selectinload(Quiz.questions).selectinload(QuizQuestion.options),
        )
        .where(Quiz.id == quiz_id)
    )
    if not quiz:
        raise NotFoundError("Quiz not found", code="QUIZ_NOT_FOUND")

    # Check enrollment
    enrollment = await db.scalar(
        select(Enrollment).where(
            Enrollment.course_id == quiz.module.course_id,
            Enrollment.user_id == actor.id,
            Enrollment.status == EnrollmentStatus.ACTIVE.value,
        )
    )
    if not enrollment:
        raise ForbiddenError("You must be enrolled to take this quiz", code="NOT_ENROLLED")

    # Check attempt limit
    attempts_count = int(
        await db.scalar(
            select(func.count(QuizSubmission.id)).where(
                QuizSubmission.quiz_id == quiz_id,
                QuizSubmission.user_id == actor.id,
            )
        )
        or 0
    )
    if quiz.max_attempts and attempts_count >= quiz.max_attempts:
        raise BadRequestError(
            f"Maximum attempts ({quiz.max_attempts}) reached for this quiz",
            code="MAX_ATTEMPTS_REACHED",
        )

    # Grade
    submitted_answers_map = {a.question_id: set(a.selected_option_ids) for a in payload.answers}

    total_points = sum(q.points for q in quiz.questions)
    points_scored = 0
    answer_records: list[QuizAnswer] = []

    for q in quiz.questions:
        selected_ids = submitted_answers_map.get(q.id, set())
        correct_ids = {opt.id for opt in q.options if opt.is_correct}

        is_correct = selected_ids == correct_ids and len(correct_ids) > 0
        awarded = q.points if is_correct else 0
        points_scored += awarded

        ans = QuizAnswer(
            question_id=q.id,
            selected_option_ids=sorted(selected_ids),
            is_correct=is_correct,
            points_awarded=awarded,
        )
        answer_records.append(ans)

    score_pct = round((points_scored / total_points) * 100, 2) if total_points > 0 else 100.0
    passed = score_pct >= quiz.passing_score

    submission = QuizSubmission(
        quiz_id=quiz_id,
        user_id=actor.id,
        score=score_pct,
        points_scored=points_scored,
        total_points=total_points,
        passed=passed,
        attempt_number=attempts_count + 1,
    )
    db.add(submission)
    await db.flush()

    for ans in answer_records:
        ans.submission_id = submission.id
        db.add(ans)

    await db.commit()
    # Refresh with answers
    sub_full = await db.scalar(
        select(QuizSubmission)
        .options(selectinload(QuizSubmission.answers))
        .where(QuizSubmission.id == submission.id)
    )
    return sub_full or submission


async def list_quiz_submissions(
    db: AsyncSession,
    *,
    quiz_id: int,
    actor: User,
) -> list[QuizSubmission]:
    quiz = await db.scalar(
        select(Quiz)
        .options(selectinload(Quiz.module).selectinload(Module.course))
        .where(Quiz.id == quiz_id)
    )
    if not quiz:
        raise NotFoundError("Quiz not found", code="QUIZ_NOT_FOUND")

    stmt = (
        select(QuizSubmission)
        .options(selectinload(QuizSubmission.answers))
        .where(QuizSubmission.quiz_id == quiz_id)
    )
    if not _can_manage_course(quiz.module.course, actor):
        stmt = stmt.where(QuizSubmission.user_id == actor.id)

    stmt = stmt.order_by(QuizSubmission.submitted_at.desc())
    return list((await db.scalars(stmt)).all())
