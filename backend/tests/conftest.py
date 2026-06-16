"""Test fixtures — reset the in-memory stores between tests for isolation.

The platform uses in-memory singletons (PostgreSQL/Redis/Kafka stand-ins). This
autouse fixture clears their state before each test so tests do not leak into
one another. The event-bus *subscribers* are preserved (workers register once at
import time); only the published/dead-letter logs are cleared.
"""
from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _reset_state():
    from app.acl.anti_corruption import acl, ost_infinity
    from app.adapters.providers import dns, notifications
    from app.core.audit import audit_log
    from app.core.container import container
    from app.core.events import bus
    from app.core.rate_limit import reset_buckets
    from app.repositories.stores import identities, memberships, sessions

    reset_buckets()
    identities._by_id.clear(); identities._by_email.clear()
    sessions._sessions.clear(); sessions._refresh_families.clear()
    memberships._by_identity.clear()
    ost_infinity.customers.clear(); ost_infinity.organisations.clear(); ost_infinity.subscriptions.clear()
    acl._idempotency.clear()
    container.orchestrator._sagas.clear()
    notifications.outbox.clear()
    dns._present.clear()
    audit_log._entries.clear()
    bus._dlq.clear(); bus._published.clear()
    yield
