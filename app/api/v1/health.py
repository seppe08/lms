from fastapi import APIRouter, status
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.api.deps import DbSession
from app.core.config import settings

router = APIRouter(tags=["health"])


@router.get(
    "/health",
    response_model=None,
    summary="API v1 health check",
    description="Returns service readiness status, database connectivity, and active environment.",
)
async def health_check(db: DbSession) -> dict[str, str] | JSONResponse:
    try:
        await db.execute(text("SELECT 1"))
    except Exception:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "status": "unhealthy",
                "service": settings.PROJECT_NAME,
                "environment": settings.ENVIRONMENT,
                "database": "unreachable",
            },
        )
    return {
        "status": "ok",
        "service": settings.PROJECT_NAME,
        "environment": settings.ENVIRONMENT,
        "database": "ok",
    }
