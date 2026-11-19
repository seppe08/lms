from datetime import datetime

from pydantic import BaseModel, ConfigDict


class LessonProgressRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    lesson_id: int
    completed_at: datetime


class CourseProgressRead(BaseModel):
    course_id: int
    user_id: int
    total_lessons: int
    completed_lessons: int
    completion_percentage: float
    completed_lesson_ids: list[int]


class LessonCompletionResponse(BaseModel):
    lesson_progress: LessonProgressRead
    course_progress: CourseProgressRead
