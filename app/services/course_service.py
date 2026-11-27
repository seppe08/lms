from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload

from app.common.errors import (
    BadRequestError,
    ConflictError,
    ForbiddenError,
    NotFoundError,
    ValidationError,
)
from app.common.utils import escape_like_pattern, slugify
from app.models.course import Course, Lesson, Module
from app.models.enrollment import Enrollment
from app.models.enums import CourseStatus, EnrollmentStatus, LessonContentType, UserRole
from app.models.user import User
from app.schemas.course import (
    CourseCreate,
    CourseUpdate,
    LessonCreate,
    LessonUpdate,
    ModuleCreate,
    ModuleUpdate,
)


def can_manage_course(course: Course, user: User) -> bool:
    return user.role == UserRole.ADMIN.value or course.instructor_id == user.id


def assert_can_manage_course(course: Course, user: User) -> None:
    if not can_manage_course(course, user):
        raise ForbiddenError(
            "Only the course instructor or an administrator can modify this course"
        )


def _assert_instructor_or_admin(actor: User) -> None:
    if actor.role not in (UserRole.INSTRUCTOR.value, UserRole.ADMIN.value):
        raise ForbiddenError("Instructor or administrator role is required")


async def _generate_unique_slug(
    db: AsyncSession,
    base_value: str,
    *,
    exclude_course_id: int | None = None,
) -> str:
    base_slug = slugify(base_value)[:200]
    candidate = base_slug
    suffix = 2
    while True:
        stmt = select(Course.id).where(Course.slug == candidate)
        if exclude_course_id is not None:
            stmt = stmt.where(Course.id != exclude_course_id)
        existing = await db.scalar(stmt)
        if existing is None:
            return candidate
        candidate = f"{base_slug}-{suffix}"
        suffix += 1


async def list_published_courses(
    db: AsyncSession,
    *,
    page: int,
    per_page: int,
    search: str | None = None,
    instructor_id: int | None = None,
) -> tuple[list[Course], int]:
    filters = [Course.status == CourseStatus.PUBLISHED.value]
    if instructor_id is not None:
        filters.append(Course.instructor_id == instructor_id)
    if search:
        pattern = f"%{escape_like_pattern(search.strip())}%"
        filters.append(
            or_(
                Course.title.ilike(pattern, escape="\\"),
                Course.description.ilike(pattern, escape="\\"),
            )
        )

    total = int(await db.scalar(select(func.count(Course.id)).where(*filters)) or 0)
    offset = (page - 1) * per_page
    stmt = (
        select(Course)
        .options(joinedload(Course.instructor))
        .where(*filters)
        .order_by(Course.created_at.desc(), Course.id.desc())
        .offset(offset)
        .limit(per_page)
    )
    items = list((await db.scalars(stmt)).unique().all())
    return items, total


async def list_manageable_courses(
    db: AsyncSession,
    *,
    actor: User,
    page: int,
    per_page: int,
    status: CourseStatus | None = None,
    search: str | None = None,
) -> tuple[list[Course], int]:
    _assert_instructor_or_admin(actor)

    filters = []
    if actor.role != UserRole.ADMIN.value:
        filters.append(Course.instructor_id == actor.id)
    if status is not None:
        filters.append(Course.status == status.value)
    if search:
        pattern = f"%{escape_like_pattern(search.strip())}%"
        filters.append(
            or_(
                Course.title.ilike(pattern, escape="\\"),
                Course.description.ilike(pattern, escape="\\"),
            )
        )

    total = int(await db.scalar(select(func.count(Course.id)).where(*filters)) or 0)
    offset = (page - 1) * per_page
    stmt = (
        select(Course)
        .options(joinedload(Course.instructor))
        .where(*filters)
        .order_by(Course.created_at.desc(), Course.id.desc())
        .offset(offset)
        .limit(per_page)
    )
    items = list((await db.scalars(stmt)).unique().all())
    return items, total


