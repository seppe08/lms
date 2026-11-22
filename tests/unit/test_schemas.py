import pytest
from pydantic import ValidationError

from app.common.pagination import PaginatedResponse
from app.models.enums import LessonContentType
from app.schemas.auth import RegisterRequest
from app.schemas.course import LessonCreate, ReorderRequest


def test_register_schema_normalizes_email() -> None:
    req = RegisterRequest(
        email="  Ada@Example.COM ", full_name="Ada", password="Password1"
    )
    assert req.email == "ada@example.com"


def test_register_schema_rejects_weak_password() -> None:
    with pytest.raises(ValidationError):
        RegisterRequest(email="ada@example.com", password="weakpassword")


def test_lesson_create_validates_content_by_type() -> None:
    text_lesson = LessonCreate(
        title="Welcome",
        content_type=LessonContentType.TEXT,
        content="Hello world",
    )
    assert text_lesson.content == "Hello world"

    with pytest.raises(ValidationError):
        LessonCreate(title="Missing text", content_type=LessonContentType.TEXT)

    with pytest.raises(ValidationError):
        LessonCreate(title="Missing URL", content_type=LessonContentType.VIDEO)

    with pytest.raises(ValidationError):
        LessonCreate(
            title="Bad URL",
            content_type=LessonContentType.LINK,
            content_url="javascript:alert(1)",
        )


def test_reorder_request_rejects_duplicates() -> None:
    with pytest.raises(ValidationError):
        ReorderRequest(ordered_ids=[1, 2, 1])


def test_paginated_response_metadata() -> None:
    page1 = PaginatedResponse.create(items=["a", "b"], total=5, page=1, per_page=2)
    assert page1.meta.total_pages == 3
    assert page1.meta.has_next is True
    assert page1.meta.has_prev is False

    page3 = PaginatedResponse.create(items=["e"], total=5, page=3, per_page=2)
    assert page3.meta.has_next is False
    assert page3.meta.has_prev is True
