from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.common.errors import BadRequestError, ConflictError, NotFoundError
from app.common.utils import calculate_completion_percentage
from app.models.course import Course, Lesson, Module
from app.models.enrollment import Enrollment, LessonProgress
from app.models.enums import CourseStatus, EnrollmentStatus
from app.models.user import User
from app.schemas.enrollment import RosterStudentRead
from app.schemas.user import UserSummary
from app.services.course_service import assert_can_manage_course


async def enroll_in_course(
    db: AsyncSession, *, course_id: int, actor: User
) -> Enrollment:
    course = await db.get(Course, course_id)
    if not course:
        raise NotFoundError("Course not found", code="COURSE_NOT_FOUND")
    if course.status != CourseStatus.PUBLISHED.value:
        raise BadRequestError(
            "Cannot enroll in a course that is not published",
            code="COURSE_NOT_PUBLISHED",
        )

    existing = await db.scalar(
        select(Enrollment).where(
            Enrollment.user_id == actor.id,
            Enrollment.course_id == course.id,
        )
    )
    if existing:
        if existing.status == EnrollmentStatus.ACTIVE.value:
            raise ConflictError(
                "Already enrolled in this course", code="ALREADY_ENROLLED"
            )
        existing.status = EnrollmentStatus.ACTIVE.value
        existing.enrolled_at = datetime.now(UTC).replace(tzinfo=None)
        try:
            await db.commit()
            await db.refresh(existing)
        except Exception:
            await db.rollback()
            raise
        return existing

    enrollment = Enrollment(
        user_id=actor.id,
        course_id=course.id,
        status=EnrollmentStatus.ACTIVE.value,
    )
    db.add(enrollment)
    try:
        await db.commit()
        await db.refresh(enrollment)
    except IntegrityError as exc:
        await db.rollback()
        raise ConflictError(
            "Already enrolled in this course", code="ALREADY_ENROLLED"
        ) from exc
    return enrollment


async def unenroll_from_course(
    db: AsyncSession, *, course_id: int, actor: User
) -> None:
    enrollment = await db.scalar(
        select(Enrollment).where(
            Enrollment.user_id == actor.id,
            Enrollment.course_id == course_id,
            Enrollment.status == EnrollmentStatus.ACTIVE.value,
        )
    )
    if not enrollment:
        raise NotFoundError("Active enrollment not found", code="ENROLLMENT_NOT_FOUND")

    enrollment.status = EnrollmentStatus.DROPPED.value
    try:
        await db.commit()
    except Exception:
        await db.rollback()
        raise


async def list_user_enrollments(
    db: AsyncSession,
    *,
    user_id: int,
    page: int,
    per_page: int,
    status: EnrollmentStatus | None = EnrollmentStatus.ACTIVE,
) -> tuple[list[Enrollment], int]:
    filters = [Enrollment.user_id == user_id]
    if status is not None:
        filters.append(Enrollment.status == status.value)

    total = int(await db.scalar(select(func.count(Enrollment.id)).where(*filters)) or 0)
    offset = (page - 1) * per_page
    stmt = (
        select(Enrollment)
        .options(joinedload(Enrollment.course).joinedload(Course.instructor))
        .where(*filters)
        .order_by(Enrollment.enrolled_at.desc(), Enrollment.id.desc())
        .offset(offset)
        .limit(per_page)
    )
    items = list((await db.scalars(stmt)).unique().all())
    return items, total


async def list_course_roster(
    db: AsyncSession,
    *,
    course_id: int,
    actor: User,
    page: int,
    per_page: int,
    status: EnrollmentStatus | None = EnrollmentStatus.ACTIVE,
) -> tuple[list[RosterStudentRead], int]:
    course = await db.get(Course, course_id)
    if not course:
        raise NotFoundError("Course not found", code="COURSE_NOT_FOUND")
    assert_can_manage_course(course, actor)

    filters = [Enrollment.course_id == course.id]
    if status is not None:
        filters.append(Enrollment.status == status.value)

    total = int(await db.scalar(select(func.count(Enrollment.id)).where(*filters)) or 0)
    offset = (page - 1) * per_page

    enrollments_stmt = (
        select(Enrollment)
        .options(joinedload(Enrollment.user))
        .where(*filters)
        .order_by(Enrollment.enrolled_at.desc(), Enrollment.id.desc())
        .offset(offset)
        .limit(per_page)
    )
    enrollments = list((await db.scalars(enrollments_stmt)).unique().all())
    if not enrollments:
        return [], total

    # Aggregate lesson count and completed counts in two constant queries (no N+1)
    total_lessons = int(
        await db.scalar(
            select(func.count(Lesson.id))
            .join(Module, Lesson.module_id == Module.id)
            .where(Module.course_id == course.id)
        )
        or 0
    )

    student_ids = [enr.user_id for enr in enrollments]
    progress_rows = await db.execute(
        select(LessonProgress.user_id, func.count(LessonProgress.id))
        .join(Lesson, LessonProgress.lesson_id == Lesson.id)
        .join(Module, Lesson.module_id == Module.id)
        .where(
            Module.course_id == course.id,
            LessonProgress.user_id.in_(student_ids),
        )
        .group_by(LessonProgress.user_id)
    )
    completed_by_user = {row[0]: int(row[1]) for row in progress_rows.all()}

    roster = [
        RosterStudentRead(
            enrollment_id=enr.id,
            student=UserSummary.model_validate(enr.user),
            status=EnrollmentStatus(enr.status),
            enrolled_at=enr.enrolled_at,
            completed_lessons=completed_by_user.get(enr.user_id, 0),
            total_lessons=total_lessons,
            completion_percentage=calculate_completion_percentage(
                completed_by_user.get(enr.user_id, 0),
                total_lessons,
            ),
        )
        for enr in enrollments
    ]
    return roster, total
