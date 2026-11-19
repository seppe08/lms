from typing import Annotated

from fastapi import APIRouter, Query, status

from app.api.deps import (
    CurrentUser,
    DbSession,
    InstructorOrAdminUser,
    OptionalCurrentUser,
    PaginationDep,
)
from app.common.pagination import PaginatedResponse
from app.models.enums import CourseStatus, EnrollmentStatus
from app.schemas.course import (
    CourseCreate,
    CourseDetailRead,
    CourseRead,
    CourseUpdate,
    LessonCreate,
    LessonRead,
    LessonUpdate,
    ModuleCreate,
    ModuleOutlineRead,
    ModuleRead,
    ModuleUpdate,
    ReorderRequest,
)
from app.schemas.enrollment import RosterStudentRead
from app.services import course_service, enrollment_service

router = APIRouter()


# ---------------------------------------------------------------------------
# Courses
# ---------------------------------------------------------------------------


@router.get(
    "/courses",
    response_model=PaginatedResponse[CourseRead],
    tags=["courses"],
    summary="List published courses",
    description=(
        "Public paginated catalog of published courses with optional search and instructor filter."
    ),
)
async def list_published_courses(
    db: DbSession,
    pagination: PaginationDep,
    search: Annotated[
        str | None,
        Query(max_length=100, description="Search title or description"),
    ] = None,
    instructor_id: Annotated[
        int | None,
        Query(ge=1, description="Filter by instructor ID"),
    ] = None,
) -> PaginatedResponse[CourseRead]:
    courses, total = await course_service.list_published_courses(
        db,
        page=pagination.page,
        per_page=pagination.per_page,
        search=search,
        instructor_id=instructor_id,
    )
    return PaginatedResponse.create(
        items=[CourseRead.model_validate(c) for c in courses],
        total=total,
        page=pagination.page,
        per_page=pagination.per_page,
    )


@router.get(
    "/courses/manage",
    response_model=PaginatedResponse[CourseRead],
    tags=["courses"],
    summary="List manageable courses (Instructor/Admin)",
    description=(
        "Returns all courses owned by the authenticated instructor (any status), "
        "or all courses in the system for administrators."
    ),
)
async def list_manageable_courses(
    db: DbSession,
    actor: InstructorOrAdminUser,
    pagination: PaginationDep,
    course_status: Annotated[
        CourseStatus | None,
        Query(alias="status", description="Filter by course status"),
    ] = None,
    search: Annotated[str | None, Query(max_length=100)] = None,
) -> PaginatedResponse[CourseRead]:
    courses, total = await course_service.list_manageable_courses(
        db,
        actor=actor,
        page=pagination.page,
        per_page=pagination.per_page,
        status=course_status,
        search=search,
    )
    return PaginatedResponse.create(
        items=[CourseRead.model_validate(c) for c in courses],
        total=total,
        page=pagination.page,
        per_page=pagination.per_page,
    )


@router.post(
    "/courses",
    response_model=CourseRead,
    status_code=status.HTTP_201_CREATED,
    tags=["courses"],
    summary="Create a new course",
    description="Creates a new draft course owned by the authenticated instructor or admin.",
)
async def create_course(
    payload: CourseCreate,
    db: DbSession,
    actor: InstructorOrAdminUser,
) -> CourseRead:
    course = await course_service.create_course(db, actor=actor, payload=payload)
    return CourseRead.model_validate(course)


@router.get(
    "/courses/{course_id}",
    response_model=CourseDetailRead,
    tags=["courses"],
    summary="Get course details and syllabus outline",
    description=(
        "Returns course metadata with ordered modules and lesson outlines. "
        "Lesson body content/URLs are omitted here and gated behind `/lessons/{lesson_id}`."
    ),
)
async def get_course(
    course_id: int,
    db: DbSession,
    actor: OptionalCurrentUser,
) -> CourseDetailRead:
    course = await course_service.get_course_detail(db, course_id=course_id, actor=actor)
    return CourseDetailRead.model_validate(course)


@router.patch(
    "/courses/{course_id}",
    response_model=CourseRead,
    tags=["courses"],
    summary="Update course metadata",
    description="Partially updates a course. Restricted to the course's instructor or an admin.",
)
async def update_course(
    course_id: int,
    payload: CourseUpdate,
    db: DbSession,
    actor: InstructorOrAdminUser,
) -> CourseRead:
    course = await course_service.update_course(
        db,
        course_id=course_id,
        actor=actor,
        payload=payload,
    )
    return CourseRead.model_validate(course)


