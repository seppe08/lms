from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models.enums import UserRole


class UserUpdate(BaseModel):
    """Fields an authenticated user may update on their own profile."""

    model_config = ConfigDict(
        json_schema_extra={"example": {"full_name": "Ada Byron"}},
    )

    full_name: str | None = Field(default=None, min_length=1, max_length=100)


class AdminUserUpdate(BaseModel):
    """Fields an admin may update on any user."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "full_name": "Grace Hopper",
                "role": "instructor",
                "is_active": True,
            }
        }
    )

    full_name: str | None = Field(default=None, min_length=1, max_length=100)
    role: UserRole | None = None
    is_active: bool | None = None


class UserSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    full_name: str | None = None
    role: UserRole


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    full_name: str | None = None
    role: UserRole
    is_active: bool
    created_at: datetime
    updated_at: datetime
