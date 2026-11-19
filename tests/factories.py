from sqlalchemy.ext.asyncio import AsyncSession

from app.common.utils import slugify
from app.core.security import hash_password
from app.models import (
    Course,
    CourseStatus,
    Enrollment,
    EnrollmentStatus,
    Lesson,
    LessonContentType,
    Module,
    User,
    UserRole,
)


async def create_user_record(
    db: AsyncSession,
    *,
    email: str,
    password: str = "Password123",
    full_name: str = "Test User",
    role: UserRole = UserRole.STUDENT,
    is_active: bool = True,
) -> User:
    user = User(
        email=email.lower(),
        full_name=full_name,
        hashed_password=hash_password(password),
        role=role.value,
        is_active=is_active,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def create_course_record(
    db: AsyncSession,
    *,
    instructor: User,
    title: str = "Python Fundamentals",
    slug: str | None = None,
    description: str = "Learn Python from scratch.",
    status: CourseStatus = CourseStatus.DRAFT,
) -> Course:
    course = Course(
        title=title,
        slug=slug or slugify(title),
        description=description,
        instructor_id=instructor.id,
        status=status.value,
    )
    db.add(course)
    await db.commit()
    await db.refresh(course)
    return course


async def create_module_record(
    db: AsyncSession,
    *,
    course: Course,
    title: str = "Module 1",
    position: int = 1,
) -> Module:
    module = Module(course_id=course.id, title=title, position=position)
    db.add(module)
    await db.commit()
    await db.refresh(module)
    return module


async def create_lesson_record(
    db: AsyncSession,
    *,
    module: Module,
    title: str = "Lesson 1",
    content_type: LessonContentType = LessonContentType.TEXT,
    content: str | None = "Secret lesson body content.",
    content_url: str | None = None,
    position: int = 1,
    duration_minutes: int | None = 15,
) -> Lesson:
    lesson = Lesson(
        module_id=module.id,
        title=title,
        content_type=content_type.value,
        content=content,
        content_url=content_url,
        position=position,
        duration_minutes=duration_minutes,
    )
    db.add(lesson)
    await db.commit()
    await db.refresh(lesson)
    return lesson


async def create_enrollment_record(
    db: AsyncSession,
    *,
    user: User,
    course: Course,
    status: EnrollmentStatus = EnrollmentStatus.ACTIVE,
) -> Enrollment:
    enrollment = Enrollment(
        user_id=user.id,
        course_id=course.id,
        status=status.value,
    )
    db.add(enrollment)
    await db.commit()
    await db.refresh(enrollment)
    return enrollment
