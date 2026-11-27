from datetime import timedelta

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token
from app.models import User, UserRole
from tests.factories import create_user_record


async def test_health_endpoints(client: AsyncClient) -> None:
    root_resp = await client.get("/health")
    assert root_resp.status_code == 200
    assert root_resp.json() == {"status": "ok"}

    v1_resp = await client.get("/api/v1/health")
    assert v1_resp.status_code == 200
    body = v1_resp.json()
    assert body["status"] == "ok"
    assert body["environment"] == "testing"


async def test_register_sets_student_role_server_side_and_rejects_duplicate(
    client: AsyncClient,
) -> None:
    payload = {
        "email": "NewLearner@Example.com",
        "full_name": "New Learner",
        "password": "Password123",
        "role": "admin",  # Must be ignored by server
    }
    resp = await client.post("/api/v1/auth/register", json=payload)
    assert resp.status_code == 201
    data = resp.json()
    assert data["user"]["email"] == "newlearner@example.com"
    assert data["user"]["role"] == "student"
    assert "hashed_password" not in data["user"]
    assert data["tokens"]["access_token"]
    assert data["tokens"]["refresh_token"]

    dup = await client.post("/api/v1/auth/register", json=payload)
    assert dup.status_code == 409
    assert dup.json()["error"]["code"] == "EMAIL_ALREADY_EXISTS"


async def test_register_weak_password_returns_422_error_envelope(
    client: AsyncClient,
) -> None:
    resp = await client.post(
        "/api/v1/auth/register",
        json={"email": "weak@example.com", "password": "short"},
    )
    assert resp.status_code == 422
    err = resp.json()["error"]
    assert err["code"] == "VALIDATION_ERROR"
    assert err["details"]["fields"]


async def test_login_refresh_and_me_flow(client: AsyncClient, student_user: User) -> None:
    bad_login = await client.post(
        "/api/v1/auth/login",
        json={"email": student_user.email, "password": "WrongPassword1"},
    )
    assert bad_login.status_code == 401
    assert bad_login.json()["error"]["code"] == "INVALID_CREDENTIALS"

    login_resp = await client.post(
        "/api/v1/auth/login",
        json={"email": student_user.email, "password": "Password123"},
    )
    assert login_resp.status_code == 200
    tokens = login_resp.json()

    me_resp = await client.get(
        "/api/v1/users/me",
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
    )
    assert me_resp.status_code == 200
    assert me_resp.json()["email"] == student_user.email

    # Using access token on /refresh must fail
    wrong_type = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": tokens["access_token"]},
    )
    assert wrong_type.status_code == 401
    assert wrong_type.json()["error"]["code"] == "INVALID_TOKEN_TYPE"

    # Valid refresh succeeds
    refreshed = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": tokens["refresh_token"]},
    )
    assert refreshed.status_code == 200
    assert refreshed.json()["access_token"]

    # Reusing the rotated refresh token fails (Token Rotation)
    reused = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": tokens["refresh_token"]},
    )
    assert reused.status_code == 401
    assert reused.json()["error"]["code"] == "TOKEN_REVOKED"

    # Logout revokes the new refresh token
    new_refresh = refreshed.json()["refresh_token"]
    logout_resp = await client.post(
        "/api/v1/auth/logout",
        json={"refresh_token": new_refresh},
    )
    assert logout_resp.status_code == 204

    # Using the logged-out refresh token fails
    after_logout = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": new_refresh},
    )
    assert after_logout.status_code == 401
    assert after_logout.json()["error"]["code"] == "TOKEN_REVOKED"

    # Expired token fails
    expired = create_access_token(
        student_user.id, student_user.role, expires_delta=timedelta(seconds=-5)
    )
    expired_resp = await client.get(
        "/api/v1/users/me",
        headers={"Authorization": f"Bearer {expired}"},
    )
    assert expired_resp.status_code == 401
    assert expired_resp.json()["error"]["code"] == "TOKEN_EXPIRED"


async def test_update_own_profile(
    client: AsyncClient,
    student_headers: dict[str, str],
) -> None:
    resp = await client.patch(
        "/api/v1/users/me",
        headers=student_headers,
        json={"full_name": "Updated Student"},
    )
    assert resp.status_code == 200
    assert resp.json()["full_name"] == "Updated Student"


async def test_admin_user_management_and_rbac(
    client: AsyncClient,
    db_session: AsyncSession,
    student_user: User,
    student_headers: dict[str, str],
    instructor_headers: dict[str, str],
    admin_user: User,
    admin_headers: dict[str, str],
) -> None:
    # Student and instructor blocked from admin endpoints
    assert (await client.get("/api/v1/users", headers=student_headers)).status_code == 403
    assert (await client.get("/api/v1/users", headers=instructor_headers)).status_code == 403

    # Admin lists users with search/role filters
    list_resp = await client.get(
        "/api/v1/users",
        headers=admin_headers,
        params={"role": "student", "search": "student@"},
    )
    assert list_resp.status_code == 200
    body = list_resp.json()
    assert body["meta"]["total"] == 1
    assert body["items"][0]["id"] == student_user.id

    # Admin promotes user to instructor
    patch_resp = await client.patch(
        f"/api/v1/users/{student_user.id}",
        headers=admin_headers,
        json={"role": "instructor", "full_name": "Promoted Instructor"},
    )
    assert patch_resp.status_code == 200
    assert patch_resp.json()["role"] == "instructor"

    # Admin deactivates user -> user cannot login or call protected endpoints
    deact = await client.post(
        f"/api/v1/users/{student_user.id}/deactivate",
        headers=admin_headers,
    )
    assert deact.status_code == 200
    assert deact.json()["is_active"] is False

    blocked_login = await client.post(
        "/api/v1/auth/login",
        json={"email": student_user.email, "password": "Password123"},
    )
    assert blocked_login.status_code == 403
    assert blocked_login.json()["error"]["code"] == "ACCOUNT_INACTIVE"

    blocked_me = await client.get("/api/v1/users/me", headers=student_headers)
    assert blocked_me.status_code == 403

    # Admin reactivates user
    act = await client.post(
        f"/api/v1/users/{student_user.id}/activate",
        headers=admin_headers,
    )
    assert act.status_code == 200
    assert act.json()["is_active"] is True

    # Admin cannot deactivate, demote, or delete themselves
    self_deact = await client.post(
        f"/api/v1/users/{admin_user.id}/deactivate",
        headers=admin_headers,
    )
    assert self_deact.status_code == 400
    self_demote = await client.patch(
        f"/api/v1/users/{admin_user.id}",
        headers=admin_headers,
        json={"role": "student"},
    )
    assert self_demote.status_code == 400
    self_delete = await client.delete(
        f"/api/v1/users/{admin_user.id}",
        headers=admin_headers,
    )
    assert self_delete.status_code == 400

    # Admin deletes another user
    disposable = await create_user_record(
        db_session, email="temp@example.com", role=UserRole.STUDENT
    )
    del_resp = await client.delete(f"/api/v1/users/{disposable.id}", headers=admin_headers)
    assert del_resp.status_code == 204
    missing = await client.get(f"/api/v1/users/{disposable.id}", headers=admin_headers)
    assert missing.status_code == 404
