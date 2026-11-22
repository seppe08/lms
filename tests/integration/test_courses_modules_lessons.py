from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import CourseStatus, User
from tests.factories import create_course_record


async def test_course_crud_publish_and_visibility(
    client: AsyncClient,
    student_headers: dict[str, str],
    instructor_headers: dict[str, str],
    other_instructor_headers: dict[str, str],
    admin_headers: dict[str, str],
) -> None:
    # Student cannot create a course
    forbidden = await client.post(
        "/api/v1/courses",
        headers=student_headers,
        json={"title": "Unauthorized Course"},
    )
    assert forbidden.status_code == 403

    # Instructor creates draft course
    create_resp = await client.post(
        "/api/v1/courses",
        headers=instructor_headers,
        json={
            "title": "FastAPI Mastery",
            "description": "End-to-end async API engineering.",
        },
    )
    assert create_resp.status_code == 201
    course = create_resp.json()
    course_id = course["id"]
    assert course["status"] == "draft"
    assert course["slug"] == "fastapi-mastery"

    # Creating another course with identical title auto-suffixes slug cleanly
    dup_title = await client.post(
        "/api/v1/courses",
        headers=instructor_headers,
        json={"title": "FastAPI Mastery"},
    )
    assert dup_title.status_code == 201
    assert dup_title.json()["slug"] == "fastapi-mastery-2"

    # Draft course is hidden from public catalog and public GET
    public_list = await client.get("/api/v1/courses")
    assert public_list.status_code == 200
    assert public_list.json()["meta"]["total"] == 0
    assert (await client.get(f"/api/v1/courses/{course_id}")).status_code == 404

    # Owner instructor and admin CAN view draft course
    assert (
        await client.get(f"/api/v1/courses/{course_id}", headers=instructor_headers)
    ).status_code == 200
    assert (
        await client.get(f"/api/v1/courses/{course_id}", headers=admin_headers)
    ).status_code == 200

    # Other instructor CANNOT update, publish, or delete instructor 1's course (IDOR protection)
    assert (
        await client.patch(
            f"/api/v1/courses/{course_id}",
            headers=other_instructor_headers,
            json={"title": "Hijacked"},
        )
    ).status_code == 403
    assert (
        await client.post(
            f"/api/v1/courses/{course_id}/publish",
            headers=other_instructor_headers,
        )
    ).status_code == 403
    assert (
        await client.delete(
            f"/api/v1/courses/{course_id}",
            headers=other_instructor_headers,
        )
    ).status_code == 403

    # Owner updates and publishes course
    patched = await client.patch(
        f"/api/v1/courses/{course_id}",
        headers=instructor_headers,
        json={"title": "FastAPI Production Mastery"},
    )
    assert patched.status_code == 200
    assert patched.json()["title"] == "FastAPI Production Mastery"

    published = await client.post(
        f"/api/v1/courses/{course_id}/publish",
        headers=instructor_headers,
    )
    assert published.status_code == 200
    assert published.json()["status"] == "published"

    # Now public catalog & search return it
    search_resp = await client.get("/api/v1/courses", params={"search": "Production"})
    assert search_resp.status_code == 200
    assert search_resp.json()["meta"]["total"] == 1
    assert search_resp.json()["items"][0]["id"] == course_id

    # Admin can unpublish, archive, and delete any course
    unpub = await client.post(
        f"/api/v1/courses/{course_id}/unpublish", headers=admin_headers
    )
    assert unpub.status_code == 200
    assert unpub.json()["status"] == "draft"

    arch = await client.post(
        f"/api/v1/courses/{course_id}/archive", headers=admin_headers
    )
    assert arch.status_code == 200
    assert arch.json()["status"] == "archived"

    deleted = await client.delete(f"/api/v1/courses/{course_id}", headers=admin_headers)
    assert deleted.status_code == 204


