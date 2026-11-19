from fastapi import APIRouter

from app.core.config import settings

router = APIRouter(tags=["health"])


@router.get(
    "/health",
    summary="API v1 health check",
    description="Returns service health status and active runtime environment.",
)
async def health_check() -> dict[str, str]:
    return {
        "status": "ok",
        "service": settings.PROJECT_NAME,
        "environment": settings.ENVIRONMENT,
    }
