from enum import StrEnum


class UserRole(StrEnum):
    STUDENT = "student"
    INSTRUCTOR = "instructor"
    ADMIN = "admin"


class CourseStatus(StrEnum):
    DRAFT = "draft"
    PUBLISHED = "published"
    ARCHIVED = "archived"


class LessonContentType(StrEnum):
    TEXT = "text"
    VIDEO = "video"
    LINK = "link"


class EnrollmentStatus(StrEnum):
    ACTIVE = "active"
    DROPPED = "dropped"
