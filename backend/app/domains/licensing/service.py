"""Licensing & RBAC service (section 5.4).

Resolves subscription/licence state from Ost Infinity into the set of
entitlements that the Auth service stamps into the JWT, and provisions licences
when a payment-confirmed event lands on the backbone.
"""
from __future__ import annotations

import uuid
from typing import Optional

from app.acl.anti_corruption import acl
from app.core.audit import audit_log


class LicensingService:
    def resolve_entitlements(self, organisation_id: Optional[str]) -> list[str]:
        """Resolve the org's current entitlements. ViXa Platform is always the
        base; subscribed products add to it (section 6)."""
        if not organisation_id:
            return ["vixa_platform"]
        return acl.entitlements_for(organisation_id)

    def provision_licence(self, organisation_id: str, product: str) -> str:
        """Assign a licence to the org/product and persist via the ACL. Called
        by the async worker on payment.confirmed (workflow 16)."""
        licence_id = f"lic_{uuid.uuid4().hex[:10]}"
        acl.record_subscription(organisation_id, product, licence_id)
        audit_log.record("licence.provisioned", target=organisation_id, product=product,
                         licence_id=licence_id)
        return licence_id

    @staticmethod
    def has_entitlement(entitlements: list[str], product: str) -> bool:
        return product in entitlements
