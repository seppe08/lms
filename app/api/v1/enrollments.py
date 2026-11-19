from typing import Annotated

from fastapi import APIRouter, Query, status

from app.api.deps import CurrentUser, DbSession, PaginationDep
from app.common.pagination import PaginatedResponse
from app.models.enums import EnrollmentStatus
from app.schemas.enrollment import EnrollmentRead, EnrollmentWithCourseRead
from app.services import enrollment_service

router = APIRouter(tags=["enrollments"])


@router.post(
    "/courses/{course_id}/enroll",
    response_model=EnrollmentRead,
    status_code=status.HTTP_201_CREATED,
    summary="Enroll in a published course",
    description=(
        "Enrolls the authenticated user in a published course. "
        "Rejects unpublished courses (400) and duplicate active enrollments (409)."
    ),
)
async def enroll_in_course(
    course_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> EnrollmentRead:
    enrollment = await enrollment_service.enroll_in_course(
        db,
        course_id=course_id,
        actor=current_user,
    )
    return EnrollmentRead.model_validate(enrollment)


@router.delete(
    "/courses/{course_id}/enroll",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Unenroll from a course",
    description="Marks the authenticated user's active enrollment in the course as `dropped`.",
)
async def unenroll_from_course(
    course_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> None:
    await enrollment_service.unenroll_from_course(
        db,
        course_id=course_id,
        actor=current_user,
    )


@router.get(
    "/users/me/enrollments",
    response_model=PaginatedResponse[EnrollmentWithCourseRead],
    summary="List current user's enrollments",
    description="Returns a paginated list of the authenticated user's enrolled courses.",
)
async def list_my_enrollments(
    db: DbSession,
    current_user: CurrentUser,
    pagination: PaginationDep,
    enrollment_status: Annotated[
        EnrollmentStatus | None,
        Query(
            alias="status",
            description="Filter by enrollment status (`active` or `dropped`)",
        ),
    ] = EnrollmentStatus.ACTIVE,
) -> PaginatedResponse[EnrollmentWithCourseRead]:
    enrollments, total = await enrollment_service.list_user_enrollments(
        db,
        user_id=current_user.id,
        page=pagination.page,
        per_page=pagination.per_page,
        status=enrollment_status,
    )
    return PaginatedResponse.create(
        items=[EnrollmentWithCourseRead.model_validate(e) for e in enrollments],
        total=total,
        page=pagination.page,
        per_page=pagination.per_page,
    )
