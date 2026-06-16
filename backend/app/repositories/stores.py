"""Repositories — the data-store boundary (section 5.7).

The architecture specifies PostgreSQL for identity/credential data and Redis for
sessions and cache. To keep the assessment runnable with zero infrastructure,
these are in-memory implementations behind small interfaces. Swapping in
SQLAlchemy + asyncpg (identity) and redis-py (sessions) is a drop-in change that
does not touch any caller.

Crucially, the identity store holds ONLY the digital identity — credentials and
the user principal. Customer master data, organisations, sites, licences and
subscription state live in Ost Infinity, reached through the anti-corruption
layer. This is the "separation of identity and system of record" from section 7.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional


@dataclass
class Identity:
    """The digital identity owned by CIAM — nothing else lives here."""
    id: str
    email: str
    password_hash: str
    full_name: str
    roles: list[str] = field(default_factory=lambda: ["standard"])
    email_verified: bool = False
    mobile_verified: bool = False
    mobile: Optional[str] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class IdentityRepository:
    def __init__(self) -> None:
        self._by_id: dict[str, Identity] = {}
        self._by_email: dict[str, str] = {}

    def create(self, *, email: str, password_hash: str, full_name: str,
               roles: Optional[list[str]] = None) -> Identity:
        if email.lower() in self._by_email:
            raise ValueError("email already registered")
        identity = Identity(
            id=f"usr_{uuid.uuid4().hex[:12]}",
            email=email.lower(),
            password_hash=password_hash,
            full_name=full_name,
            roles=roles or ["admin"],  # first user of an org is its admin
        )
        self._by_id[identity.id] = identity
        self._by_email[identity.email] = identity.id
        return identity

    def get(self, identity_id: str) -> Optional[Identity]:
        return self._by_id.get(identity_id)

    def get_by_email(self, email: str) -> Optional[Identity]:
        uid = self._by_email.get(email.lower())
        return self._by_id.get(uid) if uid else None

    def delete(self, identity_id: str) -> None:
        """Compensating action for a failed registration saga."""
        identity = self._by_id.pop(identity_id, None)
        if identity:
            self._by_email.pop(identity.email, None)


@dataclass
class Session:
    id: str
    identity_id: str
    refresh_family: str
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class SessionRepository:
    """Redis stand-in. Holds session state shared across instances (section 5.3)."""

    def __init__(self) -> None:
        self._sessions: dict[str, Session] = {}
        self._refresh_families: dict[str, str] = {}  # family -> latest jti (rotation guard)

    def create(self, identity_id: str, refresh_family: str) -> Session:
        session = Session(id=f"sess_{uuid.uuid4().hex[:12]}",
                          identity_id=identity_id, refresh_family=refresh_family)
        self._sessions[session.id] = session
        return session

    def remember_refresh(self, family: str, jti: str) -> None:
        self._refresh_families[family] = jti

    def is_current_refresh(self, family: str, jti: str) -> bool:
        return self._refresh_families.get(family) == jti

    def revoke_family(self, family: str) -> None:
        self._refresh_families.pop(family, None)


class MembershipRepository:
    """Maps a digital identity to the organisation it belongs to.

    In production this is resolved from Ost Infinity; kept as a small registry
    here so login can stamp the right org/entitlements into the token."""

    def __init__(self) -> None:
        self._by_identity: dict[str, str] = {}

    def set(self, identity_id: str, organisation_id: str) -> None:
        self._by_identity[identity_id] = organisation_id

    def organisation_for(self, identity_id: str) -> Optional[str]:
        return self._by_identity.get(identity_id)


# Shared singletons for the running app.
identities = IdentityRepository()
sessions = SessionRepository()
memberships = MembershipRepository()
