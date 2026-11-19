from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import CourseStatus, LessonContentType, User
from tests.factories import create_course_record, create_lesson_record, create_module_record


async def test_end_to_end_student_journey(
    client: AsyncClient,
    db_session: AsyncSession,
    instructor_user: User,
    instructor_headers: dict[str, str],
    admin_headers: dict[str, str],
) -> None:
    """End-to-end journey: register -> browse -> enroll -> view lessons -> complete -> progress."""
    # Setup published course with 2 lessons
    course = await create_course_record(
        db_session,
        instructor=instructor_user,
        title="Backend Engineering 101",
        status=CourseStatus.PUBLISHED,
    )
    module = await create_module_record(db_session, course=course, title="Week 1", position=1)
    lesson_1 = await create_lesson_record(
        db_session,
        module=module,
        title="HTTP Basics",
        content_type=LessonContentType.TEXT,
        content="Full HTTP lesson body.",
        position=1,
    )
    lesson_2 = await create_lesson_record(
        db_session,
        module=module,
        title="REST Video",
        content_type=LessonContentType.VIDEO,
        content=None,
        content_url="https://example.com/rest-video",
        position=2,
    )

    # 1. Student registers
    reg = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "journey.student@example.com",
            "full_name": "Journey Student",
            "password": "Password123",
        },
    )
    assert reg.status_code == 201
    token = reg.json()["tokens"]["access_token"]
    student_id = reg.json()["user"]["id"]
    headers = {"Authorization": f"Bearer {token}"}

    # 2. Student browses published courses
    catalog = await client.get("/api/v1/courses")
    assert catalog.status_code == 200
    assert any(item["id"] == course.id for item in catalog.json()["items"])

    # Before enrolling: lesson content and progress are BLOCKED for student (403)
    assert (await client.get(f"/api/v1/lessons/{lesson_1.id}", headers=headers)).status_code == 403
    assert (
        await client.post(f"/api/v1/lessons/{lesson_1.id}/complete", headers=headers)
    ).status_code == 403
    assert (
        await client.get(f"/api/v1/courses/{course.id}/progress", headers=headers)
    ).status_code == 403

    # Instructor and admin CAN view lesson content without enrolling
    inst_lesson = await client.get(f"/api/v1/lessons/{lesson_1.id}", headers=instructor_headers)
    assert inst_lesson.status_code == 200
    assert inst_lesson.json()["content"] == "Full HTTP lesson body."
    assert (
        await client.get(f"/api/v1/lessons/{lesson_1.id}", headers=admin_headers)
    ).status_code == 200

    # 3. Student enrolls
    enroll = await client.post(f"/api/v1/courses/{course.id}/enroll", headers=headers)
    assert enroll.status_code == 201
    assert enroll.json()["status"] == "active"

    # Duplicate active enrollment rejected with 409
    dup_enroll = await client.post(f"/api/v1/courses/{course.id}/enroll", headers=headers)
    assert dup_enroll.status_code == 409
    assert dup_enroll.json()["error"]["code"] == "ALREADY_ENROLLED"

    # "My courses" lists the enrolled course
    my_courses = await client.get("/api/v1/users/me/enrollments", headers=headers)
    assert my_courses.status_code == 200
    assert my_courses.json()["meta"]["total"] == 1
    assert my_courses.json()["items"][0]["course"]["id"] == course.id

    # 4. Enrolled student can read lesson content
    read_l1 = await client.get(f"/api/v1/lessons/{lesson_1.id}", headers=headers)
    assert read_l1.status_code == 200
    assert read_l1.json()["content"] == "Full HTTP lesson body."

    # 5. Complete lesson 1 -> 50% progress
    c1 = await client.post(f"/api/v1/lessons/{lesson_1.id}/complete", headers=headers)
    assert c1.status_code == 201
    assert c1.json()["course_progress"]["completion_percentage"] == 50.0
    assert c1.json()["course_progress"]["completed_lessons"] == 1
    assert c1.json()["course_progress"]["total_lessons"] == 2

    # Duplicate completion returns 409
    c1_dup = await client.post(f"/api/v1/lessons/{lesson_1.id}/complete", headers=headers)
    assert c1_dup.status_code == 409

    # Complete lesson 2 -> 100% progress
    c2 = await client.post(f"/api/v1/lessons/{lesson_2.id}/complete", headers=headers)
    assert c2.status_code == 201
    assert c2.json()["course_progress"]["completion_percentage"] == 100.0

    # Check progress endpoint directly
    prog = await client.get(f"/api/v1/courses/{course.id}/progress", headers=headers)
    assert prog.status_code == 200
    assert prog.json()["completion_percentage"] == 100.0
    assert set(prog.json()["completed_lesson_ids"]) == {lesson_1.id, lesson_2.id}

    # Instructor checks roster and sees 100% progress for the student
    roster = await client.get(f"/api/v1/courses/{course.id}/roster", headers=instructor_headers)
    assert roster.status_code == 200
    assert roster.json()["meta"]["total"] == 1
    entry = roster.json()["items"][0]
    assert entry["student"]["id"] == student_id
    assert entry["completion_percentage"] == 100.0

    # Unmark lesson 2 -> drops back to 50%
    unmark = await client.delete(f"/api/v1/lessons/{lesson_2.id}/complete", headers=headers)
    assert unmark.status_code == 204
    prog_after = await client.get(f"/api/v1/courses/{course.id}/progress", headers=headers)
    assert prog_after.json()["completion_percentage"] == 50.0

    # 6. Unenroll -> lesson content blocked again, re-enroll reactivates cleanly
    unenroll = await client.delete(f"/api/v1/courses/{course.id}/enroll", headers=headers)
    assert unenroll.status_code == 204
    assert (await client.get(f"/api/v1/lessons/{lesson_1.id}", headers=headers)).status_code == 403

    re_enroll = await client.post(f"/api/v1/courses/{course.id}/enroll", headers=headers)
    assert re_enroll.status_code == 201
    assert re_enroll.json()["status"] == "active"


