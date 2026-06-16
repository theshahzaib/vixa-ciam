"""Admin console routes (workflows 9, 12, 14, 17) — RBAC-gated.

Every route here requires the admin role claim. Covers account suspend/close,
department/structure creation and payment-preference updates.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends

from app.acl.anti_corruption import acl, ost_infinity
from app.core.audit import audit_log
from app.core.errors import NotFoundError
from app.gateway.deps import Principal, require_admin
from app.models.schemas import AccountStatus, AccountStatusUpdate, SiteCreate

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/organisation", summary="Admin console — organisation overview (workflow 12)")
def organisation_overview(principal: Principal = Depends(require_admin)):
    org_id = principal.organisation_id
    org = ost_infinity.organisations.get(org_id) if org_id else None
    if not org:
        raise NotFoundError("Organisation not found.")
    return {
        "organisation_id": org.id,
        "profile": org.profile,
        "domain_verified": org.domain_verified,
        "sites": org.sites,
        "entitlements": acl.entitlements_for(org.id),
    }


@router.post("/organisation/departments", summary="Create a department/structure (workflow 14)")
def create_department(name: str, parent: str | None = None,
                      principal: Principal = Depends(require_admin)):
    audit_log.record("department.created", actor=principal.subject,
                     target=principal.organisation_id, name=name, parent=parent)
    return {"status": "created", "name": name, "parent": parent}


@router.put("/payment-preferences", summary="Update payment preferences (workflow 9)")
def update_payment_preferences(payment_method_token: str,
                               principal: Principal = Depends(require_admin)):
    audit_log.record("payment.preferences_updated", actor=principal.subject,
                     target=principal.organisation_id)
    return {"status": "updated"}


@router.post("/accounts/{customer_id}/status", summary="Suspend or close an account (workflow 17)")
def set_account_status(customer_id: str, body: AccountStatusUpdate,
                       principal: Principal = Depends(require_admin)):
    if customer_id not in ost_infinity.customers:
        raise NotFoundError("Customer not found.")
    acl.set_account_status(customer_id, body.status)
    audit_log.record("account.status_changed", actor=principal.subject, target=customer_id,
                     status=body.status.value, reason=body.reason)
    return {"customer_id": customer_id, "status": body.status.value}
