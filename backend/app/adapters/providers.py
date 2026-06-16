"""Adapters for external providers (the one synchronous edge that leaves the
spine, section 8). Each is a mock with the same interface a real provider would
expose, so swapping in reCAPTCHA Enterprise, Twilio, Stripe or a DNS resolver is
a configuration change, not a rewrite.
"""
from __future__ import annotations

import random
import uuid
from dataclasses import dataclass


# --------------------------------------------------------------------------- #
# reCAPTCHA Enterprise (human/bot score)
# --------------------------------------------------------------------------- #
class RecaptchaAdapter:
    def assess(self, token: str) -> float:
        """Return a human-likelihood score in [0, 1]. Mock: any non-empty token
        that is not literally "bot" scores high."""
        if not token:
            return 0.0
        return 0.1 if token == "bot" else 0.9


# --------------------------------------------------------------------------- #
# Notifications (email + SMS OTP)
# --------------------------------------------------------------------------- #
@dataclass
class SentMessage:
    channel: str
    to: str
    body: str


class NotificationAdapter:
    """Captures sent messages so the demo/tests can read OTPs back."""

    def __init__(self) -> None:
        self.outbox: list[SentMessage] = []

    def send_email(self, to: str, body: str) -> None:
        self.outbox.append(SentMessage("email", to, body))

    def send_sms(self, to: str, body: str) -> None:
        self.outbox.append(SentMessage("sms", to, body))


# --------------------------------------------------------------------------- #
# Payment gateway (Stripe/Adyen-style, tokenised + 3-D Secure)
# --------------------------------------------------------------------------- #
@dataclass
class HoldResult:
    hold_id: str
    status: str  # authorised | declined
    three_ds_required: bool


class PaymentGatewayAdapter:
    """Card data is tokenised by the gateway; the platform only ever sees the
    token (PCI-DSS scope reduction, section 12)."""

    def place_hold(self, payment_method_token: str, amount_cents: int, currency: str) -> HoldResult:
        if not payment_method_token or payment_method_token == "decline":
            return HoldResult(hold_id="", status="declined", three_ds_required=False)
        return HoldResult(hold_id=f"hold_{uuid.uuid4().hex[:10]}", status="authorised",
                          three_ds_required=True)

    def release_hold(self, hold_id: str) -> None:
        # In production this calls the gateway to refund the verification hold.
        return None

    def charge_subscription(self, payment_method_token: str, amount_cents: int, currency: str) -> str:
        return f"chg_{uuid.uuid4().hex[:10]}"


# --------------------------------------------------------------------------- #
# DNS (domain-ownership verification)
# --------------------------------------------------------------------------- #
class DnsAdapter:
    """Mock DNS resolver. The demo flips a record to 'present' on first check so
    domain verification can complete without real DNS propagation."""

    def __init__(self) -> None:
        self._present: set[str] = set()

    def seed_record(self, host: str, value: str) -> None:
        self._present.add(f"{host}:{value}")

    def lookup_txt(self, host: str, expected_value: str) -> bool:
        return f"{host}:{expected_value}" in self._present


# Shared singletons.
recaptcha = RecaptchaAdapter()
notifications = NotificationAdapter()
payments_gateway = PaymentGatewayAdapter()
dns = DnsAdapter()
