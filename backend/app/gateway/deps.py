"""Gateway dependencies (section 5.2) — what the API gateway enforces.

These FastAPI dependencies implement the gateway's job: validate the JWT and its
claims, and enforce the entitlement gate (can this user open this product?) and
RBAC role gate (is this user an admin?). Each navigation is authorised cheaply
against the claim already in the token — no database hit on the hot path
(section 11.2).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from fastapi import Depends, Header
from jose import JWTError

from app.core.errors import AuthError, ForbiddenError
from app.core.security import decode_token


@dataclass
class Principal:
    subject: str
    roles: list[str]
    entitlements: list[str]
    organisation_id: Optional[str]


def get_principal(authorization: str = Header(default="")) -> Principal:
    if not authorization.startswith("Bearer "):
        raise AuthError("Missing bearer token.")
    token = authorization.split(" ", 1)[1]
    try:
        claims = decode_token(token, expected_type="access")
    except JWTError:
        raise AuthError("Invalid or expired access token.")
    return Principal(
        subject=claims["sub"],
        roles=claims.get("roles", []),
        entitlements=claims.get("ent", []),
        organisation_id=claims.get("org"),
    )


def require_admin(principal: Principal = Depends(get_principal)) -> Principal:
    if "admin" not in principal.roles:
        raise ForbiddenError("Administrator role required for this operation.")
    return principal


def require_entitlement(product: str):
    """Dependency factory: the gateway entitlement gate for a given product."""
    def _checker(principal: Principal = Depends(get_principal)) -> Principal:
        if product not in principal.entitlements:
            raise ForbiddenError(f"Your organisation is not entitled to {product}.")
        return principal
    return _checker
