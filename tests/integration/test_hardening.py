from httpx import AsyncClient

from app.common.rate_limit import auth_rate_limiter
from app.core.config import settings


async def test_security_headers_and_request_id_propagation(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/health", headers={"X-Request-ID": "req-test-123"})
    assert resp.status_code == 200
    assert resp.headers["X-Request-ID"] == "req-test-123"
    assert resp.headers["X-Content-Type-Options"] == "nosniff"
    assert resp.headers["X-Frame-Options"] == "DENY"
    assert "Referrer-Policy" in resp.headers


async def test_consistent_error_envelope_for_404_and_401(client: AsyncClient) -> None:
    not_found = await client.get("/api/v1/courses/999999")
    assert not_found.status_code == 404
    body = not_found.json()
    assert set(body.keys()) == {"error"}
    assert set(body["error"].keys()) == {"code", "message", "details"}
    assert body["error"]["code"] == "COURSE_NOT_FOUND"

    unauth = await client.get("/api/v1/users/me")
    assert unauth.status_code == 401
    assert unauth.json()["error"]["code"] == "MISSING_TOKEN"


async def test_auth_rate_limiting_enforced(client: AsyncClient, monkeypatch) -> None:
    auth_rate_limiter.reset()
    monkeypatch.setattr(settings, "RATE_LIMIT_ENABLED", True)
    monkeypatch.setattr(auth_rate_limiter, "max_requests", 2)

    payload = {"email": "nobody@example.com", "password": "WrongPassword1"}
    r1 = await client.post("/api/v1/auth/login", json=payload)
    r2 = await client.post("/api/v1/auth/login", json=payload)
    r3 = await client.post("/api/v1/auth/login", json=payload)

    assert r1.status_code == 401
    assert r2.status_code == 401
    assert r3.status_code == 429
    assert r3.json()["error"]["code"] == "RATE_LIMIT_EXCEEDED"
    assert "Retry-After" in r3.headers


async def test_x_forwarded_for_ignored_when_trust_proxy_false(
    client: AsyncClient, monkeypatch
) -> None:
    auth_rate_limiter.reset()
    monkeypatch.setattr(settings, "RATE_LIMIT_ENABLED", True)
    monkeypatch.setattr(settings, "TRUST_PROXY_HEADERS", False)
    monkeypatch.setattr(auth_rate_limiter, "max_requests", 1)

    payload = {"email": "nobody@example.com", "password": "WrongPassword1"}
    r1 = await client.post(
        "/api/v1/auth/login", json=payload, headers={"X-Forwarded-For": "1.1.1.1"}
    )
    r2 = await client.post(
        "/api/v1/auth/login", json=payload, headers={"X-Forwarded-For": "2.2.2.2"}
    )
    assert r1.status_code == 401
    assert r2.status_code == 429


async def test_sentry_debug_disabled_in_production() -> None:
    from httpx import ASGITransport

    from app.core.config import Settings
    from app.main import create_app

    prod_app = create_app(
        Settings(
            _env_file=None,  # type: ignore[call-arg]
            ENVIRONMENT="production",
            DEBUG=False,
            DATABASE_URL="sqlite+aiosqlite:///:memory:",
            SECRET_KEY="a" * 32,
            JWT_SECRET_KEY="b" * 32,
        )
    )
    async with AsyncClient(transport=ASGITransport(app=prod_app), base_url="http://test") as ac:
        resp = await ac.get("/sentry-debug")
    assert resp.status_code == 404


async def test_health_v1_checks_database(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/health")
    assert resp.status_code == 200
    assert resp.json()["database"] == "ok"


async def test_health_v1_returns_503_when_db_unreachable() -> None:
    from httpx import ASGITransport

    from app.api.deps import get_db
    from app.main import create_app

    class BrokenSession:
        async def execute(self, *_args, **_kwargs):
            raise RuntimeError("DB down")

    app = create_app()

    async def _broken_db():
        yield BrokenSession()

    app.dependency_overrides[get_db] = _broken_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get("/api/v1/health")
    assert resp.status_code == 503
    assert resp.json()["status"] == "unhealthy"
    assert resp.json()["database"] == "unreachable"


async def test_refresh_and_logout_rate_limited(client: AsyncClient, monkeypatch) -> None:
    auth_rate_limiter.reset()
    monkeypatch.setattr(settings, "RATE_LIMIT_ENABLED", True)
    monkeypatch.setattr(auth_rate_limiter, "max_requests", 1)

    r1 = await client.post("/api/v1/auth/refresh", json={"refresh_token": "bad"})
    r2 = await client.post("/api/v1/auth/refresh", json={"refresh_token": "bad"})
    assert r1.status_code == 401
    assert r2.status_code == 429

    l1 = await client.post("/api/v1/auth/logout", json={"refresh_token": "bad"})
    l2 = await client.post("/api/v1/auth/logout", json={"refresh_token": "bad"})
    assert l1.status_code == 401
    assert l2.status_code == 429


async def test_reorder_rejects_duplicate_ids_and_search_escapes_wildcards(
    client: AsyncClient,
    db_session,
    instructor_user,
    instructor_headers: dict[str, str],
) -> None:
    from app.models import CourseStatus, LessonContentType
    from tests.factories import create_course_record, create_lesson_record, create_module_record

    course = await create_course_record(
        db_session,
        instructor=instructor_user,
        title="100% Python Basics",
        status=CourseStatus.PUBLISHED,
    )
    await create_course_record(
        db_session,
        instructor=instructor_user,
        title="Rust Systems",
        status=CourseStatus.PUBLISHED,
    )
    m1 = await create_module_record(db_session, course=course, title="M1", position=1)
    m2 = await create_module_record(db_session, course=course, title="M2", position=2)
    lsn1 = await create_lesson_record(
        db_session, module=m1, title="L1", content_type=LessonContentType.TEXT, position=1
    )
    lsn2 = await create_lesson_record(
        db_session, module=m1, title="L2", content_type=LessonContentType.TEXT, position=2
    )

    # Duplicate module IDs with same set -> 422
    bad_mod_reorder = await client.put(
        f"/api/v1/courses/{course.id}/modules/reorder",
        headers=instructor_headers,
        json={"ordered_ids": [m1.id, m1.id, m2.id]},
    )
    assert bad_mod_reorder.status_code == 422

    # Duplicate lesson IDs with same set -> 422
    bad_lsn_reorder = await client.put(
        f"/api/v1/modules/{m1.id}/lessons/reorder",
        headers=instructor_headers,
        json={"ordered_ids": [lsn1.id, lsn1.id, lsn2.id]},
    )
    assert bad_lsn_reorder.status_code == 422

    # Search for literal '%' should only match "100% Python Basics", not "Rust Systems"
    search_resp = await client.get("/api/v1/courses", params={"search": "%"})
    assert search_resp.status_code == 200
    titles = [c["title"] for c in search_resp.json()["items"]]
    assert titles == ["100% Python Basics"]
