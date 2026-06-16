"""Composition root — wires the services together once at startup.

Centralising construction here keeps the routes thin and makes the dependency
graph explicit. In a multi-process deployment each service would be its own
process; the wiring contract is identical.
"""
from __future__ import annotations

from app.ciam.auth.service import AuthService
from app.ciam.mfa.service import MfaService
from app.ciam.orchestrator.saga import OnboardingOrchestrator
from app.core.events import bus
from app.core.workers import register_workers
from app.domains.licensing.service import LicensingService
from app.domains.organisation.service import OrganisationService
from app.domains.payments.service import PaymentsService
from app.domains.verification.service import VerificationService


class Container:
    def __init__(self) -> None:
        self.licensing = LicensingService()
        self.auth = AuthService(self.licensing)
        self.mfa = MfaService()
        self.organisations = OrganisationService()
        self.verification = VerificationService()
        self.payments = PaymentsService(bus)
        self.orchestrator = OnboardingOrchestrator(
            auth=self.auth, mfa=self.mfa, organisations=self.organisations,
            verification=self.verification, payments=self.payments,
        )
        register_workers(bus, self.licensing)


container = Container()
