from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.user import UserSummary


class ReviewCreate(BaseModel):
    rating: int = Field(ge=1, le=5, description="Rating from 1 to 5 stars")
    comment: str | None = Field(
        default=None, max_length=1000, description="Optional review comment"
    )


class ReviewUpdate(BaseModel):
    rating: int | None = Field(default=None, ge=1, le=5, description="Updated rating 1 to 5")
    comment: str | None = Field(default=None, max_length=1000, description="Updated comment")


class ReviewRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    course_id: int
    user_id: int
    user: UserSummary | None = None
    rating: int
    comment: str | None
    created_at: datetime
    updated_at: datetime


class CourseRatingSummary(BaseModel):
    average_rating: float = Field(default=0.0, description="Mean star rating rounded to 2 decimals")
    review_count: int = Field(default=0, description="Total number of reviews")
