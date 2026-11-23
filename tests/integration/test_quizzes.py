from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import CourseStatus, User
from tests.factories import create_course_record, create_module_record


async def test_quiz_lifecycle_and_grading(
    client: AsyncClient,
    db_session: AsyncSession,
    student_user: User,
    student_headers: dict[str, str],
    instructor_user: User,
    instructor_headers: dict[str, str],
    other_instructor_headers: dict[str, str],
) -> None:
    # 1. Setup course and module
    course = await create_course_record(
        db_session,
        instructor=instructor_user,
        title="Async Python Deep Dive",
        status=CourseStatus.PUBLISHED,
    )
    module = await create_module_record(db_session, course=course, title="Coroutines")

    # Student cannot create quiz
    forbidden_quiz = await client.post(
        f"/api/v1/modules/{module.id}/quizzes",
        headers=student_headers,
        json={"title": "Hacked Quiz"},
    )
    assert forbidden_quiz.status_code == 403

    # Instructor creates quiz (passing score 75%, max 2 attempts)
    quiz_resp = await client.post(
        f"/api/v1/modules/{module.id}/quizzes",
        headers=instructor_headers,
        json={
            "title": "Asyncio Knowledge Check",
            "passing_score": 75,
            "max_attempts": 2,
        },
    )
    assert quiz_resp.status_code == 201
    quiz = quiz_resp.json()
    quiz_id = quiz["id"]
    assert quiz["passing_score"] == 75
    assert quiz["max_attempts"] == 2

    # Instructor adds Question 1: single choice (2 points)
    q1_resp = await client.post(
        f"/api/v1/quizzes/{quiz_id}/questions",
        headers=instructor_headers,
        json={
            "question_text": "What does async keyword define?",
            "question_type": "multiple_choice",
            "points": 2,
            "options": [
                {"option_text": "A coroutine function", "is_correct": True, "position": 1},
                {"option_text": "A synchronous generator", "is_correct": False, "position": 2},
                {"option_text": "A thread pool", "is_correct": False, "position": 3},
            ],
        },
    )
    assert q1_resp.status_code == 201
    q1 = q1_resp.json()
    q1_id = q1["id"]
    correct_opt_1 = next(o["id"] for o in q1["options"] if o["is_correct"])
    wrong_opt_1 = next(o["id"] for o in q1["options"] if not o["is_correct"])

    # Instructor adds Question 2: true/false (2 points)
    q2_resp = await client.post(
        f"/api/v1/quizzes/{quiz_id}/questions",
        headers=instructor_headers,
        json={
            "question_text": "await can be used outside async functions in Python.",
            "question_type": "true_false",
            "points": 2,
            "options": [
                {"option_text": "True", "is_correct": False, "position": 1},
                {"option_text": "False", "is_correct": True, "position": 2},
            ],
        },
    )
    assert q2_resp.status_code == 201
    q2 = q2_resp.json()
    q2_id = q2["id"]
    correct_opt_2 = next(o["id"] for o in q2["options"] if o["is_correct"])

    # Non-enrolled student cannot view or take quiz
    assert (
        await client.get(f"/api/v1/quizzes/{quiz_id}", headers=student_headers)
    ).status_code == 403

    # Student enrolls
    await client.post(f"/api/v1/courses/{course.id}/enroll", headers=student_headers)

    # Enrolled student views quiz: options DO NOT reveal is_correct
    student_quiz = (await client.get(f"/api/v1/quizzes/{quiz_id}", headers=student_headers)).json()
    assert "is_correct" not in student_quiz["questions"][0]["options"][0]

    # Instructor views quiz: options DO reveal is_correct
    inst_quiz = (await client.get(f"/api/v1/quizzes/{quiz_id}", headers=instructor_headers)).json()
    assert "is_correct" in inst_quiz["questions"][0]["options"][0]

    # Attempt 1: Student gets 1 right and 1 wrong -> 2/4 points = 50% (Failed)
    sub1_resp = await client.post(
        f"/api/v1/quizzes/{quiz_id}/submit",
        headers=student_headers,
        json={
            "answers": [
                {"question_id": q1_id, "selected_option_ids": [wrong_opt_1]},
                {"question_id": q2_id, "selected_option_ids": [correct_opt_2]},
            ]
        },
    )
    assert sub1_resp.status_code == 201
    sub1 = sub1_resp.json()
    assert sub1["score"] == 50.0
    assert sub1["points_scored"] == 2
    assert sub1["total_points"] == 4
    assert sub1["passed"] is False
    assert sub1["attempt_number"] == 1

    # Attempt 2: Student gets both right -> 4/4 points = 100% (Passed)
    sub2_resp = await client.post(
        f"/api/v1/quizzes/{quiz_id}/submit",
        headers=student_headers,
        json={
            "answers": [
                {"question_id": q1_id, "selected_option_ids": [correct_opt_1]},
                {"question_id": q2_id, "selected_option_ids": [correct_opt_2]},
            ]
        },
    )
    assert sub2_resp.status_code == 201
    sub2 = sub2_resp.json()
    assert sub2["score"] == 100.0
    assert sub2["points_scored"] == 4
    assert sub2["passed"] is True
    assert sub2["attempt_number"] == 2

    # Attempt 3: Exceeds max attempts (2) -> 400 MAX_ATTEMPTS_REACHED
    sub3_resp = await client.post(
        f"/api/v1/quizzes/{quiz_id}/submit",
        headers=student_headers,
        json={"answers": []},
    )
    assert sub3_resp.status_code == 400
    assert sub3_resp.json()["error"]["code"] == "MAX_ATTEMPTS_REACHED"

    # List submissions: student sees their 2 attempts
    subs_resp = await client.get(f"/api/v1/quizzes/{quiz_id}/submissions", headers=student_headers)
    assert subs_resp.status_code == 200
    assert len(subs_resp.json()) == 2

    # Cross-instructor IDOR protection: other instructor cannot update or delete quiz/question
    assert (
        await client.patch(
            f"/api/v1/quizzes/{quiz_id}",
            headers=other_instructor_headers,
            json={"title": "Hijacked Quiz"},
        )
    ).status_code == 403
    assert (
        await client.patch(
            f"/api/v1/quizzes/questions/{q1_id}",
            headers=other_instructor_headers,
            json={"question_text": "Hijacked Question"},
        )
    ).status_code == 403
    assert (
        await client.delete(
            f"/api/v1/quizzes/questions/{q1_id}",
            headers=other_instructor_headers,
        )
    ).status_code == 403
    assert (
        await client.delete(
            f"/api/v1/quizzes/{quiz_id}",
            headers=other_instructor_headers,
        )
    ).status_code == 403

    # Owner instructor updates quiz and question
    patched_quiz = await client.patch(
        f"/api/v1/quizzes/{quiz_id}",
        headers=instructor_headers,
        json={"title": "Updated Asyncio Quiz"},
    )
    assert patched_quiz.status_code == 200
    assert patched_quiz.json()["title"] == "Updated Asyncio Quiz"

    patched_q = await client.patch(
        f"/api/v1/quizzes/questions/{q1_id}",
        headers=instructor_headers,
        json={"question_text": "Updated Question Text"},
    )
    assert patched_q.status_code == 200
    assert patched_q.json()["question_text"] == "Updated Question Text"

    # Owner instructor deletes question 2
    del_q = await client.delete(f"/api/v1/quizzes/questions/{q2_id}", headers=instructor_headers)
    assert del_q.status_code == 204

    # Owner instructor deletes quiz
    del_quiz = await client.delete(f"/api/v1/quizzes/{quiz_id}", headers=instructor_headers)
    assert del_quiz.status_code == 204

    # Quiz now not found
    assert (
        await client.get(f"/api/v1/quizzes/{quiz_id}", headers=instructor_headers)
    ).status_code == 404
