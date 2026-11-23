from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import CourseStatus, User
from tests.factories import (
    create_course_record,
)


async def test_course_reviews_lifecycle(
    client: AsyncClient,
    db_session: AsyncSession,
    student_user: User,
    student_headers: dict[str, str],
    second_student_user: User,
    second_student_headers: dict[str, str],
    instructor_user: User,
    instructor_headers: dict[str, str],
    admin_headers: dict[str, str],
) -> None:
    # 1. Create published course
    course = await create_course_record(
        db_session,
        instructor=instructor_user,
        title="Modern Python Architecture",
        status=CourseStatus.PUBLISHED,
    )

    # Instructor cannot review own course
    inst_rev = await client.post(
        f"/api/v1/courses/{course.id}/reviews",
        headers=instructor_headers,
        json={"rating": 5, "comment": "Great course!"},
    )
    assert inst_rev.status_code == 403
    assert inst_rev.json()["error"]["code"] == "INSTRUCTOR_CANNOT_REVIEW"

    # Non-enrolled student cannot review
    unenroll_rev = await client.post(
        f"/api/v1/courses/{course.id}/reviews",
        headers=student_headers,
        json={"rating": 5, "comment": "Loved it"},
    )
    assert unenroll_rev.status_code == 403
    assert unenroll_rev.json()["error"]["code"] == "NOT_ENROLLED"

    # Enroll student 1
    enroll_resp = await client.post(f"/api/v1/courses/{course.id}/enroll", headers=student_headers)
    assert enroll_resp.status_code == 201

    # Student 1 creates review
    rev_resp = await client.post(
        f"/api/v1/courses/{course.id}/reviews",
        headers=student_headers,
        json={"rating": 5, "comment": "Exceptional course material."},
    )
    assert rev_resp.status_code == 201
    rev_data = rev_resp.json()
    assert rev_data["rating"] == 5
    assert rev_data["comment"] == "Exceptional course material."
    review_id = rev_data["id"]

    # Duplicate review fails with 409
    dup_rev = await client.post(
        f"/api/v1/courses/{course.id}/reviews",
        headers=student_headers,
        json={"rating": 4},
    )
    assert dup_rev.status_code == 409
    assert dup_rev.json()["error"]["code"] == "REVIEW_ALREADY_EXISTS"

    # Student 2 enrolls and creates 3-star review
    await client.post(f"/api/v1/courses/{course.id}/enroll", headers=second_student_headers)
    await client.post(
        f"/api/v1/courses/{course.id}/reviews",
        headers=second_student_headers,
        json={"rating": 3, "comment": "Good, but paced quickly."},
    )

    # Check rating summary: (5 + 3) / 2 = 4.0
    summary_resp = await client.get(f"/api/v1/courses/{course.id}/reviews/summary")
    assert summary_resp.status_code == 200
    summary = summary_resp.json()
    assert summary["average_rating"] == 4.0
    assert summary["review_count"] == 2

    # Check list reviews
    list_resp = await client.get(f"/api/v1/courses/{course.id}/reviews")
    assert list_resp.status_code == 200
    assert list_resp.json()["meta"]["total"] == 2

    # Student 2 cannot update Student 1's review
    hijack_resp = await client.patch(
        f"/api/v1/reviews/{review_id}",
        headers=second_student_headers,
        json={"rating": 1},
    )
    assert hijack_resp.status_code == 403

    # Student 1 updates own review
    patch_resp = await client.patch(
        f"/api/v1/reviews/{review_id}",
        headers=student_headers,
        json={"rating": 4, "comment": "Updated comment."},
    )
    assert patch_resp.status_code == 200
    assert patch_resp.json()["rating"] == 4
    assert patch_resp.json()["comment"] == "Updated comment."

    # Admin deletes review
    del_resp = await client.delete(f"/api/v1/reviews/{review_id}", headers=admin_headers)
    assert del_resp.status_code == 204

    # Now total reviews count is 1
    new_summary = (await client.get(f"/api/v1/courses/{course.id}/reviews/summary")).json()
    assert new_summary["review_count"] == 1
    assert new_summary["average_rating"] == 3.0
