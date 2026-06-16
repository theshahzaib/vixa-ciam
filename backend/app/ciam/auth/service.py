"""Auth service (section 5.3) — owns the digital identity and the token lifecycle.

Responsibilities: create the credential/principal, validate credentials on
login, issue the short-lived access JWT and the rotating refresh token, and
rotate refresh tokens with reuse detection. Entitlement claims are resolved by
the Licensing service and stamped in here at issue time.
"""
from __future__ import annotations

from typing import Optional

from jose import JWTError

from app.acl.anti_corruption import acl
from app.core.audit import audit_log
from app.core.errors import AuthError, ConflictError
from app.core.security import (create_access_token, create_refresh_token,
                               decode_token, hash_password, verify_password)
from app.domains.licensing.service import LicensingService
from app.repositories.stores import Identity, identities, sessions


class AuthService:
    def __init__(self, licensing: LicensingService) -> None:
        self._licensing = licensing

    # --- identity creation (used by the onboarding saga) ------------------- #
    def create_identity(self, *, email: str, password: str, full_name: str) -> Identity:
        if identities.get_by_email(email):
            raise ConflictError("An account with this email already exists.")
        identity = identities.create(
            email=email, password_hash=hash_password(password), full_name=full_name,
        )
        audit_log.record("identity.created", actor=identity.id, target=identity.email)
        return identity

    # --- login ------------------------------------------------------------- #
    def authenticate(self, email: str, password: str) -> Identity:
        identity = identities.get_by_email(email)
        if not identity or not verify_password(password, identity.password_hash):
            audit_log.record("login.failed", target=email)
            # Identical message for unknown-user and bad-password (no enumeration).
            raise AuthError("Invalid credentials.")
        return identity

    def issue_tokens(self, identity: Identity, organisation_id: Optional[str]) -> tuple[str, int, str]:
        """Resolve entitlements, stamp claims, mint access + refresh tokens."""
        entitlements = self._licensing.resolve_entitlements(organisation_id) if organisation_id else ["vixa_platform"]
        extra = {"org": organisation_id} if organisation_id else {}
        access, ttl = create_access_token(
            identity.id, roles=identity.roles, entitlements=entitlements, extra=extra,
        )
        refresh, family = create_refresh_token(identity.id)
        session = sessions.create(identity.id, family)
        # Remember the latest refresh jti for this family (rotation guard).
        claims = decode_token(refresh, expected_type="refresh")
        sessions.remember_refresh(family, claims["jti"])
        audit_log.record("login.success", actor=identity.id, target=session.id,
                         entitlements=entitlements)
        return access, ttl, refresh

    # --- refresh rotation with reuse detection ----------------------------- #
    def refresh(self, refresh_token: str, organisation_id: Optional[str]) -> tuple[str, int, str]:
        try:
            claims = decode_token(refresh_token, expected_type="refresh")
        except JWTError:
            raise AuthError("Invalid or expired refresh token.")
        family, jti, sub = claims["fam"], claims["jti"], claims["sub"]
        if not sessions.is_current_refresh(family, jti):
            # A non-current token from this family was replayed → likely theft.
            sessions.revoke_family(family)
            audit_log.record("refresh.reuse_detected", actor=sub, target=family)
            raise AuthError("Refresh token reuse detected; session revoked. Please sign in again.")
        identity = identities.get(sub)
        if not identity:
            raise AuthError("Unknown subject.")
        entitlements = self._licensing.resolve_entitlements(organisation_id) if organisation_id else ["vixa_platform"]
        extra = {"org": organisation_id} if organisation_id else {}
        access, ttl = create_access_token(
            identity.id, roles=identity.roles, entitlements=entitlements, extra=extra)
        new_refresh, _ = create_refresh_token(identity.id, family_id=family)
        new_claims = decode_token(new_refresh, expected_type="refresh")
        sessions.remember_refresh(family, new_claims["jti"])  # invalidates the old one
        audit_log.record("refresh.rotated", actor=identity.id, target=family)
        return access, ttl, new_refresh
