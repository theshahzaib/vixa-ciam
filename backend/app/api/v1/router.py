"""API v1 aggregation router.

Versioning the API under ``/api/v1`` (an explicit API-layer recommendation from
the brief) lets the contract evolve without breaking existing clients: a future
``/api/v2`` can ship breaking changes side by side.
"""
from __future__ import annotations

from fastapi import APIRouter

from app.api.v1 import (admin_routes, auth_routes, onboarding_routes,
                        products_routes, system_routes)

api_router = APIRouter()
api_router.include_router(auth_routes.router)
api_router.include_router(onboarding_routes.router)
api_router.include_router(products_routes.router)
api_router.include_router(admin_routes.router)
api_router.include_router(system_routes.router)
