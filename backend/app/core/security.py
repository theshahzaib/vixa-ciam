"""Security primitives — password hashing and the JWT token strategy.

Implements the token strategy from section 12:
  * short-lived access JWT carrying entitlement claims,
  * longer-lived rotating refresh token,
  * standard OIDC-style claims (iss, aud, sub, exp, iat, jti).
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import bcrypt
from jose import JWTError, jwt

from app.core.config import settings


# --------------------------------------------------------------------------- #
# Passwords (bcrypt directly — avoids the passlib/bcrypt 4.x detection bug)
# --------------------------------------------------------------------------- #
def hash_password(password: str) -> str:
    # bcrypt operates on the first 72 bytes; encode then hash.
    return bcrypt.hashpw(password.encode("utf-8")[:72], bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8")[:72], hashed.encode("utf-8"))
    except ValueError:
        return False


# --------------------------------------------------------------------------- #
# Tokens
# --------------------------------------------------------------------------- #
def _now() -> datetime:
    return datetime.now(timezone.utc)


def create_access_token(
    subject: str,
    *,
    roles: list[str],
    entitlements: list[str],
    extra: Optional[dict[str, Any]] = None,
) -> tuple[str, int]:
    """Mint a short-lived access token. Entitlement claims are stamped in by the
    Licensing service before the token is issued (section 6)."""
    ttl = settings.access_token_ttl_seconds
    payload: dict[str, Any] = {
        "iss": settings.jwt_issuer,
        "aud": settings.jwt_audience,
        "sub": subject,
        "iat": _now(),
        "exp": _now() + timedelta(seconds=ttl),
        "jti": uuid.uuid4().hex,
        "typ": "access",
        "roles": roles,
        "ent": entitlements,  # entitlement claims drive the gateway gate
    }
    if extra:
        payload.update(extra)
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm), ttl


def create_refresh_token(subject: str, *, family_id: Optional[str] = None) -> tuple[str, str]:
    """Rotating refresh token. ``family_id`` lets us detect token reuse and
    revoke a whole family if a stolen refresh token is replayed."""
    family = family_id or uuid.uuid4().hex
    payload = {
        "iss": settings.jwt_issuer,
        "aud": settings.jwt_audience,
        "sub": subject,
        "iat": _now(),
        "exp": _now() + timedelta(seconds=settings.refresh_token_ttl_seconds),
        "jti": uuid.uuid4().hex,
        "typ": "refresh",
        "fam": family,
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm), family


def decode_token(token: str, *, expected_type: Optional[str] = None) -> dict[str, Any]:
    """Validate signature, issuer, audience and expiry. Raises ``JWTError``."""
    claims = jwt.decode(
        token,
        settings.jwt_secret,
        algorithms=[settings.jwt_algorithm],
        audience=settings.jwt_audience,
        issuer=settings.jwt_issuer,
    )
    if expected_type and claims.get("typ") != expected_type:
        raise JWTError(f"expected {expected_type} token, got {claims.get('typ')}")
    return claims
