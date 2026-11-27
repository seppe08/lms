from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.common.errors import BadRequestError, ForbiddenError, NotFoundError
from app.models.course import Module
from app.models.enrollment import Enrollment
from app.models.enums import CourseStatus, EnrollmentStatus
from app.models.quiz import (
    QuestionOption,
    Quiz,
    QuizAnswer,
    QuizQuestion,
    QuizSubmission,
)
from app.models.user import User
from app.schemas.quiz import (
    QuestionOptionCreate,
    QuestionOptionUpdate,
    QuizCreate,
    QuizQuestionCreate,
    QuizQuestionUpdate,
    QuizSubmitRequest,
    QuizUpdate,
)
from app.services.course_service import can_manage_course


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

    if not can_manage_course(module.course, actor):
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

    if not can_manage_course(quiz.module.course, actor):
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

    if not can_manage_course(quiz.module.course, actor):
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

    if not can_manage_course(quiz.module.course, actor):
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

    if not can_manage_course(question.quiz.module.course, actor):
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

    if not can_manage_course(question.quiz.module.course, actor):
        raise ForbiddenError(
            "Only the course instructor or an administrator can delete this question"
        )

    await db.delete(question)
    await db.commit()


async def add_option(
    db: AsyncSession,
    *,
    question_id: int,
    actor: User,
    payload: QuestionOptionCreate,
) -> QuestionOption:
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
    if not can_manage_course(question.quiz.module.course, actor):
        raise ForbiddenError(
            "Only the course instructor or an administrator can modify this question"
        )
    if (
        payload.is_correct
        and question.question_type in ("multiple_choice", "true_false")
        and any(opt.is_correct for opt in question.options)
    ):
        raise BadRequestError(
            f"{question.question_type} questions can only have one correct option",
            code="MULTIPLE_CORRECT_OPTIONS",
        )

    option = QuestionOption(
        question_id=question_id,
        option_text=payload.option_text,
        is_correct=payload.is_correct,
        position=payload.position,
    )
    db.add(option)
    await db.commit()
    await db.refresh(option)
    return option


async def update_option(
    db: AsyncSession,
    *,
    option_id: int,
    actor: User,
    payload: QuestionOptionUpdate,
) -> QuestionOption:
    option = await db.scalar(
        select(QuestionOption)
        .options(
            selectinload(QuestionOption.question)
            .selectinload(QuizQuestion.quiz)
            .selectinload(Quiz.module)
            .selectinload(Module.course),
            selectinload(QuestionOption.question).selectinload(QuizQuestion.options),
        )
        .where(QuestionOption.id == option_id)
    )
    if not option:
        raise NotFoundError("Option not found", code="OPTION_NOT_FOUND")
    if not can_manage_course(option.question.quiz.module.course, actor):
        raise ForbiddenError(
            "Only the course instructor or an administrator can modify this option"
        )

    updates = payload.model_dump(exclude_unset=True)
    if (
        updates.get("is_correct") is True
        and option.question.question_type in ("multiple_choice", "true_false")
        and any(opt.is_correct and opt.id != option.id for opt in option.question.options)
    ):
        raise BadRequestError(
            f"{option.question.question_type} questions can only have one correct option",
            code="MULTIPLE_CORRECT_OPTIONS",
        )

    for field, val in updates.items():
        setattr(option, field, val)

    await db.commit()
    await db.refresh(option)
    return option


async def delete_option(db: AsyncSession, *, option_id: int, actor: User) -> None:
    option = await db.scalar(
        select(QuestionOption)
        .options(
            selectinload(QuestionOption.question)
            .selectinload(QuizQuestion.quiz)
            .selectinload(Quiz.module)
            .selectinload(Module.course),
            selectinload(QuestionOption.question).selectinload(QuizQuestion.options),
        )
        .where(QuestionOption.id == option_id)
    )
    if not option:
        raise NotFoundError("Option not found", code="OPTION_NOT_FOUND")
    if not can_manage_course(option.question.quiz.module.course, actor):
        raise ForbiddenError(
            "Only the course instructor or an administrator can delete this option"
        )
    if len(option.question.options) <= 2:
        raise BadRequestError(
            "Questions must retain at least 2 options",
            code="MINIMUM_OPTIONS_REQUIRED",
        )

    await db.delete(option)
    await db.commit()