@router.post(
    "/courses/{course_id}/publish",
    response_model=CourseRead,
    tags=["courses"],
    summary="Publish a course",
    description="Sets a course's status to `published` so students can discover and enroll in it.",
)
async def publish_course(
    course_id: int,
    db: DbSession,
    actor: InstructorOrAdminUser,
) -> CourseRead:
    course = await course_service.set_course_status(
        db,
        course_id=course_id,
        actor=actor,
        new_status=CourseStatus.PUBLISHED,
    )
    return CourseRead.model_validate(course)


@router.post(
    "/courses/{course_id}/unpublish",
    response_model=CourseRead,
    tags=["courses"],
    summary="Unpublish a course",
    description="Reverts a course's status back to `draft`.",
)
async def unpublish_course(
    course_id: int,
    db: DbSession,
    actor: InstructorOrAdminUser,
) -> CourseRead:
    course = await course_service.set_course_status(
        db,
        course_id=course_id,
        actor=actor,
        new_status=CourseStatus.DRAFT,
    )
    return CourseRead.model_validate(course)


@router.post(
    "/courses/{course_id}/archive",
    response_model=CourseRead,
    tags=["courses"],
    summary="Archive a course",
    description="Sets a course's status to `archived`, removing it from the public catalog.",
)
async def archive_course(
    course_id: int,
    db: DbSession,
    actor: InstructorOrAdminUser,
) -> CourseRead:
    course = await course_service.set_course_status(
        db,
        course_id=course_id,
        actor=actor,
        new_status=CourseStatus.ARCHIVED,
    )
    return CourseRead.model_validate(course)


@router.delete(
    "/courses/{course_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["courses"],
    summary="Delete a course",
    description="Deletes a course and cascades its modules, lessons, and enrollments.",
)
async def delete_course(
    course_id: int,
    db: DbSession,
    actor: InstructorOrAdminUser,
) -> None:
    await course_service.delete_course(db, course_id=course_id, actor=actor)


@router.get(
    "/courses/{course_id}/roster",
    response_model=PaginatedResponse[RosterStudentRead],
    tags=["enrollments"],
    summary="Get course student roster (Instructor/Admin)",
    description=(
        "Returns a paginated list of enrolled students along with each student's "
        "lesson completion counts and course completion percentage."
    ),
)
async def get_course_roster(
    course_id: int,
    db: DbSession,
    actor: InstructorOrAdminUser,
    pagination: PaginationDep,
    enrollment_status: Annotated[
        EnrollmentStatus | None,
        Query(
            alias="status",
            description="Filter enrollments by status (omit or pass null for all)",
        ),
    ] = EnrollmentStatus.ACTIVE,
) -> PaginatedResponse[RosterStudentRead]:
    roster, total = await enrollment_service.list_course_roster(
        db,
        course_id=course_id,
        actor=actor,
        page=pagination.page,
        per_page=pagination.per_page,
        status=enrollment_status,
    )
    return PaginatedResponse.create(
        items=roster,
        total=total,
        page=pagination.page,
        per_page=pagination.per_page,
    )


# ---------------------------------------------------------------------------
# Modules
# ---------------------------------------------------------------------------


@router.get(
    "/courses/{course_id}/modules",
    response_model=list[ModuleOutlineRead],
    tags=["modules"],
    summary="List ordered modules for a course",
    description="Returns all modules and lesson outlines for a visible course ordered by position.",
)
async def list_course_modules(
    course_id: int,
    db: DbSession,
    actor: OptionalCurrentUser,
) -> list[ModuleOutlineRead]:
    modules = await course_service.list_course_modules(db, course_id=course_id, actor=actor)
    return [ModuleOutlineRead.model_validate(m) for m in modules]


@router.post(
    "/courses/{course_id}/modules",
    response_model=ModuleRead,
    status_code=status.HTTP_201_CREATED,
    tags=["modules"],
    summary="Add a module to a course",
    description="Creates a new module inside a course. Appends to the end if position is omitted.",
)
async def create_module(
    course_id: int,
    payload: ModuleCreate,
    db: DbSession,
    actor: InstructorOrAdminUser,
) -> ModuleRead:
    module = await course_service.create_module(
        db,
        course_id=course_id,
        actor=actor,
        payload=payload,
    )
    return ModuleRead.model_validate(module)


