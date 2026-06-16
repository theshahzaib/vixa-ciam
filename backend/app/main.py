"""FastAPI application — the gateway/app composition root.

This is the single entry point for all API traffic (section 5.2): it mounts the
rate-limiting middleware, CORS, the structured error handlers and the versioned
v1 router. FastAPI gives us the speed, type validation and automatic OpenAPI
documentation the brief asks for out of the box (visit /docs).
"""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.container import container  # noqa: F401 — instantiates + wires services/workers
from app.core.errors import register_exception_handlers
from app.core.rate_limit import RateLimitMiddleware

app = FastAPI(
    title="ViXa CIAM Platform API",
    version="1.0.0",
    description=(
        "Customer Identity & Access Management for the Ost Infinity ecosystem. "
        "Identity-first, event-driven onboarding with an anti-corruption layer "
        "in front of the system of record."
    ),
    openapi_url=f"{settings.api_v1_prefix}/openapi.json",
    docs_url="/docs",
)

# CORS for the React SPA.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Gateway edge concerns.
app.add_middleware(RateLimitMiddleware)
register_exception_handlers(app)

# Versioned API surface.
app.include_router(api_router, prefix=settings.api_v1_prefix)


@app.get("/", tags=["system"], summary="Service banner")
def root():
    return {
        "service": settings.app_name,
        "version": "1.0.0",
        "docs": "/docs",
        "api": settings.api_v1_prefix,
    }
