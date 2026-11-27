from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.common.errors import BadRequestError, ForbiddenError, NotFoundError
from app.models.certificate import Certificate
from app.models.course import Course
from app.models.enrollment import Enrollment
from app.models.enums import CourseStatus, EnrollmentStatus
from app.models.user import User
from app.schemas.certificate import CertificateVerifyRead
from app.services import progress_service


async def generate_certificate(
    db: AsyncSession,
    *,
    course_id: int,
    actor: User,
) -> Certificate:
    course = await db.get(Course, course_id)
    if not course or course.status != CourseStatus.PUBLISHED.value:
        raise NotFoundError("Course not found", code="COURSE_NOT_FOUND")

    enrollment = await db.scalar(
        select(Enrollment).where(
            Enrollment.course_id == course_id,
            Enrollment.user_id == actor.id,
            Enrollment.status == EnrollmentStatus.ACTIVE.value,
        )
    )
    if not enrollment:
        raise ForbiddenError(
            "You must be actively enrolled to receive a certificate",
            code="NOT_ENROLLED",
        )

    # Check progress
    progress = await progress_service.get_course_progress(db, course_id=course_id, actor=actor)
    if progress.completion_percentage < 100.0 or progress.total_lessons == 0:
        raise BadRequestError(
            f"Course completion is {progress.completion_percentage}%. "
            "100% completion is required to earn a certificate.",
            code="COURSE_INCOMPLETE",
            details={
                "completion_percentage": progress.completion_percentage,
                "completed_lessons": progress.completed_lessons,
                "total_lessons": progress.total_lessons,
            },
        )

    existing = await db.scalar(
        select(Certificate).where(
            Certificate.course_id == course_id,
            Certificate.user_id == actor.id,
        )
    )
    if existing:
        return existing

    code = f"CERT-{uuid4().hex[:12].upper()}"
    certificate = Certificate(
        certificate_code=code,
        user_id=actor.id,
        course_id=course_id,
    )
    db.add(certificate)
    try:
        await db.commit()
        await db.refresh(certificate)
    except IntegrityError:
        await db.rollback()
        existing_after_race = await db.scalar(
            select(Certificate).where(
                Certificate.course_id == course_id,
                Certificate.user_id == actor.id,
            )
        )
        if existing_after_race:
            return existing_after_race
        raise
    return certificate


async def list_user_certificates(
    db: AsyncSession,
    *,
    user_id: int,
) -> list[Certificate]:
    stmt = (
        select(Certificate)
        .where(Certificate.user_id == user_id)
        .order_by(Certificate.issued_at.desc())
    )
    return list((await db.scalars(stmt)).all())


async def verify_certificate(
    db: AsyncSession,
    *,
    certificate_code: str,
) -> CertificateVerifyRead:
    stmt = (
        select(Certificate)
        .options(
            joinedload(Certificate.user),
            joinedload(Certificate.course).joinedload(Course.instructor),
        )
        .where(Certificate.certificate_code == certificate_code)
    )
    cert = await db.scalar(stmt)
    if not cert:
        raise NotFoundError(
            "Certificate not found or invalid",
            code="CERTIFICATE_NOT_FOUND",
        )

    student_name = cert.user.full_name or cert.user.email
    instructor_name = cert.course.instructor.full_name if cert.course.instructor else None

    return CertificateVerifyRead(
        certificate_code=cert.certificate_code,
        student_name=student_name,
        course_title=cert.course.title,
        course_slug=cert.course.slug,
        instructor_name=instructor_name,
        issued_at=cert.issued_at,
        is_valid=True,
    )