async def create_course(db: AsyncSession, *, actor: User, payload: CourseCreate) -> Course:
    _assert_instructor_or_admin(actor)

    if payload.slug:
        exists = await db.scalar(select(Course.id).where(Course.slug == payload.slug))
        if exists is not None:
            raise ConflictError("Course slug already exists", code="SLUG_ALREADY_EXISTS")
        slug = payload.slug
    else:
        slug = await _generate_unique_slug(db, payload.title)

    course = Course(
        title=payload.title.strip(),
        slug=slug,
        description=payload.description,
        instructor_id=actor.id,
        status=CourseStatus.DRAFT.value,
    )
    db.add(course)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise ConflictError("Course slug already exists", code="SLUG_ALREADY_EXISTS") from exc

    stmt = select(Course).options(joinedload(Course.instructor)).where(Course.id == course.id)
    return (await db.scalars(stmt)).one()


async def get_course_detail(
    db: AsyncSession,
    *,
    course_id: int,
    actor: User | None = None,
) -> Course:
    stmt = (
        select(Course)
        .options(
            joinedload(Course.instructor),
            selectinload(Course.modules).selectinload(Module.lessons),
        )
        .where(Course.id == course_id)
    )
    course = (await db.scalars(stmt)).unique().one_or_none()
    if not course:
        raise NotFoundError("Course not found", code="COURSE_NOT_FOUND")

    if course.status != CourseStatus.PUBLISHED.value:
        if actor is None or not can_manage_course(course, actor):
            raise NotFoundError("Course not found", code="COURSE_NOT_FOUND")
    return course


async def _get_course_for_write(db: AsyncSession, course_id: int, actor: User) -> Course:
    stmt = select(Course).options(joinedload(Course.instructor)).where(Course.id == course_id)
    course = (await db.scalars(stmt)).unique().one_or_none()
    if not course:
        raise NotFoundError("Course not found", code="COURSE_NOT_FOUND")
    assert_can_manage_course(course, actor)
    return course


async def update_course(
    db: AsyncSession,
    *,
    course_id: int,
    actor: User,
    payload: CourseUpdate,
) -> Course:
    course = await _get_course_for_write(db, course_id, actor)
    updates = payload.model_dump(exclude_unset=True)

    if "slug" in updates and updates["slug"] is not None:
        exists = await db.scalar(
            select(Course.id).where(Course.slug == updates["slug"], Course.id != course.id)
        )
        if exists is not None:
            raise ConflictError("Course slug already exists", code="SLUG_ALREADY_EXISTS")

    for field, value in updates.items():
        if field == "title" and value is not None:
            setattr(course, field, value.strip())
        else:
            setattr(course, field, value)

    try:
        await db.commit()
        await db.refresh(course)
    except IntegrityError as exc:
        await db.rollback()
        raise ConflictError("Course slug already exists", code="SLUG_ALREADY_EXISTS") from exc
    return course


async def set_course_status(
    db: AsyncSession,
    *,
    course_id: int,
    actor: User,
    new_status: CourseStatus,
) -> Course:
    course = await _get_course_for_write(db, course_id, actor)
    course.status = new_status.value
    try:
        await db.commit()
        await db.refresh(course)
    except Exception:
        await db.rollback()
        raise
    return course


async def delete_course(db: AsyncSession, *, course_id: int, actor: User) -> None:
    course = await _get_course_for_write(db, course_id, actor)
    try:
        await db.delete(course)
        await db.commit()
    except Exception:
        await db.rollback()
        raise


# ---------------------------------------------------------------------------
# Modules
# ---------------------------------------------------------------------------


async def list_course_modules(
    db: AsyncSession,
    *,
    course_id: int,
    actor: User | None = None,
) -> list[Module]:
    course = await get_course_detail(db, course_id=course_id, actor=actor)
    return list(course.modules)


