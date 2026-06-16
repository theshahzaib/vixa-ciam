"""MFA & session service (section 5.3) — OTP challenges over email and SMS.

Generates time-boxed one-time passwords for step-up authentication and for the
email/mobile verification workflows. Challenges are single-use and expire.
"""
from __future__ import annotations

import secrets
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

from app.adapters.providers import notifications
from app.core.config import settings
from app.core.errors import AuthError, NotFoundError


@dataclass
class _Challenge:
    id: str
    purpose: str            # login_stepup | email_verify | mobile_verify
    destination: str
    code: str
    channel: str            # email | sms
    expires_at: datetime
    consumed: bool = False


class MfaService:
    def __init__(self) -> None:
        self._challenges: dict[str, _Challenge] = {}

    def _new_code(self) -> str:
        return "".join(secrets.choice("0123456789") for _ in range(settings.otp_length))

    def issue(self, *, purpose: str, destination: str, channel: str) -> str:
        code = self._new_code()
        challenge = _Challenge(
            id=f"chl_{uuid.uuid4().hex[:12]}",
            purpose=purpose, destination=destination, code=code, channel=channel,
            expires_at=datetime.now(timezone.utc) + timedelta(seconds=settings.otp_ttl_seconds),
        )
        self._challenges[challenge.id] = challenge
        body = f"Your ViXa verification code is {code} (valid {settings.otp_ttl_seconds // 60} minutes)."
        if channel == "email":
            notifications.send_email(destination, body)
        else:
            notifications.send_sms(destination, body)
        return challenge.id

    def verify(self, challenge_id: str, code: str) -> _Challenge:
        challenge = self._challenges.get(challenge_id)
        if not challenge:
            raise NotFoundError("Unknown verification challenge.")
        if challenge.consumed:
            raise AuthError("This verification code has already been used.")
        if datetime.now(timezone.utc) > challenge.expires_at:
            raise AuthError("This verification code has expired.")
        if not secrets.compare_digest(challenge.code, code):
            raise AuthError("Incorrect verification code.")
        challenge.consumed = True
        return challenge

    def peek_code(self, challenge_id: str) -> Optional[str]:
        """Demo helper only — lets the SPA/tests retrieve the OTP without a real
        inbox. Disabled outside development."""
        if settings.environment != "development":
            return None
        c = self._challenges.get(challenge_id)
        return c.code if c else None
