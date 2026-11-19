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
    try:
        user_id = int(claims["sub"])
    except (ValueError, TypeError) as exc:
        raise UnauthorizedError("Invalid token subject", code="INVALID_TOKEN") from exc

    user = await db.get(User, user_id)
    if not user:
        raise UnauthorizedError("User no longer exists", code="INVALID_TOKEN")
    if not user.is_active:
        raise ForbiddenError("Account has been deactivated", code="ACCOUNT_INACTIVE")

    return _build_token_pair(user)
