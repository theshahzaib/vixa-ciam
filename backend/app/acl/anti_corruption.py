"""Anti-corruption layer + Ost Infinity client (sections 5.6 and 7).

Ost Infinity is the authoritative system of record for customer master data,
organisation/site structures, licences, subscription state and account status.
CIAM never talks to it directly. Every write passes through the anti-corruption
layer (ACL), which:

  * translates the CIAM domain model into the Ost Infinity API contract,
  * enforces idempotency keys so a retried saga step can never create a
    duplicate organisation or double-charge,
  * isolates each model so either side can evolve independently.

``OstInfinityClient`` is a mock of the external system (in-memory). In
production it would be an HTTP client against the real Ost Infinity API; the ACL
above it would not change.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from app.models.schemas import AccountStatus, OrganisationCreate, SiteCreate


# --------------------------------------------------------------------------- #
# Mock external system of record
# --------------------------------------------------------------------------- #
@dataclass
class _OstCustomer:
    id: str
    identity_id: str
    full_name: str
    email: str
    account_status: AccountStatus = AccountStatus.pending


@dataclass
class _OstOrganisation:
    id: str
    customer_id: str
    profile: dict
    domain_verified: bool = False
    sites: list[dict] = field(default_factory=list)


@dataclass
class _OstSubscription:
    organisation_id: str
    product: str
    state: str  # active | cancelled
    licence_id: str


class OstInfinityClient:
    """Stand-in for the external Ost Infinity API."""

    def __init__(self) -> None:
        self.customers: dict[str, _OstCustomer] = {}
        self.organisations: dict[str, _OstOrganisation] = {}
        self.subscriptions: dict[str, list[_OstSubscription]] = {}

    def upsert_customer(self, identity_id: str, full_name: str, email: str) -> _OstCustomer:
        cid = f"cust_{uuid.uuid4().hex[:10]}"
        cust = _OstCustomer(id=cid, identity_id=identity_id, full_name=full_name, email=email)
        self.customers[cid] = cust
        return cust

    def create_organisation(self, customer_id: str, profile: dict) -> _OstOrganisation:
        oid = f"org_{uuid.uuid4().hex[:10]}"
        org = _OstOrganisation(id=oid, customer_id=customer_id, profile=profile)
        self.organisations[oid] = org
        return org

    def add_site(self, organisation_id: str, site: dict) -> dict:
        org = self.organisations[organisation_id]
        site = {**site, "id": f"site_{uuid.uuid4().hex[:8]}"}
        org.sites.append(site)
        return site

    def set_account_status(self, customer_id: str, status: AccountStatus) -> None:
        self.customers[customer_id].account_status = status

    def set_domain_verified(self, organisation_id: str, verified: bool) -> None:
        self.organisations[organisation_id].domain_verified = verified

    def record_subscription(self, organisation_id: str, product: str, licence_id: str) -> None:
        self.subscriptions.setdefault(organisation_id, []).append(
            _OstSubscription(organisation_id, product, "active", licence_id))

    def entitlements_for(self, organisation_id: str) -> list[str]:
        active = [s.product for s in self.subscriptions.get(organisation_id, []) if s.state == "active"]
        # ViXa Platform is the base product every onboarded customer receives.
        return sorted(set(["vixa_platform", *active]))

    def delete_organisation(self, organisation_id: str) -> None:
        self.organisations.pop(organisation_id, None)

    def delete_customer(self, customer_id: str) -> None:
        self.customers.pop(customer_id, None)


# --------------------------------------------------------------------------- #
# Anti-corruption layer
# --------------------------------------------------------------------------- #
class AntiCorruptionLayer:
    """The only path from CIAM into Ost Infinity. Enforces idempotency."""

    def __init__(self, client: OstInfinityClient) -> None:
        self._client = client
        self._idempotency: dict[str, object] = {}

    def _idempotent(self, key: str, produce):
        """Return the cached result for an idempotency key, or run ``produce``
        once and cache it. A retried saga step is therefore a no-op."""
        if key in self._idempotency:
            return self._idempotency[key]
        result = produce()
        self._idempotency[key] = result
        return result

    # --- translation methods (CIAM model -> Ost Infinity contract) ---------- #
    def create_customer(self, *, idem_key: str, identity_id: str, full_name: str, email: str) -> str:
        cust = self._idempotent(
            f"customer:{idem_key}",
            lambda: self._client.upsert_customer(identity_id, full_name, email),
        )
        return cust.id

    def create_organisation(self, *, idem_key: str, customer_id: str,
                            org: OrganisationCreate) -> str:
        created = self._idempotent(
            f"org:{idem_key}",
            lambda: self._client.create_organisation(customer_id, org.model_dump()),
        )
        return created.id

    def add_sites(self, *, idem_key: str, organisation_id: str, sites: list[SiteCreate]) -> list[str]:
        def _produce():
            return [self._client.add_site(organisation_id, s.model_dump())["id"] for s in sites]
        return self._idempotent(f"sites:{idem_key}", _produce)

    def mark_domain_verified(self, organisation_id: str) -> None:
        self._client.set_domain_verified(organisation_id, True)

    def set_account_status(self, customer_id: str, status: AccountStatus) -> None:
        self._client.set_account_status(customer_id, status)

    def record_subscription(self, organisation_id: str, product: str, licence_id: str) -> None:
        self._client.record_subscription(organisation_id, product, licence_id)

    def entitlements_for(self, organisation_id: str) -> list[str]:
        return self._client.entitlements_for(organisation_id)

    # --- compensating actions ---------------------------------------------- #
    def compensate_organisation(self, organisation_id: str) -> None:
        self._client.delete_organisation(organisation_id)

    def compensate_customer(self, customer_id: str) -> None:
        self._client.delete_customer(customer_id)


# Shared singletons.
ost_infinity = OstInfinityClient()
acl = AntiCorruptionLayer(ost_infinity)