async def test_pagination_cap_and_manageable_courses(
    client: AsyncClient,
    db_session: AsyncSession,
    instructor_user: User,
    other_instructor_user: User,
    instructor_headers: dict[str, str],
    admin_headers: dict[str, str],
) -> None:
    for idx in range(5):
        await create_course_record(
            db_session,
            instructor=instructor_user,
            title=f"Course {idx}",
            slug=f"course-{idx}",
            status=CourseStatus.PUBLISHED,
        )
    await create_course_record(
        db_session,
        instructor=other_instructor_user,
        title="Other Draft",
        slug="other-draft",
        status=CourseStatus.DRAFT,
    )

    # Max cap (>100) rejected with 422
    too_large = await client.get("/api/v1/courses", params={"per_page": 101})
    assert too_large.status_code == 422

    # Valid pagination
    page2 = await client.get("/api/v1/courses", params={"page": 2, "per_page": 2})
    assert page2.status_code == 200
    data = page2.json()
    assert len(data["items"]) == 2
    assert data["meta"]["total"] == 5
    assert data["meta"]["total_pages"] == 3
    assert data["meta"]["has_next"] is True
    assert data["meta"]["has_prev"] is True

    # Instructor sees only own courses on /manage; admin sees all 6
    inst_manage = await client.get("/api/v1/courses/manage", headers=instructor_headers)
    assert inst_manage.status_code == 200
    assert inst_manage.json()["meta"]["total"] == 5

    admin_manage = await client.get("/api/v1/courses/manage", headers=admin_headers)
    assert admin_manage.status_code == 200
    assert admin_manage.json()["meta"]["total"] == 6


async def test_modules_and_lessons_nested_crud_and_reorder(
    client: AsyncClient,
    instructor_headers: dict[str, str],
    other_instructor_headers: dict[str, str],
) -> None:
    course_id = (
        await client.post(
            "/api/v1/courses",
            headers=instructor_headers,
            json={"title": "SQLAlchemy Deep Dive"},
        )
    ).json()["id"]

    # Create modules
    m1 = (
        await client.post(
            f"/api/v1/courses/{course_id}/modules",
            headers=instructor_headers,
            json={"title": "Basics"},
        )
    ).json()
    m2 = (
        await client.post(
            f"/api/v1/courses/{course_id}/modules",
            headers=instructor_headers,
            json={"title": "Async Sessions"},
        )
    ).json()
    assert m1["position"] == 1
    assert m2["position"] == 2

    # Other instructor cannot add modules or reorder
    assert (
        await client.post(
            f"/api/v1/courses/{course_id}/modules",
            headers=other_instructor_headers,
            json={"title": "Intruder"},
        )
    ).status_code == 403

    # Reorder modules
    reordered = await client.put(
        f"/api/v1/courses/{course_id}/modules/reorder",
        headers=instructor_headers,
        json={"ordered_ids": [m2["id"], m1["id"]]},
    )
    assert reordered.status_code == 200
    assert [m["id"] for m in reordered.json()] == [m2["id"], m1["id"]]
    assert [m["position"] for m in reordered.json()] == [1, 2]

    # Invalid reorder ID set fails with 400
    bad_reorder = await client.put(
        f"/api/v1/courses/{course_id}/modules/reorder",
        headers=instructor_headers,
        json={"ordered_ids": [m1["id"]]},
    )
    assert bad_reorder.status_code == 400

    # Create lessons inside m1 (text + video)
    l1 = (
        await client.post(
            f"/api/v1/modules/{m1['id']}/lessons",
            headers=instructor_headers,
            json={
                "title": "Engine Setup",
                "content_type": "text",
                "content": "Create an async engine with create_async_engine.",
                "duration_minutes": 10,
            },
        )
    ).json()
    l2 = (
        await client.post(
            f"/api/v1/modules/{m1['id']}/lessons",
            headers=instructor_headers,
            json={
                "title": "Video Walkthrough",
                "content_type": "video",
                "content_url": "https://example.com/video/1",
                "duration_minutes": 20,
            },
        )
    ).json()

    # Reorder lessons
    l_reordered = await client.put(
        f"/api/v1/modules/{m1['id']}/lessons/reorder",
        headers=instructor_headers,
        json={"ordered_ids": [l2["id"], l1["id"]]},
    )
    assert l_reordered.status_code == 200
    assert [lesson["id"] for lesson in l_reordered.json()] == [l2["id"], l1["id"]]

    # Update lesson & module
    patched_lesson = await client.patch(
        f"/api/v1/lessons/{l1['id']}",
        headers=instructor_headers,
        json={"title": "Async Engine Setup", "duration_minutes": 12},
    )
    assert patched_lesson.status_code == 200
    assert patched_lesson.json()["title"] == "Async Engine Setup"

    patched_mod = await client.patch(
        f"/api/v1/modules/{m1['id']}",
        headers=instructor_headers,
        json={"title": "Foundations"},
    )
    assert patched_mod.status_code == 200
    assert patched_mod.json()["title"] == "Foundations"

    # Publish and verify public course detail omits gated lesson body content/URL
    await client.post(
        f"/api/v1/courses/{course_id}/publish", headers=instructor_headers
    )
    detail = (await client.get(f"/api/v1/courses/{course_id}")).json()
    first_lesson_outline = detail["modules"][1]["lessons"][0]
    assert "content" not in first_lesson_outline
    assert "content_url" not in first_lesson_outline

    # Delete lesson and module
    assert (
        await client.delete(f"/api/v1/lessons/{l2['id']}", headers=instructor_headers)
    ).status_code == 204
    assert (
        await client.delete(f"/api/v1/modules/{m2['id']}", headers=instructor_headers)
    ).status_code == 204


