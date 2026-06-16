"""Async workers (section 5.5) — consume backbone events and do the slow work.

These subscribe to the event bus. On ``payment.confirmed`` a worker provisions
the licence through the Licensing service (writing to Ost Infinity via the ACL)
and then requests a welcome notification. This is why a slow payment never
freezes the user: the licence is provisioned in the background and entitlements
refresh on the next token cycle (sections 8 and 16).
"""
from __future__ import annotations

from app.adapters.providers import notifications
from app.core.events import Event, EventBus, Topics
from app.domains.licensing.service import LicensingService


def register_workers(bus: EventBus, licensing: LicensingService) -> None:
    async def on_payment_confirmed(event: Event) -> None:
        org_id = event.payload["organisation_id"]
        product = event.payload["product"]
        licence_id = licensing.provision_licence(org_id, product)
        await bus.publish(Topics.LICENCE_PROVISIONED,
                          {"organisation_id": org_id, "product": product, "licence_id": licence_id})
        await bus.publish(Topics.NOTIFICATION_REQUESTED,
                          {"to": org_id, "template": "licence_provisioned", "product": product})

    async def on_notification(event: Event) -> None:
        notifications.send_email(
            event.payload.get("to", "unknown"),
            f"Your {event.payload.get('product', 'product')} licence is ready.",
        )

    bus.subscribe(Topics.PAYMENT_CONFIRMED, on_payment_confirmed)
    bus.subscribe(Topics.NOTIFICATION_REQUESTED, on_notification)
