"""Onboarding routes — drive the saga (workflows 1-7, 10, 11).

The flow is interactive: each call advances one phase and returns the saga state
including ``next_action``. Demo helpers expose the OTP/DNS values so the SPA can
complete the flow without a real inbox or DNS zone (development only).
"""
from __future__ import annotations

from fastapi import APIRouter

from app.core.config import settings
from app.core.container import container
from app.models.schemas import (CardVerificationRequest, OnboardingState,
                                OtpVerifyRequest, StartOnboardingRequest)

router = APIRouter(prefix="/onboarding", tags=["onboarding"])


@router.post("", response_model=OnboardingState, status_code=201,
             summary="Start onboarding: register identity, create organisation and sites")
def start(body: StartOnboardingRequest):
    return container.orchestrator.start(body)


@router.post("/{saga_id}/email", response_model=OnboardingState,
             summary="Verify the email OTP (workflow 5)")
def verify_email(saga_id: str, body: OtpVerifyRequest):
    return container.orchestrator.verify_email(saga_id, body.code)


@router.post("/{saga_id}/mobile", response_model=OnboardingState,
             summary="Verify the mobile OTP (workflow 6)")
def verify_mobile(saga_id: str, body: OtpVerifyRequest):
    return container.orchestrator.verify_mobile(saga_id, body.code)


@router.post("/{saga_id}/card", response_model=OnboardingState,
             summary="Card verification with one-euro hold (workflow 7)")
def verify_card(saga_id: str, body: CardVerificationRequest):
    return container.orchestrator.verify_card(saga_id, body.payment_method_token)


@router.get("/{saga_id}/domain-record",
            summary="Fetch the auto-generated TXT record to publish (workflow 10)")
def domain_record(saga_id: str):
    return container.orchestrator.get_domain_record(saga_id)


@router.post("/{saga_id}/domain", response_model=OnboardingState,
             summary="Confirm domain ownership and activate the account (workflows 11, activation)")
def verify_domain(saga_id: str):
    return container.orchestrator.verify_domain(saga_id)


@router.get("/{saga_id}", response_model=OnboardingState, summary="Current saga state")
def state(saga_id: str):
    return container.orchestrator.state(saga_id)


# --- development-only helpers (resolve OTPs so the SPA can self-drive) ------ #
if settings.environment == "development":
    @router.get("/{saga_id}/dev/otp", summary="[dev] Read the pending OTPs for this saga")
    def dev_otp(saga_id: str):
        saga = container.orchestrator._get(saga_id)  # noqa: SLF001 (dev helper)
        return {
            "email_code": container.mfa.peek_code(saga.email_challenge) if saga.email_challenge else None,
            "mobile_code": container.mfa.peek_code(saga.mobile_challenge) if saga.mobile_challenge else None,
        }
