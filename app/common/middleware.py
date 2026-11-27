import logging
import time
from uuid import uuid4

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from app.core.config import settings
from app.core.logging import request_id_ctx_var
from app.core.sentry_agent import (
    CONVERSATION_ID_HEADER,
    bind_conversation_id,
    clear_conversation_id,
    clear_sentry_user,
)

logger = logging.getLogger("app.access")


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Attaches X-Request-ID and emits structured access logs for every request."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        request_id = request.headers.get("X-Request-ID") or str(uuid4())
        token = request_id_ctx_var.set(request_id)
        start = time.perf_counter()
        try:
            response = await call_next(request)
            duration_ms = round((time.perf_counter() - start) * 1000, 2)
            response.headers["X-Request-ID"] = request_id
            logger.info(
                "request completed",
                extra={
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": response.status_code,
                    "duration_ms": duration_ms,
                    "client_ip": request.client.host if request.client else "unknown",
                },
            )
            return response
        finally:
            request_id_ctx_var.reset(token)


class SentryAgentMiddleware(BaseHTTPMiddleware):
    """Binds a stable conversation ID to the Sentry scope for the request.

    Supported AI integrations create ``gen_ai`` spans on this scope, which lets
    Sentry group multiple turns and traces into one conversation.
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        conversation_id = bind_conversation_id(request.headers.get(CONVERSATION_ID_HEADER))
        try:
            return await call_next(request)
        finally:
            if conversation_id:
                clear_conversation_id()
            clear_sentry_user()


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Adds baseline HTTP security headers to all responses."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        if settings.ENVIRONMENT in ("production", "testing"):
            response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault(
            "Permissions-Policy", "geolocation=(), microphone=(), camera=()"
        )
        response.headers.setdefault("X-XSS-Protection", "0")
        return response
