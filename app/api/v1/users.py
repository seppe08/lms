from typing import Annotated

from fastapi import APIRouter, Query, status

from app.api.deps import AdminUser, CurrentUser, DbSession, PaginationDep
from app.common.pagination import PaginatedResponse
from app.models.enums import UserRole
from app.schemas.user import AdminUserUpdate, UserRead, UserUpdate
from app.services import user_service

router = APIRouter(prefix="/users", tags=["users"])


@router.get(
    "/me",
    response_model=UserRead,
    summary="Get current user profile",
    description="Returns the authenticated user's profile.",
)
async def read_current_user(current_user: CurrentUser) -> UserRead:
    return UserRead.model_validate(current_user)


@router.patch(
    "/me",
    response_model=UserRead,
    summary="Update current user profile",
    description="Allows the authenticated user to update their own editable profile fields.",
)
async def update_current_user(
    payload: UserUpdate,
    current_user: CurrentUser,
    db: DbSession,
) -> UserRead:
    user = await user_service.update_own_profile(db, current_user, payload)
    return UserRead.model_validate(user)


@router.get(
    "",
    response_model=PaginatedResponse[UserRead],
    summary="List users (Admin)",
    description="Returns a paginated, filterable list of all users. Restricted to administrators.",
)
async def list_users(
    db: DbSession,
    admin: AdminUser,
    pagination: PaginationDep,
    role: Annotated[UserRole | None, Query(description="Filter by user role")] = None,
    is_active: Annotated[bool | None, Query(description="Filter by active status")] = None,
    search: Annotated[str | None, Query(max_length=100, description="Search email or name")] = None,
) -> PaginatedResponse[UserRead]:
    users, total = await user_service.list_users(
        db,
        actor=admin,
        page=pagination.page,
        per_page=pagination.per_page,
        role=role,
        is_active=is_active,
        search=search,
    )
    return PaginatedResponse.create(
        items=[UserRead.model_validate(u) for u in users],
        total=total,
        page=pagination.page,
        per_page=pagination.per_page,
    )


@router.get(
    "/{user_id}",
    response_model=UserRead,
    summary="Get user by ID (Admin)",
    description="Returns a single user's details. Restricted to administrators.",
)
async def get_user(user_id: int, db: DbSession, _admin: AdminUser) -> UserRead:
    user = await user_service.get_user_by_id(db, user_id)
    return UserRead.model_validate(user)


@router.patch(
    "/{user_id}",
    response_model=UserRead,
    summary="Update user (Admin)",
    description="Allows an administrator to update a user's name, role, or active status.",
)
async def admin_update_user(
    user_id: int,
    payload: AdminUserUpdate,
    db: DbSession,
    admin: AdminUser,
) -> UserRead:
    user = await user_service.admin_update_user(
        db,
        target_user_id=user_id,
        actor=admin,
        payload=payload,
    )
    return UserRead.model_validate(user)


@router.post(
    "/{user_id}/deactivate",
    response_model=UserRead,
    summary="Deactivate user (Admin)",
    description="Deactivates a user account so they can no longer authenticate.",
)
async def deactivate_user(user_id: int, db: DbSession, admin: AdminUser) -> UserRead:
    user = await user_service.set_user_active(
        db,
        target_user_id=user_id,
        actor=admin,
        is_active=False,
    )
    return UserRead.model_validate(user)


@router.post(
    "/{user_id}/activate",
    response_model=UserRead,
    summary="Activate user (Admin)",
    description="Re-activates a previously deactivated user account.",
)
async def activate_user(user_id: int, db: DbSession, admin: AdminUser) -> UserRead:
    user = await user_service.set_user_active(
        db,
        target_user_id=user_id,
        actor=admin,
        is_active=True,
    )
    return UserRead.model_validate(user)


@router.delete(
    "/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete user (Admin)",
    description="Permanently deletes a user account and cascades owned records.",
)
async def delete_user(user_id: int, db: DbSession, admin: AdminUser) -> None:
    await user_service.delete_user(db, target_user_id=user_id, actor=admin)
