from datetime import timedelta

import pytest
from pydantic import ValidationError as PydanticValidationError

from app.common.errors import UnauthorizedError
from app.common.rate_limit import SlidingWindowRateLimiter
from app.common.utils import (
    calculate_completion_percentage,
    slugify,
    validate_password_strength,
)
from app.core.config import Settings
from app.core.security import (
    ACCESS_TOKEN_TYPE,
    REFRESH_TOKEN_TYPE,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)


def test_password_hashing_and_verification() -> None:
    hashed = hash_password("StrongPass1")
    assert hashed != "StrongPass1"
    assert verify_password("StrongPass1", hashed) is True
    assert verify_password("WrongPass1", hashed) is False


def test_jwt_access_and_refresh_tokens() -> None:
    access = create_access_token(42, "instructor")
    claims = decode_token(access, expected_type=ACCESS_TOKEN_TYPE)
    assert claims["sub"] == "42"
    assert claims["role"] == "instructor"
    assert claims["type"] == ACCESS_TOKEN_TYPE

    refresh = create_refresh_token(42, "instructor")
    refresh_claims = decode_token(refresh, expected_type=REFRESH_TOKEN_TYPE)
    assert refresh_claims["sub"] == "42"
    assert refresh_claims["type"] == REFRESH_TOKEN_TYPE

    with pytest.raises(UnauthorizedError) as exc_info:
        decode_token(access, expected_type=REFRESH_TOKEN_TYPE)
    assert exc_info.value.code == "INVALID_TOKEN_TYPE"


def test_expired_jwt_token_rejected() -> None:
    expired = create_access_token(1, "student", expires_delta=timedelta(seconds=-10))
    with pytest.raises(UnauthorizedError) as exc_info:
        decode_token(expired, expected_type=ACCESS_TOKEN_TYPE)
    assert exc_info.value.code == "TOKEN_EXPIRED"


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Intro to FastAPI & SQLAlchemy!", "intro-to-fastapi-sqlalchemy"),
        ("  Python   3.12__Course  ", "python-312-course"),
        ("!!!", "course"),
    ],
)
def test_slugify(raw: str, expected: str) -> None:
    assert slugify(raw) == expected


@pytest.mark.parametrize(
    ("completed", "total", "expected"),
    [
        (0, 0, 0.0),
        (0, 4, 0.0),
        (1, 3, 33.33),
        (2, 4, 50.0),
        (4, 4, 100.0),
        (6, 4, 100.0),
    ],
)
def test_calculate_completion_percentage(completed: int, total: int, expected: float) -> None:
    assert calculate_completion_percentage(completed, total) == expected


@pytest.mark.parametrize(
    "bad_password",
    [
        "Short1",
        "alllowercase1",
        "ALLUPPERCASE1",
        "NoDigitsHere",
    ],
)
def test_password_strength_rejects_weak_passwords(bad_password: str) -> None:
    with pytest.raises(ValueError):
        validate_password_strength(bad_password)


async def test_sliding_window_rate_limiter() -> None:
    limiter = SlidingWindowRateLimiter(max_requests=2, window_seconds=60)
    assert (await limiter.check("ip1"))[0] is True
    assert (await limiter.check("ip1"))[0] is True
    allowed, retry_after = await limiter.check("ip1")
    assert allowed is False
    assert retry_after >= 1
    assert (await limiter.check("ip2"))[0] is True


def test_production_settings_enforces_hardening() -> None:
    with pytest.raises(PydanticValidationError):
        Settings(
            ENVIRONMENT="production",
            DEBUG=True,
            DATABASE_URL="postgresql+asyncpg://u:p@localhost/db",
            SECRET_KEY="a" * 32,
            JWT_SECRET_KEY="b" * 32,
        )

    with pytest.raises(PydanticValidationError):
        Settings(
            ENVIRONMENT="production",
            DEBUG=False,
            DATABASE_URL="postgresql+asyncpg://u:p@localhost/db",
            SECRET_KEY="short-key-under-32",
            JWT_SECRET_KEY="b" * 32,
        )
