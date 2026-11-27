from fastapi import APIRouter

from app.api.v1 import (
    auth,
    certificates,
    courses,
    enrollments,
    health,
    progress,
    quizzes,
    reviews,
    users,
)

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(enrollments.router)
api_router.include_router(users.router)
api_router.include_router(courses.router)
api_router.include_router(progress.router)
api_router.include_router(reviews.router)
api_router.include_router(certificates.router)
api_router.include_router(quizzes.router)
