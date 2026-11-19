from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.common.errors import ConflictError, ForbiddenError, NotFoundError
from app.common.utils import calculate_completion_percentage
from app.models.course import Course, Lesson, Module
from app.models.enrollment import Enrollment, LessonProgress
from app.models.enums import EnrollmentStatus
from app.models.user import User
from app.schemas.progress import CourseProgressRead, LessonCompletionResponse, LessonProgressRead
from app.services.course_service import assert_can_manage_course, can_manage_course


async def _compute_course_progress(
    db: AsyncSession,
    *,
    course_id: int,
    user_id: int,
) -> CourseProgressRead:
    lesson_ids_stmt = (
        select(Lesson.id)
        .join(Module, Lesson.module_id == Module.id)
        .where(Module.course_id == course_id)
    )
    all_lesson_ids = list((await db.scalars(lesson_ids_stmt)).all())
    total_lessons = len(all_lesson_ids)

    if total_lessons == 0:
        return CourseProgressRead(
            course_id=course_id,
            user_id=user_id,
            total_lessons=0,
            completed_lessons=0,
            completion_percentage=0.0,
            completed_lesson_ids=[],
        )

    completed_stmt = (
        select(LessonProgress.lesson_id)
        .where(
            LessonProgress.user_id == user_id,
            LessonProgress.lesson_id.in_(all_lesson_ids),
        )
        .order_by(LessonProgress.lesson_id.asc())
    )
    completed_lesson_ids = list((await db.scalars(completed_stmt)).all())
    completed_count = len(completed_lesson_ids)

    return CourseProgressRead(
        course_id=course_id,
        user_id=user_id,
        total_lessons=total_lessons,
        completed_lessons=completed_count,
        completion_percentage=calculate_completion_percentage(completed_count, total_lessons),
        completed_lesson_ids=completed_lesson_ids,
    )


async def mark_lesson_complete(
    db: AsyncSession,
    *,
    lesson_id: int,
    actor: User,
) -> LessonCompletionResponse:
    stmt = (
        select(Lesson)
        .options(joinedload(Lesson.module).joinedload(Module.course))
        .where(Lesson.id == lesson_id)
    )
    lesson = (await db.scalars(stmt)).unique().one_or_none()
    if not lesson:
        raise NotFoundError("Lesson not found", code="LESSON_NOT_FOUND")

    course_id = lesson.module.course_id
    enrollment = await db.scalar(
        select(Enrollment).where(
            Enrollment.user_id == actor.id,
            Enrollment.course_id == course_id,
            Enrollment.status == EnrollmentStatus.ACTIVE.value,
        )
    )
    if not enrollment:
        raise ForbiddenError(
            "You must be actively enrolled in this course to mark lessons complete",
            code="ENROLLMENT_REQUIRED",
        )

    existing = await db.scalar(
        select(LessonProgress).where(
            LessonProgress.user_id == actor.id,
            LessonProgress.lesson_id == lesson.id,
        )
    )
    if existing:
        raise ConflictError("Lesson already marked as complete", code="ALREADY_COMPLETED")

    progress = LessonProgress(user_id=actor.id, lesson_id=lesson.id)
    db.add(progress)
    try:
        await db.commit()
        await db.refresh(progress)
    except IntegrityError as exc:
        await db.rollback()
        raise ConflictError("Lesson already marked as complete", code="ALREADY_COMPLETED") from exc

    course_progress = await _compute_course_progress(db, course_id=course_id, user_id=actor.id)
    return LessonCompletionResponse(
        lesson_progress=LessonProgressRead.model_validate(progress),
        course_progress=course_progress,
    )


async def unmark_lesson_complete(
    db: AsyncSession,
    *,
    lesson_id: int,
    actor: User,
) -> None:
    stmt = select(Lesson).options(joinedload(Lesson.module)).where(Lesson.id == lesson_id)
    lesson = (await db.scalars(stmt)).unique().one_or_none()
    if not lesson:
        raise NotFoundError("Lesson not found", code="LESSON_NOT_FOUND")

    enrollment = await db.scalar(
        select(Enrollment).where(
            Enrollment.user_id == actor.id,
            Enrollment.course_id == lesson.module.course_id,
            Enrollment.status == EnrollmentStatus.ACTIVE.value,
        )
    )
    if not enrollment:
        raise ForbiddenError(
            "You must be actively enrolled in this course to update lesson progress",
            code="ENROLLMENT_REQUIRED",
        )

    progress = await db.scalar(
        select(LessonProgress).where(
            LessonProgress.user_id == actor.id,
            LessonProgress.lesson_id == lesson.id,
        )
    )
    if not progress:
        raise NotFoundError("Lesson completion record not found", code="PROGRESS_NOT_FOUND")

    try:
        await db.delete(progress)
        await db.commit()
    except Exception:
        await db.rollback()
        raise


async def get_course_progress(
    db: AsyncSession,
    *,
    course_id: int,
    actor: User,
    target_user_id: int | None = None,
) -> CourseProgressRead:
    course = await db.get(Course, course_id)
    if not course:
        raise NotFoundError("Course not found", code="COURSE_NOT_FOUND")

    resolved_user_id = target_user_id if target_user_id is not None else actor.id
    if resolved_user_id != actor.id:
        assert_can_manage_course(course, actor)
    elif not can_manage_course(course, actor):
        enrollment = await db.scalar(
            select(Enrollment).where(
                Enrollment.user_id == actor.id,
                Enrollment.course_id == course.id,
                Enrollment.status == EnrollmentStatus.ACTIVE.value,
            )
        )
        if not enrollment:
            raise ForbiddenError(
                "You must be actively enrolled in this course to view progress",
                code="ENROLLMENT_REQUIRED",
            )

    return await _compute_course_progress(db, course_id=course.id, user_id=resolved_user_id)
