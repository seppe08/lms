from datetime import datetime

from pydantic import BaseModel, ConfigDict


class CertificateRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    certificate_code: str
    user_id: int
    course_id: int
    issued_at: datetime


class CertificateVerifyRead(BaseModel):
    certificate_code: str
    student_name: str
    student_email: str
    course_title: str
    course_slug: str
    instructor_name: str | None
    issued_at: datetime
    is_valid: bool = True
