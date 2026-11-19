from fastapi import APIRouter

from app.api.v1 import auth, courses, enrollments, health, progress, users

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(enrollments.router)
api_router.include_router(users.router)
api_router.include_router(courses.router)
api_router.include_router(progress.router)
