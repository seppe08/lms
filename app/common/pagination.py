import math

from fastapi import Query
from pydantic import BaseModel, Field

DEFAULT_PAGE = 1
DEFAULT_PER_PAGE = 20
MAX_PER_PAGE = 100


class PaginationParams:
    """Reusable FastAPI dependency for page/per_page query parameters with max cap."""

    def __init__(
        self,
        page: int = Query(default=DEFAULT_PAGE, ge=1, description="Page number (1-indexed)"),
        per_page: int = Query(
            default=DEFAULT_PER_PAGE,
            ge=1,
            le=MAX_PER_PAGE,
            description=f"Items per page (1-{MAX_PER_PAGE})",
        ),
    ) -> None:
        self.page = page
        self.per_page = per_page

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.per_page


class PaginationMeta(BaseModel):
    page: int = Field(ge=1)
    per_page: int = Field(ge=1, le=MAX_PER_PAGE)
    total: int = Field(ge=0)
    total_pages: int = Field(ge=0)
    has_next: bool
    has_prev: bool


class PaginatedResponse[T](BaseModel):
    items: list[T]
    meta: PaginationMeta

    @classmethod
    def create(
        cls,
        *,
        items: list[T],
        total: int,
        page: int,
        per_page: int,
    ) -> "PaginatedResponse[T]":
        total_pages = math.ceil(total / per_page) if total > 0 else 0
        return cls(
            items=items,
            meta=PaginationMeta(
                page=page,
                per_page=per_page,
                total=total,
                total_pages=total_pages,
                has_next=page < total_pages,
                has_prev=page > 1 and total_pages > 0,
            ),
        )
