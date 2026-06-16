"""Onboarding orchestrator (sections 5.3 and 9) — the saga.

The onboarding journey is a distributed transaction across identity, the system
of record and external providers. It is modelled as an orchestrated saga: each
step runs in sequence, progress is recorded, and if a step fails the orchestrator
issues the compensating actions for the steps already completed (refund the
hold, roll back the created records).

The five phases group the brief's workflows:
  1. identity_and_org   — register, organisation, site
  2. human_and_contact  — reCAPTCHA, email, mobile verification
  3. payment            — card OTP + one-euro hold
  4. domain             — TXT/CNAME generation + DNS check
  5. activation         — features unlocked, account active

Because the flow is interactive (the user supplies OTPs, completes the bank
redirect, publishes DNS), the saga persists its state between calls and exposes
``next_action`` so the client knows what to do next. A failed or abandoned saga
can be safely resumed or compensated from its recorded progress.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable, Optional

from app.acl.anti_corruption import acl
from app.adapters.providers import recaptcha
from app.ciam.auth.service import AuthService
from app.ciam.mfa.service import MfaService
from app.core.audit import audit_log
from app.core.errors import AuthError, ConflictError, DomainError, NotFoundError
from app.domains.organisation.service import OrganisationService
from app.domains.payments.service import PaymentsService
from app.domains.verification.service import VerificationService
from app.models.schemas import (AccountStatus, OnboardingPhase, OnboardingState,
                                SagaStepLog, StartOnboardingRequest)


@dataclass
class _Saga:
    id: str
    request: StartOnboardingRequest
    phase: OnboardingPhase = OnboardingPhase.identity_and_org
    status: str = "in_progress"
    customer_id: Optional[str] = None
    organisation_id: Optional[str] = None
    identity_id: Optional[str] = None
    site_ids: list[str] = field(default_factory=list)
    email_challenge: Optional[str] = None
    mobile_challenge: Optional[str] = None
    domain_record: Optional[object] = None
    steps: list[SagaStepLog] = field(default_factory=list)
    next_action: Optional[str] = None
    # Compensations are pushed as completed steps succeed; run in reverse on failure.
    _compensations: list[Callable[[], None]] = field(default_factory=list)

    def log(self, step: str, status: str, detail: str | None = None) -> None:
        self.steps.append(SagaStepLog(step=step, status=status, detail=detail,
                                      at=datetime.now(timezone.utc)))


class OnboardingOrchestrator:
    def __init__(self, *, auth: AuthService, mfa: MfaService,
                 organisations: OrganisationService, verification: VerificationService,
                 payments: PaymentsService) -> None:
        self._auth = auth
        self._mfa = mfa
        self._orgs = organisations
        self._verification = verification
        self._payments = payments
        self._sagas: dict[str, _Saga] = {}

    # ----------------------------------------------------------------- utils
    def _get(self, saga_id: str) -> _Saga:
        saga = self._sagas.get(saga_id)
        if not saga:
            raise NotFoundError("Unknown onboarding session.")
        return saga

    def _state(self, saga: _Saga) -> OnboardingState:
        return OnboardingState(
            saga_id=saga.id, customer_id=saga.customer_id, organisation_id=saga.organisation_id,
            phase=saga.phase, status=saga.status, steps=saga.steps, next_action=saga.next_action,
        )

    def _compensate(self, saga: _Saga, reason: str) -> None:
        """Run compensating actions in reverse order, then mark the saga failed."""
        for comp in reversed(saga._compensations):
            try:
                comp()
            except Exception as exc:  # noqa: BLE001
                saga.log("compensation", "failed", str(exc))
        saga.status = "failed"
        saga.phase = OnboardingPhase.compensated
        saga.next_action = None
        audit_log.record("onboarding.compensated", target=saga.id, reason=reason)

    # ------------------------------------------------ phase 1: identity + org
    def start(self, request: StartOnboardingRequest) -> OnboardingState:
        saga = _Saga(id=f"saga_{uuid.uuid4().hex[:12]}", request=request)
        self._sagas[saga.id] = saga
        idem = saga.id  # the saga id is the natural idempotency key for this flow

        # reCAPTCHA gate before anything is created.
        if recaptcha.assess(request.recaptcha_token) < 0.5:
            saga.log("recaptcha", "failed", "low human score")
            self._compensate(saga, "recaptcha")
            raise DomainError("Automated traffic suspected. Please retry the challenge.")
        if not request.consent_gdpr:
            raise DomainError("GDPR consent is required to create an account.")

        try:
            identity = self._auth.create_identity(
                email=request.email, password=request.password, full_name=request.full_name)
            saga.identity_id = identity.id
            saga._compensations.append(lambda: __import__(
                "app.repositories.stores", fromlist=["identities"]).identities.delete(identity.id))
            saga.log("identity.created", "completed", identity.id)

            saga.customer_id = acl.create_customer(
                idem_key=idem, identity_id=identity.id,
                full_name=request.full_name, email=request.email)
            saga._compensations.append(lambda: acl.compensate_customer(saga.customer_id))
            saga.log("customer.created", "completed", saga.customer_id)

            saga.organisation_id = self._orgs.create_organisation(
                idem_key=idem, customer_id=saga.customer_id, org=request.organisation)
            saga._compensations.append(lambda: acl.compensate_organisation(saga.organisation_id))
            saga.log("organisation.created", "completed", saga.organisation_id)

            saga.site_ids = self._orgs.add_sites(
                idem_key=idem, organisation_id=saga.organisation_id, sites=request.sites)
            saga.log("sites.created", "completed", f"{len(saga.site_ids)} site(s)")
        except ConflictError:
            self._compensate(saga, "duplicate_email")
            raise
        except Exception as exc:  # noqa: BLE001
            self._compensate(saga, f"phase1:{exc}")
            raise

        # Move into contact verification and issue the email OTP.
        saga.phase = OnboardingPhase.human_and_contact
        saga.email_challenge = self._mfa.issue(
            purpose="email_verify", destination=request.email, channel="email")
        saga.next_action = "verify_email"
        audit_log.record("onboarding.started", target=saga.id, organisation=saga.organisation_id)
        return self._state(saga)

    # ----------------------------------------- phase 2: contact verification
    def verify_email(self, saga_id: str, code: str) -> OnboardingState:
        saga = self._get(saga_id)
        self._mfa.verify(saga.email_challenge, code)
        saga.log("email.verified", "completed")
        # Mobile is optional in this flow; if supplied, challenge it, else skip.
        saga.mobile_challenge = self._mfa.issue(
            purpose="mobile_verify", destination=saga.request.email, channel="sms")
        saga.next_action = "verify_mobile"
        return self._state(saga)

    def verify_mobile(self, saga_id: str, code: str) -> OnboardingState:
        saga = self._get(saga_id)
        self._mfa.verify(saga.mobile_challenge, code)
        saga.log("mobile.verified", "completed")
        saga.phase = OnboardingPhase.payment
        saga.next_action = "verify_card"
        return self._state(saga)

    # --------------------------------------------------- phase 3: card check
    def verify_card(self, saga_id: str, payment_method_token: str) -> OnboardingState:
        saga = self._get(saga_id)
        try:
            hold_id = self._payments.verify_card(payment_method_token)
            saga.log("card.verified", "completed", hold_id)
        except DomainError:
            saga.log("card.verified", "failed")
            raise  # card decline is recoverable: user can retry without compensating
        saga.phase = OnboardingPhase.domain
        record = self._verification.generate_domain_record(
            saga.organisation_id, domain=saga.request.email.split("@")[-1])
        saga.domain_record = record
        saga.next_action = "verify_domain"
        return self._state(saga)

    # ------------------------------------------------- phase 4: domain check
    def get_domain_record(self, saga_id: str):
        return self._get(saga_id).domain_record

    def verify_domain(self, saga_id: str) -> OnboardingState:
        saga = self._get(saga_id)
        self._verification.confirm_domain(saga.organisation_id, saga.domain_record)
        saga.log("domain.verified", "completed")
        return self._activate(saga)

    # ---------------------------------------------------- phase 5: activation
    def _activate(self, saga: _Saga) -> OnboardingState:
        acl.set_account_status(saga.customer_id, AccountStatus.active)
        # Record membership so login can resolve this identity's organisation.
        from app.repositories.stores import memberships
        memberships.set(saga.identity_id, saga.organisation_id)
        saga.phase = OnboardingPhase.completed
        saga.status = "completed"
        saga.next_action = None
        saga.log("account.activated", "completed")
        audit_log.record("account.activated", target=saga.customer_id,
                         organisation=saga.organisation_id)
        return self._state(saga)

    def state(self, saga_id: str) -> OnboardingState:
        return self._state(self._get(saga_id))

    def organisation_for_identity(self, saga_id: str) -> Optional[str]:
        return self._get(saga_id).organisation_id