async def create_module(
    db: AsyncSession,
    *,
    course_id: int,
    actor: User,
    payload: ModuleCreate,
) -> Module:
    course = await _get_course_for_write(db, course_id, actor)
    if payload.position is None:
        max_pos = await db.scalar(
            select(func.coalesce(func.max(Module.position), 0)).where(Module.course_id == course.id)
        )
        position = int(max_pos or 0) + 1
    else:
        position = payload.position

    module = Module(course_id=course.id, title=payload.title.strip(), position=position)
    db.add(module)
    try:
        await db.commit()
        await db.refresh(module)
    except Exception:
        await db.rollback()
        raise
    return module


async def _get_module_for_write(db: AsyncSession, module_id: int, actor: User) -> Module:
    stmt = select(Module).options(joinedload(Module.course)).where(Module.id == module_id)
    module = (await db.scalars(stmt)).unique().one_or_none()
    if not module:
        raise NotFoundError("Module not found", code="MODULE_NOT_FOUND")
    assert_can_manage_course(module.course, actor)
    return module


async def update_module(
    db: AsyncSession,
    *,
    module_id: int,
    actor: User,
    payload: ModuleUpdate,
) -> Module:
    module = await _get_module_for_write(db, module_id, actor)
    updates = payload.model_dump(exclude_unset=True)
    for field, value in updates.items():
        if field == "title" and value is not None:
            setattr(module, field, value.strip())
        else:
            setattr(module, field, value)
    try:
        await db.commit()
        await db.refresh(module)
    except Exception:
        await db.rollback()
        raise
    return module


async def reorder_modules(
    db: AsyncSession,
    *,
    course_id: int,
    actor: User,
    ordered_ids: list[int],
) -> list[Module]:
    course = await _get_course_for_write(db, course_id, actor)
    stmt = select(Module).where(Module.course_id == course.id).order_by(Module.position.asc())
    modules = list((await db.scalars(stmt)).all())
    existing_map = {m.id: m for m in modules}

    if len(ordered_ids) != len(existing_map) or set(ordered_ids) != set(existing_map.keys()):
        raise BadRequestError(
            "ordered_ids must include every module ID belonging to this course exactly once",
            code="INVALID_REORDER_IDS",
        )

    for index, mod_id in enumerate(ordered_ids, start=1):
        existing_map[mod_id].position = index

    try:
        await db.commit()
    except Exception:
        await db.rollback()
        raise

    refreshed = (
        await db.scalars(
            select(Module).where(Module.course_id == course.id).order_by(Module.position.asc())
        )
    ).all()
    return list(refreshed)


async def delete_module(db: AsyncSession, *, module_id: int, actor: User) -> None:
    module = await _get_module_for_write(db, module_id, actor)
    try:
        await db.delete(module)
        await db.commit()
    except Exception:
        await db.rollback()
        raise


# ---------------------------------------------------------------------------
# Lessons
# ---------------------------------------------------------------------------


async def create_lesson(
    db: AsyncSession,
    *,
    module_id: int,
    actor: User,
    payload: LessonCreate,
) -> Lesson:
    module = await _get_module_for_write(db, module_id, actor)
    if payload.position is None:
        max_pos = await db.scalar(
            select(func.coalesce(func.max(Lesson.position), 0)).where(Lesson.module_id == module.id)
        )
        position = int(max_pos or 0) + 1
    else:
        position = payload.position

    lesson = Lesson(
        module_id=module.id,
        title=payload.title.strip(),
        content_type=payload.content_type.value,
        content=payload.content,
        content_url=payload.content_url,
        position=position,
        duration_minutes=payload.duration_minutes,
    )
    db.add(lesson)
    try:
        await db.commit()
        await db.refresh(lesson)
    except Exception:
        await db.rollback()
        raise
    return lesson


