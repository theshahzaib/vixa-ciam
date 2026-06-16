"""Payments service (section 5.4).

Runs the card verification (one-euro hold via 3-D Secure) synchronously because
the user is waiting on the bank, but does NOT block on subscription provisioning:
a confirmed subscription payment publishes ``payment.confirmed`` to the backbone
and an async worker provisions the licence (sections 8 and 9). Card data is
tokenised by the gateway and never stored here (PCI-DSS).
"""
from __future__ import annotations

from app.adapters.providers import payments_gateway
from app.core.audit import audit_log
from app.core.config import settings
from app.core.errors import DomainError
from app.core.events import EventBus, Topics


class PaymentsService:
    def __init__(self, bus: EventBus) -> None:
        self._bus = bus

    def verify_card(self, payment_method_token: str) -> str:
        """Place and immediately schedule release of the one-euro hold."""
        hold = payments_gateway.place_hold(
            payment_method_token, settings.payment_hold_amount_cents, settings.payment_hold_currency)
        if hold.status != "authorised":
            audit_log.record("payment.card_declined")
            raise DomainError("Card verification was declined by the issuer.")
        # The hold is held for three days then refunded (workflow 7). The release
        # is recorded here; in production a scheduled job releases after the window.
        payments_gateway.release_hold(hold.hold_id)
        audit_log.record("payment.card_verified", hold_id=hold.hold_id)
        return hold.hold_id

    async def subscribe(self, *, organisation_id: str, product: str,
                        payment_method_token: str | None) -> None:
        """Charge for a subscription, then publish payment.confirmed. Licence
        provisioning happens asynchronously off the back of the event."""
        charge_id = payments_gateway.charge_subscription(
            payment_method_token or "tok_on_file", 4900, settings.payment_hold_currency)
        audit_log.record("payment.charged", target=organisation_id, product=product,
                         charge_id=charge_id)
        await self._bus.publish(Topics.PAYMENT_CONFIRMED, {
            "organisation_id": organisation_id, "product": product, "charge_id": charge_id,
        })