async def test_course_slug_conflicts_module_listing_and_not_found_paths(
    client: AsyncClient,
    instructor_headers: dict[str, str],
) -> None:
    c1 = await client.post(
        "/api/v1/courses",
        headers=instructor_headers,
        json={"title": "Custom Slug Course", "slug": "custom-slug"},
    )
    assert c1.status_code == 201
    c1_id = c1.json()["id"]

    # Duplicate explicit slug returns 409
    dup = await client.post(
        "/api/v1/courses",
        headers=instructor_headers,
        json={"title": "Another Course", "slug": "custom-slug"},
    )
    assert dup.status_code == 409

    c2 = await client.post(
        "/api/v1/courses",
        headers=instructor_headers,
        json={"title": "Second Course", "slug": "second-slug"},
    )
    c2_id = c2.json()["id"]
    conflict_patch = await client.patch(
        f"/api/v1/courses/{c2_id}",
        headers=instructor_headers,
        json={"slug": "custom-slug"},
    )
    assert conflict_patch.status_code == 409

    # Create module + lesson, verify GET /courses/{id}/modules and lesson PATCH validation
    mod = (
        await client.post(
            f"/api/v1/courses/{c1_id}/modules",
            headers=instructor_headers,
            json={"title": "Intro", "position": 1},
        )
    ).json()
    mods_list = await client.get(
        f"/api/v1/courses/{c1_id}/modules",
        headers=instructor_headers,
    )
    assert mods_list.status_code == 200
    assert len(mods_list.json()) == 1

    lesson = (
        await client.post(
            f"/api/v1/modules/{mod['id']}/lessons",
            headers=instructor_headers,
            json={
                "title": "Text Lesson",
                "content_type": "text",
                "content": "Initial body",
                "position": 1,
            },
        )
    ).json()

    # Switching lesson to video without content_url returns 422
    bad_switch = await client.patch(
        f"/api/v1/lessons/{lesson['id']}",
        headers=instructor_headers,
        json={"content_type": "video"},
    )
    assert bad_switch.status_code == 422

    # Missing module/lesson/course IDs return 404
    assert (
        await client.patch(
            "/api/v1/modules/99999",
            headers=instructor_headers,
            json={"title": "Missing"},
        )
    ).status_code == 404
    assert (
        await client.get("/api/v1/lessons/99999", headers=instructor_headers)
    ).status_code == 404
    assert (
        await client.patch(
            "/api/v1/lessons/99999",
            headers=instructor_headers,
            json={"title": "Missing"},
        )
    ).status_code == 404
    assert (
        await client.put(
            f"/api/v1/modules/{mod['id']}/lessons/reorder",
            headers=instructor_headers,
            json={"ordered_ids": [99999]},
        )
    ).status_code == 400
