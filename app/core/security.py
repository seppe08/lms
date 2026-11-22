from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

import jwt
from pwdlib import PasswordHash

from app.common.errors import UnauthorizedError
from app.core.config import settings

_password_hash = PasswordHash.recommended()

ACCESS_TOKEN_TYPE = "access"
REFRESH_TOKEN_TYPE = "refresh"


def hash_password(password: str) -> str:
    return _password_hash.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    return _password_hash.verify(password, hashed)


def _create_token(
    subject: str,
    role: str,
    token_type: str,
    expires_delta: timedelta,
) -> str:
    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        "sub": subject,
        "role": role,
        "type": token_type,
        "jti": str(uuid4()),
        "iat": now,
        "exp": now + expires_delta,
    }
    return jwt.encode(
        payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM
    )


def create_access_token(
    user_id: int, role: str, expires_delta: timedelta | None = None
) -> str:
    delta = expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    return _create_token(
        subject=str(user_id),
        role=role,
        token_type=ACCESS_TOKEN_TYPE,
        expires_delta=delta,
    )


def create_refresh_token(
    user_id: int, role: str, expires_delta: timedelta | None = None
) -> str:
    delta = expires_delta or timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    return _create_token(
        subject=str(user_id),
        role=role,
        token_type=REFRESH_TOKEN_TYPE,
        expires_delta=delta,
    )


def decode_token(token: str, expected_type: str = ACCESS_TOKEN_TYPE) -> dict[str, Any]:
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
    except jwt.ExpiredSignatureError as exc:
        raise UnauthorizedError("Token has expired", code="TOKEN_EXPIRED") from exc
    except jwt.InvalidTokenError as exc:
        raise UnauthorizedError(
            "Invalid authentication token", code="INVALID_TOKEN"
        ) from exc

    if payload.get("type") != expected_type:
        raise UnauthorizedError(
            f"Invalid token type; expected {expected_type} token",
            code="INVALID_TOKEN_TYPE",
        )
    if not payload.get("sub"):
        raise UnauthorizedError("Token missing subject", code="INVALID_TOKEN")
    return payload