@router.put(
    "/courses/{course_id}/modules/reorder",
    response_model=list[ModuleRead],
    tags=["modules"],
    summary="Reorder course modules",
    description="Reassigns sequential 1-indexed positions to all modules in the course.",
)
async def reorder_modules(
    course_id: int,
    payload: ReorderRequest,
    db: DbSession,
    actor: InstructorOrAdminUser,
) -> list[ModuleRead]:
    modules = await course_service.reorder_modules(
        db,
        course_id=course_id,
        actor=actor,
        ordered_ids=payload.ordered_ids,
    )
    return [ModuleRead.model_validate(m) for m in modules]


@router.patch(
    "/modules/{module_id}",
    response_model=ModuleRead,
    tags=["modules"],
    summary="Update a module",
    description="Updates a module's title or position. Restricted to course instructor or admin.",
)
async def update_module(
    module_id: int,
    payload: ModuleUpdate,
    db: DbSession,
    actor: InstructorOrAdminUser,
) -> ModuleRead:
    module = await course_service.update_module(
        db,
        module_id=module_id,
        actor=actor,
        payload=payload,
    )
    return ModuleRead.model_validate(module)


@router.delete(
    "/modules/{module_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["modules"],
    summary="Delete a module",
    description="Deletes a module and cascades its lessons.",
)
async def delete_module(
    module_id: int,
    db: DbSession,
    actor: InstructorOrAdminUser,
) -> None:
    await course_service.delete_module(db, module_id=module_id, actor=actor)


# ---------------------------------------------------------------------------
# Lessons
# ---------------------------------------------------------------------------


@router.post(
    "/modules/{module_id}/lessons",
    response_model=LessonRead,
    status_code=status.HTTP_201_CREATED,
    tags=["lessons"],
    summary="Add a lesson to a module",
    description="Creates a new text, video, or link lesson inside a module.",
)
async def create_lesson(
    module_id: int,
    payload: LessonCreate,
    db: DbSession,
    actor: InstructorOrAdminUser,
) -> LessonRead:
    lesson = await course_service.create_lesson(
        db,
        module_id=module_id,
        actor=actor,
        payload=payload,
    )
    return LessonRead.model_validate(lesson)


@router.put(
    "/modules/{module_id}/lessons/reorder",
    response_model=list[LessonRead],
    tags=["lessons"],
    summary="Reorder module lessons",
    description="Reassigns sequential 1-indexed positions to all lessons in the module.",
)
async def reorder_lessons(
    module_id: int,
    payload: ReorderRequest,
    db: DbSession,
    actor: InstructorOrAdminUser,
) -> list[LessonRead]:
    lessons = await course_service.reorder_lessons(
        db,
        module_id=module_id,
        actor=actor,
        ordered_ids=payload.ordered_ids,
    )
    return [LessonRead.model_validate(lesson) for lesson in lessons]


@router.get(
    "/lessons/{lesson_id}",
    response_model=LessonRead,
    tags=["lessons"],
    summary="Get full lesson content",
    description=(
        "Returns full lesson content and URL. Restricted to actively enrolled students, "
        "the course's instructor, or administrators."
    ),
)
async def get_lesson(
    lesson_id: int,
    db: DbSession,
    actor: CurrentUser,
) -> LessonRead:
    lesson = await course_service.get_lesson_content(db, lesson_id=lesson_id, actor=actor)
    return LessonRead.model_validate(lesson)


@router.patch(
    "/lessons/{lesson_id}",
    response_model=LessonRead,
    tags=["lessons"],
    summary="Update a lesson",
    description="Partially updates a lesson's fields. Restricted to course instructor or admin.",
)
async def update_lesson(
    lesson_id: int,
    payload: LessonUpdate,
    db: DbSession,
    actor: InstructorOrAdminUser,
) -> LessonRead:
    lesson = await course_service.update_lesson(
        db,
        lesson_id=lesson_id,
        actor=actor,
        payload=payload,
    )
    return LessonRead.model_validate(lesson)


@router.delete(
    "/lessons/{lesson_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["lessons"],
    summary="Delete a lesson",
    description="Deletes a lesson and cascades its completion progress records.",
)
async def delete_lesson(
    lesson_id: int,
    db: DbSession,
    actor: InstructorOrAdminUser,
) -> None:
    await course_service.delete_lesson(db, lesson_id=lesson_id, actor=actor)
