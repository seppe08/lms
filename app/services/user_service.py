from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.errors import BadRequestError, ForbiddenError, NotFoundError
from app.common.utils import escape_like_pattern
from app.models.enums import UserRole
from app.models.user import User
from app.schemas.user import AdminUserUpdate, UserUpdate


def _assert_admin(actor: User) -> None:
    if actor.role != UserRole.ADMIN.value:
        raise ForbiddenError("Administrator privileges are required")


async def get_user_by_id(db: AsyncSession, user_id: int) -> User:
    user = await db.get(User, user_id)
    if not user:
        raise NotFoundError("User not found", code="USER_NOT_FOUND")
    return user


async def list_users(
    db: AsyncSession,
    *,
    actor: User,
    page: int,
    per_page: int,
    role: UserRole | None = None,
    is_active: bool | None = None,
    search: str | None = None,
) -> tuple[list[User], int]:
    _assert_admin(actor)

    filters = []
    if role is not None:
        filters.append(User.role == role.value)
    if is_active is not None:
        filters.append(User.is_active.is_(is_active))
    if search:
        pattern = f"%{escape_like_pattern(search.strip())}%"
        filters.append(
            or_(
                User.email.ilike(pattern, escape="\\"),
                User.full_name.ilike(pattern, escape="\\"),
            )
        )

    count_stmt = select(func.count(User.id)).where(*filters)
    total = int(await db.scalar(count_stmt) or 0)

    offset = (page - 1) * per_page
    stmt = select(User).where(*filters).order_by(User.id.asc()).offset(offset).limit(per_page)
    rows = list((await db.scalars(stmt)).all())
    return rows, total


async def update_own_profile(db: AsyncSession, user: User, payload: UserUpdate) -> User:
    updates = payload.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(user, field, value)
    try:
        await db.commit()
        await db.refresh(user)
    except Exception:
        await db.rollback()
        raise
    return user


async def admin_update_user(
    db: AsyncSession,
    *,
    target_user_id: int,
    actor: User,
    payload: AdminUserUpdate,
) -> User:
    _assert_admin(actor)
    user = await get_user_by_id(db, target_user_id)
    updates = payload.model_dump(exclude_unset=True)

    if user.id == actor.id:
        if updates.get("is_active") is False:
            raise BadRequestError("Administrators cannot deactivate their own account")
        if "role" in updates and updates["role"] != UserRole.ADMIN:
            raise BadRequestError("Administrators cannot demote their own role")

    for field, value in updates.items():
        if field == "role" and value is not None:
            setattr(user, field, value.value)
        else:
            setattr(user, field, value)

    try:
        await db.commit()
        await db.refresh(user)
    except Exception:
        await db.rollback()
        raise
    return user


async def set_user_active(
    db: AsyncSession,
    *,
    target_user_id: int,
    actor: User,
    is_active: bool,
) -> User:
    _assert_admin(actor)
    user = await get_user_by_id(db, target_user_id)
    if user.id == actor.id and not is_active:
        raise BadRequestError("Administrators cannot deactivate their own account")

    user.is_active = is_active
    try:
        await db.commit()
        await db.refresh(user)
    except Exception:
        await db.rollback()
        raise
    return user


async def delete_user(db: AsyncSession, *, target_user_id: int, actor: User) -> None:
    _assert_admin(actor)
    user = await get_user_by_id(db, target_user_id)
    if user.id == actor.id:
        raise BadRequestError("Administrators cannot delete their own account")

    try:
        await db.delete(user)
        await db.commit()
    except Exception:
        await db.rollback()
        raise
