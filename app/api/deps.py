from collections.abc import AsyncGenerator, Callable
from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.errors import ForbiddenError, UnauthorizedError
from app.common.pagination import PaginationParams
from app.core.security import ACCESS_TOKEN_TYPE, decode_token
from app.db.session import SessionLocal
from app.models.enums import UserRole
from app.models.user import User

bearer_scheme = HTTPBearer(auto_error=False)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with SessionLocal() as session:
        yield session


DbSession = Annotated[AsyncSession, Depends(get_db)]
PaginationDep = Annotated[PaginationParams, Depends(PaginationParams)]


async def _resolve_user_from_credentials(
    credentials: HTTPAuthorizationCredentials | None,
    db: AsyncSession,
    *,
    required: bool,
) -> User | None:
    if credentials is None or not credentials.credentials:
        if required:
            raise UnauthorizedError(
                "Authentication credentials were not provided",
                code="MISSING_TOKEN",
            )
        return None

    claims = decode_token(credentials.credentials, expected_type=ACCESS_TOKEN_TYPE)
    try:
        user_id = int(claims["sub"])
    except (ValueError, TypeError) as exc:
        raise UnauthorizedError("Invalid token subject", code="INVALID_TOKEN") from exc

    user = await db.get(User, user_id)
    if not user:
        raise UnauthorizedError("User not found", code="INVALID_TOKEN")
    if not user.is_active:
        raise ForbiddenError("Account has been deactivated", code="ACCOUNT_INACTIVE")
    return user


async def get_current_user(
    db: DbSession,
    credentials: Annotated[
        HTTPAuthorizationCredentials | None, Depends(bearer_scheme)
    ] = None,
) -> User:
    user = await _resolve_user_from_credentials(credentials, db, required=True)
    assert user is not None
    return user


async def get_optional_current_user(
    db: DbSession,
    credentials: Annotated[
        HTTPAuthorizationCredentials | None, Depends(bearer_scheme)
    ] = None,
) -> User | None:
    return await _resolve_user_from_credentials(credentials, db, required=False)


CurrentUser = Annotated[User, Depends(get_current_user)]
OptionalCurrentUser = Annotated[User | None, Depends(get_optional_current_user)]


def require_roles(*allowed_roles: UserRole) -> Callable[[CurrentUser], User]:
    """Dependency factory enforcing RBAC based on the authenticated user's role."""
    allowed_values = {role.value for role in allowed_roles}

    async def _role_checker(current_user: CurrentUser) -> User:
        if current_user.role not in allowed_values:
            raise ForbiddenError(
                "You do not have permission to perform this action",
                code="INSUFFICIENT_ROLE",
            )
        return current_user

    return _role_checker


AdminUser = Annotated[User, Depends(require_roles(UserRole.ADMIN))]
InstructorOrAdminUser = Annotated[
    User,
    Depends(require_roles(UserRole.INSTRUCTOR, UserRole.ADMIN)),
]
