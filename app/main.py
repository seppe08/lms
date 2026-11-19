from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse

from app.api.v1.router import api_router
from app.common.errors import register_exception_handlers
from app.common.middleware import RequestIDMiddleware, SecurityHeadersMiddleware
from app.core.config import Settings, settings
from app.core.logging import configure_logging
from app.db.session import engine

OPENAPI_TAGS = [
    {"name": "health", "description": "Service liveness and readiness checks."},
    {"name": "auth", "description": "Registration, login, and JWT refresh token lifecycle."},
    {
        "name": "users",
        "description": "Self-service user profile and administrator user management.",
    },
    {"name": "courses", "description": "Course catalog, publishing workflow, and management."},
    {"name": "modules", "description": "Ordered course modules (sections)."},
    {"name": "lessons", "description": "Ordered module lessons with enrollment-gated content."},
    {"name": "enrollments", "description": "Course enrollment, unenrollment, and rosters."},
    {"name": "progress", "description": "Lesson completion tracking and course completion %."},
]


@asynccontextmanager
async def lifespan(_app: FastAPI):
    yield
    await engine.dispose()


def create_app(app_settings: Settings | None = None) -> FastAPI:
    cfg = app_settings or settings
    configure_logging(cfg.LOG_LEVEL)

    if cfg.SENTRY_DSN:
        import sentry_sdk

        sentry_sdk.init(dsn=cfg.SENTRY_DSN, environment=cfg.ENVIRONMENT)

    application = FastAPI(
        title=cfg.PROJECT_NAME,
        version="1.0.0",
        description=(
            "Production-grade Learning Management System (LMS) REST API featuring "
            "JWT authentication, role-based & ownership authorization, courses/modules/lessons, "
            "enrollments, and progress tracking."
        ),
        debug=cfg.DEBUG,
        openapi_tags=OPENAPI_TAGS,
        lifespan=lifespan,
    )

    application.add_middleware(SecurityHeadersMiddleware)
    application.add_middleware(RequestIDMiddleware)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=cfg.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
    )

    register_exception_handlers(application)
    application.include_router(api_router, prefix="/api/v1")

    @application.get("/", include_in_schema=False)
    async def root() -> RedirectResponse:
        return RedirectResponse(url="/docs")

    @application.get("/health", tags=["health"], summary="Root health check")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return application


app = create_app()
