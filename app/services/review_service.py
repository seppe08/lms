from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.common.errors import ConflictError, ForbiddenError, NotFoundError
from app.models.course import Course
from app.models.enrollment import Enrollment
from app.models.enums import CourseStatus, EnrollmentStatus, UserRole
from app.models.review import Review
from app.models.user import User
from app.schemas.review import CourseRatingSummary, ReviewCreate, ReviewUpdate


async def create_review(
    db: AsyncSession,
    *,
    course_id: int,
    actor: User,
    payload: ReviewCreate,
) -> Review:
    course = await db.get(Course, course_id)
    if not course or course.status != CourseStatus.PUBLISHED.value:
        raise NotFoundError("Course not found", code="COURSE_NOT_FOUND")

    if course.instructor_id == actor.id:
        raise ForbiddenError(
            "Instructors cannot review their own course",
            code="INSTRUCTOR_CANNOT_REVIEW",
        )

    # Must be actively enrolled
    enrollment = await db.scalar(
        select(Enrollment).where(
            Enrollment.course_id == course_id,
            Enrollment.user_id == actor.id,
            Enrollment.status == EnrollmentStatus.ACTIVE.value,
        )
    )
    if not enrollment:
        raise ForbiddenError(
            "Only actively enrolled students can review this course",
            code="NOT_ENROLLED",
        )

    existing = await db.scalar(
        select(Review.id).where(Review.course_id == course_id, Review.user_id == actor.id)
    )
    if existing:
        raise ConflictError(
            "You have already reviewed this course",
            code="REVIEW_ALREADY_EXISTS",
        )

    review = Review(
        course_id=course_id,
        user_id=actor.id,
        rating=payload.rating,
        comment=payload.comment,
    )
    db.add(review)
    try:
        await db.commit()
        await db.refresh(review)
    except IntegrityError as exc:
        await db.rollback()
        raise ConflictError(
            "You have already reviewed this course", code="REVIEW_ALREADY_EXISTS"
        ) from exc

    # Load user relationship
    review.user = actor
    return review


async def list_course_reviews(
    db: AsyncSession,
    *,
    course_id: int,
    page: int,
    per_page: int,
) -> tuple[list[Review], int]:
    course = await db.get(Course, course_id)
    if not course:
        raise NotFoundError("Course not found", code="COURSE_NOT_FOUND")

    total = int(
        await db.scalar(select(func.count(Review.id)).where(Review.course_id == course_id)) or 0
    )
    offset = (page - 1) * per_page
    stmt = (
        select(Review)
        .options(joinedload(Review.user))
        .where(Review.course_id == course_id)
        .order_by(Review.created_at.desc(), Review.id.desc())
        .offset(offset)
        .limit(per_page)
    )
    items = list((await db.scalars(stmt)).unique().all())
    return items, total


async def update_review(
    db: AsyncSession,
    *,
    review_id: int,
    actor: User,
    payload: ReviewUpdate,
) -> Review:
    review = await db.scalar(
        select(Review).options(joinedload(Review.user)).where(Review.id == review_id)
    )
    if not review:
        raise NotFoundError("Review not found", code="REVIEW_NOT_FOUND")

    if actor.role != UserRole.ADMIN.value and review.user_id != actor.id:
        raise ForbiddenError("Only the author or an administrator can modify this review")

    if payload.rating is not None:
        review.rating = payload.rating
    if payload.comment is not None:
        review.comment = payload.comment

    await db.commit()
    await db.refresh(review)
    return review


async def delete_review(db: AsyncSession, *, review_id: int, actor: User) -> None:
    review = await db.get(Review, review_id)
    if not review:
        raise NotFoundError("Review not found", code="REVIEW_NOT_FOUND")

    if actor.role != UserRole.ADMIN.value and review.user_id != actor.id:
        raise ForbiddenError("Only the author or an administrator can delete this review")

    await db.delete(review)
    await db.commit()


async def get_course_rating_summary(db: AsyncSession, *, course_id: int) -> CourseRatingSummary:
    stmt = select(func.avg(Review.rating), func.count(Review.id)).where(
        Review.course_id == course_id
    )
    row = (await db.execute(stmt)).first()
    if not row or row[1] == 0:
        return CourseRatingSummary(average_rating=0.0, review_count=0)

    avg_val = round(float(row[0]), 2) if row[0] is not None else 0.0
    count_val = int(row[1])
    return CourseRatingSummary(average_rating=avg_val, review_count=count_val)
