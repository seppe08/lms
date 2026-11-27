import asyncio
import math
import time
from collections import deque

from fastapi import Request

from app.common.errors import RateLimitExceededError
from app.core.config import settings


class SlidingWindowRateLimiter:
    """In-memory async-safe sliding-window rate limiter keyed by client identifier."""

    def __init__(self, max_requests: int, window_seconds: int) -> None:
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._buckets: dict[str, deque[float]] = {}
        self._lock = asyncio.Lock()

    async def check(self, key: str) -> tuple[bool, int]:
        now = time.monotonic()
        cutoff = now - self.window_seconds
        async with self._lock:
            bucket = self._buckets.get(key)
            if bucket is not None:
                while bucket and bucket[0] <= cutoff:
                    bucket.popleft()
                if not bucket:
                    del self._buckets[key]
                    bucket = None
            if bucket is not None and len(bucket) >= self.max_requests:
                retry_after = max(1, math.ceil(bucket[0] + self.window_seconds - now))
                return False, retry_after
            if bucket is None:
                bucket = deque()
                self._buckets[key] = bucket
            bucket.append(now)
            return True, 0

    def reset(self) -> None:
        self._buckets.clear()


auth_rate_limiter = SlidingWindowRateLimiter(
    max_requests=settings.AUTH_RATE_LIMIT_REQUESTS,
    window_seconds=settings.AUTH_RATE_LIMIT_WINDOW_SECONDS,
)


async def enforce_auth_rate_limit(request: Request) -> None:
    if not settings.RATE_LIMIT_ENABLED:
        return
    forwarded = request.headers.get("X-Forwarded-For") if settings.TRUST_PROXY_HEADERS else None
    client_ip = (
        forwarded.split(",")[0].strip()
        if forwarded
        else (request.client.host if request.client else "unknown")
    )
    key = f"{request.url.path}:{client_ip}"
    allowed, retry_after = await auth_rate_limiter.check(key)
    if not allowed:
        raise RateLimitExceededError(
            "Too many requests. Please try again later.",
            details={"retry_after_seconds": retry_after},
            headers={"Retry-After": str(retry_after)},
        )
