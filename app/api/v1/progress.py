from fastapi import APIRouter, Query, status

from app.api.deps import CurrentUser, DbSession
from app.schemas.progress import CourseProgressRead, LessonCompletionResponse
from app.services import progress_service

router = APIRouter(tags=["progress"])


@router.post(
    "/lessons/{lesson_id}/complete",
    response_model=LessonCompletionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Mark a lesson as complete",
    description=(
        "Records completion of a lesson for an actively enrolled user and returns "
        "the updated course completion percentage."
    ),
)
async def complete_lesson(
    lesson_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> LessonCompletionResponse:
    return await progress_service.mark_lesson_complete(
        db,
        lesson_id=lesson_id,
        actor=current_user,
    )


@router.delete(
    "/lessons/{lesson_id}/complete",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Unmark a lesson completion",
    description="Removes the completion record for a lesson for an actively enrolled user.",
)
async def uncomplete_lesson(
    lesson_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> None:
    await progress_service.unmark_lesson_complete(
        db,
        lesson_id=lesson_id,
        actor=current_user,
    )


@router.get(
    "/courses/{course_id}/progress",
    response_model=CourseProgressRead,
    summary="Get course completion progress",
    description=(
        "Returns completed lessons count, total lessons, completion percentage, "
        "and completed lesson IDs. Instructors/admins may inspect a specific student via `user_id`."
    ),
)
async def get_course_progress(
    course_id: int,
    db: DbSession,
    current_user: CurrentUser,
    user_id: int | None = Query(
        default=None,
        ge=1,
        description="Optional student user ID (course instructor or admin only)",
    ),
) -> CourseProgressRead:
    return await progress_service.get_course_progress(
        db,
        course_id=course_id,
        actor=current_user,
        target_user_id=user_id,
    )
