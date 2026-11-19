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