async def get_lesson_content(db: AsyncSession, *, lesson_id: int, actor: User) -> Lesson:
    """Return full lesson content only to enrolled active students, course instructor, or admin."""
    stmt = (
        select(Lesson)
        .options(joinedload(Lesson.module).joinedload(Module.course))
        .where(Lesson.id == lesson_id)
    )
    lesson = (await db.scalars(stmt)).unique().one_or_none()
    if not lesson:
        raise NotFoundError("Lesson not found", code="LESSON_NOT_FOUND")

    course = lesson.module.course
    if can_manage_course(course, actor):
        return lesson

    if course.status != CourseStatus.PUBLISHED.value:
        raise ForbiddenError("You do not have access to this lesson")

    enrollment = await db.scalar(
        select(Enrollment).where(
            Enrollment.user_id == actor.id,
            Enrollment.course_id == course.id,
            Enrollment.status == EnrollmentStatus.ACTIVE.value,
        )
    )
    if not enrollment:
        raise ForbiddenError(
            "You must be enrolled in this course to access lesson content",
            code="ENROLLMENT_REQUIRED",
        )
    return lesson


async def _get_lesson_for_write(db: AsyncSession, lesson_id: int, actor: User) -> Lesson:
    stmt = (
        select(Lesson)
        .options(joinedload(Lesson.module).joinedload(Module.course))
        .where(Lesson.id == lesson_id)
    )
    lesson = (await db.scalars(stmt)).unique().one_or_none()
    if not lesson:
        raise NotFoundError("Lesson not found", code="LESSON_NOT_FOUND")
    assert_can_manage_course(lesson.module.course, actor)
    return lesson


async def update_lesson(
    db: AsyncSession,
    *,
    lesson_id: int,
    actor: User,
    payload: LessonUpdate,
) -> Lesson:
    lesson = await _get_lesson_for_write(db, lesson_id, actor)
    updates = payload.model_dump(exclude_unset=True)

    new_type = updates.get("content_type")
    effective_type = (
        new_type.value if isinstance(new_type, LessonContentType) else lesson.content_type
    )
    effective_content = updates.get("content", lesson.content)
    effective_url = updates.get("content_url", lesson.content_url)

    if effective_type == LessonContentType.TEXT.value:
        if not effective_content or not str(effective_content).strip():
            raise ValidationError("Text lessons require non-empty content")
    elif effective_type in (
        LessonContentType.VIDEO.value,
        LessonContentType.LINK.value,
    ):
        if not effective_url:
            raise ValidationError(f"{effective_type.capitalize()} lessons require a content_url")

    for field, value in updates.items():
        if field == "content_type" and isinstance(value, LessonContentType):
            setattr(lesson, field, value.value)
        elif field == "title" and value is not None:
            setattr(lesson, field, value.strip())
        else:
            setattr(lesson, field, value)

    try:
        await db.commit()
        await db.refresh(lesson)
    except Exception:
        await db.rollback()
        raise
    return lesson


async def reorder_lessons(
    db: AsyncSession,
    *,
    module_id: int,
    actor: User,
    ordered_ids: list[int],
) -> list[Lesson]:
    module = await _get_module_for_write(db, module_id, actor)
    stmt = select(Lesson).where(Lesson.module_id == module.id).order_by(Lesson.position.asc())
    lessons = list((await db.scalars(stmt)).all())
    existing_map = {lesson.id: lesson for lesson in lessons}

    if len(ordered_ids) != len(existing_map) or set(ordered_ids) != set(existing_map.keys()):
        raise BadRequestError(
            "ordered_ids must include every lesson ID belonging to this module exactly once",
            code="INVALID_REORDER_IDS",
        )

    for index, lsn_id in enumerate(ordered_ids, start=1):
        existing_map[lsn_id].position = index

    try:
        await db.commit()
    except Exception:
        await db.rollback()
        raise

    refreshed = (
        await db.scalars(
            select(Lesson).where(Lesson.module_id == module.id).order_by(Lesson.position.asc())
        )
    ).all()
    return list(refreshed)


async def delete_lesson(db: AsyncSession, *, lesson_id: int, actor: User) -> None:
    lesson = await _get_lesson_for_write(db, lesson_id, actor)
    try:
        await db.delete(lesson)
        await db.commit()
    except Exception:
        await db.rollback()
        raise
