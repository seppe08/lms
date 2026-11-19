from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.enums import CourseStatus, LessonContentType
from app.schemas.user import UserSummary


def _validate_http_url(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    if not cleaned.startswith(("http://", "https://")):
        raise ValueError("content_url must start with http:// or https://")
    return cleaned


class CourseCreate(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "title": "Introduction to Python Backend Engineering",
                "description": "Build production REST APIs with FastAPI and PostgreSQL.",
            }
        }
    )

    title: str = Field(min_length=3, max_length=200)
    slug: str | None = Field(default=None, min_length=3, max_length=220, pattern=r"^[a-z0-9-]+$")
    description: str | None = Field(default=None, max_length=5000)


class CourseUpdate(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "title": "Advanced FastAPI Architecture",
                "description": "Updated course description.",
            }
        }
    )

    title: str | None = Field(default=None, min_length=3, max_length=200)
    slug: str | None = Field(default=None, min_length=3, max_length=220, pattern=r"^[a-z0-9-]+$")
    description: str | None = Field(default=None, max_length=5000)


class ModuleCreate(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={"example": {"title": "Getting Started", "position": 1}}
    )

    title: str = Field(min_length=2, max_length=200)
    position: int | None = Field(default=None, ge=1)


class ModuleUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=2, max_length=200)
    position: int | None = Field(default=None, ge=1)


class LessonCreate(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "title": "Installing Dependencies",
                "content_type": "text",
                "content": "Run uv sync to install project dependencies.",
                "position": 1,
                "duration_minutes": 10,
            }
        }
    )

    title: str = Field(min_length=2, max_length=200)
    content_type: LessonContentType
    content: str | None = Field(default=None, max_length=50000)
    content_url: str | None = Field(default=None, max_length=1000)
    position: int | None = Field(default=None, ge=1)
    duration_minutes: int | None = Field(default=None, ge=0, le=1440)

    @field_validator("content_url")
    @classmethod
    def check_content_url(cls, value: str | None) -> str | None:
        return _validate_http_url(value)

    @model_validator(mode="after")
    def validate_content_by_type(self) -> "LessonCreate":
        if self.content_type == LessonContentType.TEXT:
            if not self.content or not self.content.strip():
                raise ValueError("Text lessons require non-empty content")
        elif self.content_type in (LessonContentType.VIDEO, LessonContentType.LINK):
            if not self.content_url:
                raise ValueError(f"{self.content_type.value.capitalize()} lessons require a URL")
        return self


class LessonUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=2, max_length=200)
    content_type: LessonContentType | None = None
    content: str | None = Field(default=None, max_length=50000)
    content_url: str | None = Field(default=None, max_length=1000)
    position: int | None = Field(default=None, ge=1)
    duration_minutes: int | None = Field(default=None, ge=0, le=1440)

    @field_validator("content_url")
    @classmethod
    def check_content_url(cls, value: str | None) -> str | None:
        return _validate_http_url(value)


class ReorderRequest(BaseModel):
    """Ordered list of entity IDs defining the new 1-indexed sequence."""

    ordered_ids: list[int] = Field(min_length=1)

    @field_validator("ordered_ids")
    @classmethod
    def ensure_unique_ids(cls, value: list[int]) -> list[int]:
        if len(set(value)) != len(value):
            raise ValueError("ordered_ids must not contain duplicates")
        return value


class LessonOutlineRead(BaseModel):
    """Public-safe lesson summary that omits gated content and content_url."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    module_id: int
    title: str
    content_type: LessonContentType
    position: int
    duration_minutes: int | None = None


class LessonRead(LessonOutlineRead):
    """Full lesson details including content/URL for enrolled users, instructors, and admins."""

    content: str | None = None
    content_url: str | None = None
    created_at: datetime
    updated_at: datetime


class ModuleRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    course_id: int
    title: str
    position: int
    created_at: datetime
    updated_at: datetime


class ModuleOutlineRead(ModuleRead):
    lessons: list[LessonOutlineRead] = Field(default_factory=list)


class CourseRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    slug: str
    description: str | None = None
    instructor_id: int
    instructor: UserSummary | None = None
    status: CourseStatus
    created_at: datetime
    updated_at: datetime


class CourseDetailRead(CourseRead):
    modules: list[ModuleOutlineRead] = Field(default_factory=list)