async def test_enroll_unpublished_course_rejected_and_roster_authorization(
    client: AsyncClient,
    db_session: AsyncSession,
    instructor_user: User,
    student_user: User,
    student_headers: dict[str, str],
    second_student_headers: dict[str, str],
    instructor_headers: dict[str, str],
    other_instructor_headers: dict[str, str],
) -> None:
    draft_course = await create_course_record(
        db_session,
        instructor=instructor_user,
        title="Draft Course",
        status=CourseStatus.DRAFT,
    )
    resp = await client.post(
        f"/api/v1/courses/{draft_course.id}/enroll",
        headers=student_headers,
    )
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "COURSE_NOT_PUBLISHED"

    # Publish course and check roster/progress authorization
    await client.post(f"/api/v1/courses/{draft_course.id}/publish", headers=instructor_headers)
    await client.post(f"/api/v1/courses/{draft_course.id}/enroll", headers=student_headers)

    # Other instructor and students cannot view course roster
    assert (
        await client.get(
            f"/api/v1/courses/{draft_course.id}/roster",
            headers=other_instructor_headers,
        )
    ).status_code == 403
    assert (
        await client.get(
            f"/api/v1/courses/{draft_course.id}/roster",
            headers=student_headers,
        )
    ).status_code == 403

    # Student 2 cannot inspect Student 1's progress, but course instructor can
    assert (
        await client.get(
            f"/api/v1/courses/{draft_course.id}/progress",
            headers=second_student_headers,
            params={"user_id": student_user.id},
        )
    ).status_code == 403
    inst_view = await client.get(
        f"/api/v1/courses/{draft_course.id}/progress",
        headers=instructor_headers,
        params={"user_id": student_user.id},
    )
    assert inst_view.status_code == 200
    assert inst_view.json()["user_id"] == student_user.id