async def list_module_quizzes(
    db: AsyncSession,
    *,
    module_id: int,
    actor: User,
) -> list[Quiz]:
    module = await db.scalar(
        select(Module).options(selectinload(Module.course)).where(Module.id == module_id)
    )
    if not module:
        raise NotFoundError("Module not found", code="MODULE_NOT_FOUND")

    is_manager = can_manage_course(module.course, actor)
    if not is_manager:
        if module.course.status != CourseStatus.PUBLISHED.value:
            raise NotFoundError("Module not found", code="MODULE_NOT_FOUND")
        enrollment = await db.scalar(
            select(Enrollment).where(
                Enrollment.course_id == module.course_id,
                Enrollment.user_id == actor.id,
                Enrollment.status == EnrollmentStatus.ACTIVE.value,
            )
        )
        if not enrollment:
            raise ForbiddenError("You must be enrolled to view quizzes", code="NOT_ENROLLED")

    stmt = (
        select(Quiz)
        .options(selectinload(Quiz.questions).selectinload(QuizQuestion.options))
        .where(Quiz.module_id == module_id)
    )
    if not is_manager:
        stmt = stmt.where(Quiz.is_published.is_(True))
    stmt = stmt.order_by(Quiz.position.asc(), Quiz.id.asc())
    return list((await db.scalars(stmt)).all())


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

    # If actor is not instructor/admin, course and quiz must be published and user enrolled
    if not can_manage_course(quiz.module.course, actor):
        if quiz.module.course.status != CourseStatus.PUBLISHED.value or not quiz.is_published:
            raise NotFoundError("Quiz not found", code="QUIZ_NOT_FOUND")
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

    if quiz.module.course.status != CourseStatus.PUBLISHED.value or not quiz.is_published:
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

    # Validate submitted answers against quiz questions and options
    question_map = {q.id: q for q in quiz.questions}
    submitted_answers_map: dict[int, set[int]] = {}
    for ans in payload.answers:
        if ans.question_id not in question_map:
            raise BadRequestError(
                f"Question {ans.question_id} does not belong to this quiz",
                code="INVALID_QUESTION_ID",
            )
        q = question_map[ans.question_id]
        selected_set = set(ans.selected_option_ids)
        valid_option_ids = {opt.id for opt in q.options}
        if not selected_set.issubset(valid_option_ids):
            raise BadRequestError(
                f"Invalid option ID selected for question {ans.question_id}",
                code="INVALID_OPTION_ID",
            )
        if q.question_type in ("multiple_choice", "true_false") and len(selected_set) > 1:
            raise BadRequestError(
                f"{q.question_type} questions allow at most one selected option",
                code="MULTIPLE_OPTIONS_NOT_ALLOWED",
            )
        submitted_answers_map[ans.question_id] = selected_set

    total_points = sum(q.points for q in quiz.questions)
    points_scored = 0
    answer_records: list[QuizAnswer] = []

    for q in quiz.questions:
        selected_ids = submitted_answers_map.get(q.id, set())
        correct_ids = {opt.id for opt in q.options if opt.is_correct}

        is_correct = selected_ids == correct_ids and len(correct_ids) > 0
        awarded = q.points if is_correct else 0
        points_scored += awarded

        ans_record = QuizAnswer(
            question_id=q.id,
            selected_option_ids=sorted(selected_ids),
            is_correct=is_correct,
            points_awarded=awarded,
        )
        answer_records.append(ans_record)

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
    try:
        await db.flush()
        for ans_record in answer_records:
            ans_record.submission_id = submission.id
            db.add(ans_record)
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise BadRequestError(
            "Concurrent quiz submission conflict; please retry",
            code="SUBMISSION_CONFLICT",
        ) from exc

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
    if not can_manage_course(quiz.module.course, actor):
        if quiz.module.course.status != CourseStatus.PUBLISHED.value or not quiz.is_published:
            raise NotFoundError("Quiz not found", code="QUIZ_NOT_FOUND")
        stmt = stmt.where(QuizSubmission.user_id == actor.id)

    stmt = stmt.order_by(QuizSubmission.submitted_at.desc())
    return list((await db.scalars(stmt)).all())
