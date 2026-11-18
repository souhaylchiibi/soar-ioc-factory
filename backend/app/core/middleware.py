"""HTTP hardening: security headers + in-memory rate limiting.

The limiter is per-process (single uvicorn worker in this deployment). It is a
brute-force/abuse brake, not a distributed quota: with several workers, put
the limit in the reverse proxy instead (documented in docs/SECURITY.md).
"""
from __future__ import annotations

import time
from collections import defaultdict, deque
from threading import Lock

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Cross-Origin-Opener-Policy": "same-origin",
    "Permissions-Policy": "geolocation=(), camera=(), microphone=()",
    # API responses are JSON only; Swagger UI needs its CDN assets.
    "Cache-Control": "no-store",
}


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        for k, v in SECURITY_HEADERS.items():
            response.headers.setdefault(k, v)
        return response


class SlidingWindowLimiter:
    def __init__(self) -> None:
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = Lock()

    def hit(self, key: str, limit: int, window_s: float) -> tuple[bool, int]:
        """Record a hit. Returns (allowed, retry_after_seconds)."""
        now = time.monotonic()
        with self._lock:
            q = self._hits[key]
            while q and now - q[0] > window_s:
                q.popleft()
            if len(q) >= limit:
                return False, max(1, int(window_s - (now - q[0])) + 1)
            q.append(now)
            return True, 0

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()


limiter = SlidingWindowLimiter()


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Global per-IP budget + a much stricter one on the login endpoint."""

    def __init__(self, app, per_minute: int, login_per_minute: int) -> None:
        super().__init__(app)
        self.per_minute = per_minute
        self.login_per_minute = login_per_minute

    async def dispatch(self, request: Request, call_next) -> Response:
        ip = request.client.host if request.client else "unknown"
        path = request.url.path
        if path.endswith("/auth/login") and request.method == "POST":
            ok, retry = limiter.hit(f"login:{ip}", self.login_per_minute, 60)
        elif path.startswith("/api/"):
            ok, retry = limiter.hit(f"api:{ip}", self.per_minute, 60)
        else:
            ok, retry = True, 0
        if not ok:
            return JSONResponse(
                status_code=429,
                content={"detail": "Trop de requêtes, réessayez plus tard"},
                headers={"Retry-After": str(retry)},
            )
        return await call_next(request)
