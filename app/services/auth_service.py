from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.errors import ConflictError, ForbiddenError, UnauthorizedError
from app.core.security import (
    REFRESH_TOKEN_TYPE,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.models.enums import UserRole
from app.models.token import RevokedToken
from app.models.user import User
from app.schemas.auth import LoginRequest, RegisterRequest, TokenPair


def _build_token_pair(user: User) -> TokenPair:
    return TokenPair(
        access_token=create_access_token(user.id, user.role),
        refresh_token=create_refresh_token(user.id, user.role),
    )


async def register_user(db: AsyncSession, payload: RegisterRequest) -> tuple[User, TokenPair]:
    existing = await db.scalar(select(User).where(User.email == payload.email))
    if existing:
        raise ConflictError("Email is already registered", code="EMAIL_ALREADY_EXISTS")

    user = User(
        email=payload.email,
        full_name=payload.full_name,
        hashed_password=hash_password(payload.password),
        role=UserRole.STUDENT.value,  # Always assigned server-side
        is_active=True,
    )
    db.add(user)
    try:
        await db.commit()
        await db.refresh(user)
    except IntegrityError as exc:
        await db.rollback()
        raise ConflictError("Email is already registered", code="EMAIL_ALREADY_EXISTS") from exc

    return user, _build_token_pair(user)


async def authenticate_user(db: AsyncSession, payload: LoginRequest) -> TokenPair:
    user = await db.scalar(select(User).where(User.email == payload.email))
    if not user or not verify_password(payload.password, user.hashed_password):
        raise UnauthorizedError("Invalid email or password", code="INVALID_CREDENTIALS")
    if not user.is_active:
        raise ForbiddenError("Account has been deactivated", code="ACCOUNT_INACTIVE")
    return _build_token_pair(user)


async def refresh_tokens(db: AsyncSession, refresh_token: str) -> TokenPair:
    claims = decode_token(refresh_token, expected_type=REFRESH_TOKEN_TYPE)
    jti = claims.get("jti")
    if jti:
        is_revoked = await db.scalar(select(RevokedToken.id).where(RevokedToken.jti == jti))
        if is_revoked:
            raise UnauthorizedError("Token has been revoked", code="TOKEN_REVOKED")

    try:
        user_id = int(claims["sub"])
    except (ValueError, TypeError) as exc:
        raise UnauthorizedError("Invalid token subject", code="INVALID_TOKEN") from exc

    user = await db.get(User, user_id)
    if not user:
        raise UnauthorizedError("User no longer exists", code="INVALID_TOKEN")
    if not user.is_active:
        raise ForbiddenError("Account has been deactivated", code="ACCOUNT_INACTIVE")

    # Rotate refresh token: revoke the old one
    if jti:
        exp = claims.get("exp")
        exp_dt = (
            datetime.fromtimestamp(exp, tz=UTC) if exp else datetime.now(UTC) + timedelta(days=7)
        )
        revoked = RevokedToken(
            jti=jti,
            token_type=REFRESH_TOKEN_TYPE,
            user_id=user.id,
            expires_at=exp_dt.replace(tzinfo=None),
        )
        db.add(revoked)
        await db.commit()

    return _build_token_pair(user)


async def logout_user(db: AsyncSession, refresh_token: str) -> None:
    claims = decode_token(refresh_token, expected_type=REFRESH_TOKEN_TYPE)
    jti = claims.get("jti")
    if not jti:
        return

    existing = await db.scalar(select(RevokedToken.id).where(RevokedToken.jti == jti))
    if existing:
        return

    try:
        user_id: int | None = int(claims["sub"])
    except (ValueError, TypeError):
        user_id = None

    exp = claims.get("exp")
    exp_dt = datetime.fromtimestamp(exp, tz=UTC) if exp else datetime.now(UTC) + timedelta(days=7)
    revoked = RevokedToken(
        jti=jti,
        token_type=REFRESH_TOKEN_TYPE,
        user_id=user_id,
        expires_at=exp_dt.replace(tzinfo=None),
    )
    db.add(revoked)
    await db.commit()
