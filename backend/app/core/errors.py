"""Error handling — a consistent, machine-readable error contract.

Every error the platform returns follows RFC 7807 (``application/problem+json``)
so the frontend and any service-to-service caller can handle failures uniformly.
This is one of the API-layer enhancements called for in the brief (error
handling, response formats).
"""
from __future__ import annotations

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


class DomainError(Exception):
    """Base class for expected business-rule failures (maps to 4xx)."""

    status_code = 400
    error_type = "about:blank"
    title = "Bad Request"

    def __init__(self, detail: str, *, status_code: int | None = None):
        self.detail = detail
        if status_code is not None:
            self.status_code = status_code
        super().__init__(detail)


class NotFoundError(DomainError):
    status_code = 404
    title = "Not Found"


class ConflictError(DomainError):
    status_code = 409
    title = "Conflict"


class AuthError(DomainError):
    status_code = 401
    title = "Unauthorized"


class ForbiddenError(DomainError):
    status_code = 403
    title = "Forbidden"


class RateLimitError(DomainError):
    status_code = 429
    title = "Too Many Requests"


def _problem(status: int, title: str, detail: str, instance: str, **extra) -> JSONResponse:
    body = {"type": "about:blank", "title": title, "status": status, "detail": detail, "instance": instance}
    body.update(extra)
    return JSONResponse(status_code=status, content=body, media_type="application/problem+json")


def register_exception_handlers(app) -> None:
    @app.exception_handler(DomainError)
    async def _domain(request: Request, exc: DomainError):
        return _problem(exc.status_code, exc.title, exc.detail, str(request.url.path))

    @app.exception_handler(StarletteHTTPException)
    async def _http(request: Request, exc: StarletteHTTPException):
        return _problem(exc.status_code, exc.detail if isinstance(exc.detail, str) else "Error",
                        str(exc.detail), str(request.url.path))

    @app.exception_handler(RequestValidationError)
    async def _validation(request: Request, exc: RequestValidationError):
        return _problem(422, "Validation Error", "Request payload failed validation",
                        str(request.url.path), errors=exc.errors())
