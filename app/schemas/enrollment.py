from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.enums import EnrollmentStatus
from app.schemas.course import CourseRead
from app.schemas.user import UserSummary


class EnrollmentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    course_id: int
    status: EnrollmentStatus
    enrolled_at: datetime
    created_at: datetime
    updated_at: datetime


class EnrollmentWithCourseRead(EnrollmentRead):
    course: CourseRead


class RosterStudentRead(BaseModel):
    enrollment_id: int
    student: UserSummary
    status: EnrollmentStatus
    enrolled_at: datetime
    completed_lessons: int
    total_lessons: int
    completion_percentage: float
