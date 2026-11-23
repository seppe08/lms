from fastapi import APIRouter, status

from app.api.deps import CurrentUser, DbSession, PaginationDep
from app.common.pagination import PaginatedResponse
from app.schemas.review import (
    CourseRatingSummary,
    ReviewCreate,
    ReviewRead,
    ReviewUpdate,
)
from app.services import review_service

router = APIRouter(tags=["reviews"])


@router.post(
    "/courses/{course_id}/reviews",
    response_model=ReviewRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create course review",
    description=(
        "Allows an actively enrolled student to submit a rating (1-5) and comment for a course."
    ),
)
async def create_course_review(
    course_id: int,
    payload: ReviewCreate,
    db: DbSession,
    current_user: CurrentUser,
) -> ReviewRead:
    review = await review_service.create_review(
        db,
        course_id=course_id,
        actor=current_user,
        payload=payload,
    )
    return ReviewRead.model_validate(review)


@router.get(
    "/courses/{course_id}/reviews",
    response_model=PaginatedResponse[ReviewRead],
    summary="List course reviews",
    description="Public paginated list of reviews for a given course.",
)
async def list_course_reviews(
    course_id: int,
    db: DbSession,
    pagination: PaginationDep,
) -> PaginatedResponse[ReviewRead]:
    reviews, total = await review_service.list_course_reviews(
        db,
        course_id=course_id,
        page=pagination.page,
        per_page=pagination.per_page,
    )
    return PaginatedResponse.create(
        items=[ReviewRead.model_validate(r) for r in reviews],
        total=total,
        page=pagination.page,
        per_page=pagination.per_page,
    )


@router.get(
    "/courses/{course_id}/reviews/summary",
    response_model=CourseRatingSummary,
    summary="Get course rating summary",
    description="Returns the average star rating and total review count for a course.",
)
async def get_course_rating_summary(
    course_id: int,
    db: DbSession,
) -> CourseRatingSummary:
    return await review_service.get_course_rating_summary(db, course_id=course_id)


@router.patch(
    "/reviews/{review_id}",
    response_model=ReviewRead,
    summary="Update course review",
    description="Allows the author or an administrator to edit a review.",
)
async def update_review(
    review_id: int,
    payload: ReviewUpdate,
    db: DbSession,
    current_user: CurrentUser,
) -> ReviewRead:
    review = await review_service.update_review(
        db,
        review_id=review_id,
        actor=current_user,
        payload=payload,
    )
    return ReviewRead.model_validate(review)


@router.delete(
    "/reviews/{review_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete course review",
    description="Allows the author or an administrator to delete a review.",
)
async def delete_review(
    review_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> None:
    await review_service.delete_review(
        db,
        review_id=review_id,
        actor=current_user,
    )
