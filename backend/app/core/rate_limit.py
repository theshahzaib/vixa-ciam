"""Rate limiting (sections 5.2 and 12) — enforced at the gateway edge.

A per-identity token-bucket limiter. Sensitive routes (login, register, OTP)
get a tighter budget to mitigate credential stuffing and OTP abuse, exactly as
the architecture calls for. The identity key is the authenticated subject when
present, otherwise the client IP.

In production this state lives in Redis so it is shared across gateway
instances; here it is in-process, with the same interface.
"""
from __future__ import annotations

import time
from collections import defaultdict

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from app.core.config import settings
from app.core.errors import _problem

_SENSITIVE_PREFIXES = ("/api/v1/auth/login", "/api/v1/auth/register",
                       "/api/v1/onboarding", "/api/v1/verification")

# Module-level so it can be inspected/reset (e.g. by tests). In production this
# is backed by Redis and shared across gateway instances.
_BUCKETS: dict[tuple[str, bool], "_Bucket"] = {}


def reset_buckets() -> None:
    _BUCKETS.clear()


class _Bucket:
    __slots__ = ("tokens", "updated", "capacity", "refill_per_sec")

    def __init__(self, capacity: int):
        self.capacity = float(capacity)
        self.tokens = float(capacity)
        self.refill_per_sec = capacity / 60.0
        self.updated = time.monotonic()

    def allow(self) -> bool:
        now = time.monotonic()
        self.tokens = min(self.capacity, self.tokens + (now - self.updated) * self.refill_per_sec)
        self.updated = now
        if self.tokens >= 1:
            self.tokens -= 1
            return True
        return False


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app):
        super().__init__(app)

    def _identity(self, request: Request) -> str:
        auth = request.headers.get("authorization", "")
        if auth.startswith("Bearer "):
            return f"tok:{hash(auth)}"
        client = request.client
        return f"ip:{client.host if client else 'unknown'}"

    async def dispatch(self, request: Request, call_next):
        sensitive = request.url.path.startswith(_SENSITIVE_PREFIXES)
        key = (self._identity(request), sensitive)
        bucket = _BUCKETS.get(key)
        if bucket is None:
            cap = (settings.sensitive_rate_limit_per_minute if sensitive
                   else settings.rate_limit_per_minute)
            bucket = _BUCKETS[key] = _Bucket(cap)
        if not bucket.allow():
            resp = _problem(429, "Too Many Requests",
                            "Rate limit exceeded. Slow down and retry shortly.",
                            request.url.path)
            resp.headers["Retry-After"] = "5"
            return resp
        return await call_next(request)
