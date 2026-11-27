from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import CourseStatus, LessonContentType, User
from tests.factories import (
    create_course_record,
    create_lesson_record,
    create_module_record,
)


async def test_certificate_issuance_and_verification(
    client: AsyncClient,
    db_session: AsyncSession,
    student_user: User,
    student_headers: dict[str, str],
    instructor_user: User,
) -> None:
    # 1. Create course with 1 lesson
    course = await create_course_record(
        db_session,
        instructor=instructor_user,
        title="Distributed Systems with Python",
        status=CourseStatus.PUBLISHED,
    )
    module = await create_module_record(db_session, course=course, title="Overview")
    lesson = await create_lesson_record(
        db_session,
        module=module,
        title="Intro",
        content_type=LessonContentType.TEXT,
    )

    # Attempt certificate claim before enrolling -> 403
    unauth_claim = await client.post(
        f"/api/v1/courses/{course.id}/certificate",
        headers=student_headers,
    )
    assert unauth_claim.status_code == 403

    # Enroll
    await client.post(f"/api/v1/courses/{course.id}/enroll", headers=student_headers)

    # Attempt certificate claim before completion -> 400 COURSE_INCOMPLETE
    incomplete_claim = await client.post(
        f"/api/v1/courses/{course.id}/certificate",
        headers=student_headers,
    )
    assert incomplete_claim.status_code == 400
    assert incomplete_claim.json()["error"]["code"] == "COURSE_INCOMPLETE"

    # Mark lesson complete -> 100% progress
    await client.post(f"/api/v1/lessons/{lesson.id}/complete", headers=student_headers)

    # Claim certificate -> 201
    claim_resp = await client.post(
        f"/api/v1/courses/{course.id}/certificate",
        headers=student_headers,
    )
    assert claim_resp.status_code == 201
    cert = claim_resp.json()
    assert cert["certificate_code"].startswith("CERT-")
    code = cert["certificate_code"]

    # Duplicate claim returns existing certificate
    dup_claim = await client.post(
        f"/api/v1/courses/{course.id}/certificate",
        headers=student_headers,
    )
    assert dup_claim.status_code == 201
    assert dup_claim.json()["id"] == cert["id"]

    # Public verification of certificate
    verify_resp = await client.get(f"/api/v1/certificates/verify/{code}")
    assert verify_resp.status_code == 200
    verify_data = verify_resp.json()
    assert verify_data["certificate_code"] == code
    assert verify_data["course_title"] == course.title
    assert verify_data["student_email"] == student_user.email
    assert verify_data["is_valid"] is True

    # Invalid code returns 404
    bad_verify = await client.get("/api/v1/certificates/verify/CERT-NONEXISTENT")
    assert bad_verify.status_code == 404
    assert bad_verify.json()["error"]["code"] == "CERTIFICATE_NOT_FOUND"

    # User can list their earned certificates
    my_certs = await client.get("/api/v1/users/me/certificates", headers=student_headers)
    assert my_certs.status_code == 200
    assert len(my_certs.json()) == 1
    assert my_certs.json()[0]["certificate_code"] == code
