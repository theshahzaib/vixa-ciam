"""Products & subscriptions routes (workflows 13, 15, 16).

The products home renders only entitled tiles, read straight from the JWT claims
(no DB hit). Subscribing publishes a payment-confirmed event; the async worker
provisions the licence and entitlements refresh on the next token cycle.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends

from app.core.container import container
from app.gateway.deps import Principal, get_principal, require_entitlement
from app.models.schemas import Product, SubscribeRequest

router = APIRouter(tags=["products"])

_ALL_PRODUCTS = [
    {"id": "vixa_platform", "name": "ViXa Platform", "base": True},
    {"id": "vixa_xdr_xsiam", "name": "ViXa XDR-XSIAM", "base": False},
    {"id": "vixa_ai", "name": "ViXa AI", "base": False},
    {"id": "vixa_autoark", "name": "ViXa AutoArk", "base": False},
    {"id": "vixa_vault", "name": "ViXa Vault", "base": False},
]


@router.get("/products", summary="Products & Services home — entitled tiles active, others upsell")
def products_home(principal: Principal = Depends(get_principal)):
    tiles = []
    for p in _ALL_PRODUCTS:
        entitled = p["id"] in principal.entitlements
        tiles.append({**p, "state": "active" if entitled else "upsell"})
    return {"organisation_id": principal.organisation_id, "tiles": tiles}


@router.post("/subscribe", summary="Subscribe to a product (workflow 15) — async provisioning")
async def subscribe(body: SubscribeRequest, principal: Principal = Depends(get_principal)):
    if not principal.organisation_id:
        return {"status": "error", "detail": "No organisation associated with this identity."}
    await container.payments.subscribe(
        organisation_id=principal.organisation_id,
        product=body.product.value,
        payment_method_token=body.payment_method_token,
    )
    return {
        "status": "accepted",
        "detail": ("Payment confirmed. Licence is being provisioned asynchronously; "
                   "re-authenticate or refresh your token to pick up the new entitlement."),
        "product": body.product.value,
    }


@router.get("/products/vault/open", summary="Example entitlement-gated resource",
            dependencies=[Depends(require_entitlement("vixa_vault"))])
def open_vault():
    return {"status": "ok", "detail": "ViXa Vault opened — you are entitled to this product."}
