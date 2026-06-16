"""Pydantic models — the typed contracts that FastAPI validates and documents.

These cover the request/response shapes for every workflow, plus the internal
entities. Strong typing here is one of the FastAPI principles the brief calls
for: speed, type validation and automatic OpenAPI documentation.
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, EmailStr, Field


# --------------------------------------------------------------------------- #
# Enumerations
# --------------------------------------------------------------------------- #
class AccountStatus(str, Enum):
    pending = "pending"
    active = "active"
    suspended = "suspended"
    closed = "closed"


class OnboardingPhase(str, Enum):
    identity_and_org = "identity_and_org"
    human_and_contact = "human_and_contact"
    payment = "payment"
    domain = "domain"
    activation = "activation"
    completed = "completed"
    compensated = "compensated"


class Product(str, Enum):
    platform = "vixa_platform"
    xdr_xsiam = "vixa_xdr_xsiam"
    ai = "vixa_ai"
    autoark = "vixa_autoark"
    vault = "vixa_vault"


class Role(str, Enum):
    admin = "admin"
    standard = "standard"


# --------------------------------------------------------------------------- #
# Auth & identity
# --------------------------------------------------------------------------- #
class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=10, max_length=128)
    full_name: str = Field(min_length=1, max_length=200)
    recaptcha_token: str = Field(description="Token from reCAPTCHA Enterprise on the client")
    consent_gdpr: bool = Field(description="Explicit GDPR consent captured at onboarding")


class LoginRequest(BaseModel):
    email: EmailStr
    password: str
    recaptcha_token: Optional[str] = None
    otp_code: Optional[str] = Field(default=None, description="Step-up MFA code when challenged")


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "Bearer"
    expires_in: int
    # Refresh token is delivered in an HTTP-only cookie (section 11.2),
    # echoed here only so the SPA dev flow works without a cookie jar.
    refresh_token: Optional[str] = None


class MfaChallenge(BaseModel):
    mfa_required: bool = True
    challenge_id: str
    channels: list[str]
    message: str = "Step-up verification required. Submit the OTP to continue."


# --------------------------------------------------------------------------- #
# Organisation & site
# --------------------------------------------------------------------------- #
class OrganisationCreate(BaseModel):
    name: str
    country: str
    city: str
    address: str
    postcode: str
    telephone: str
    directors: list[str] = Field(default_factory=list)


class SiteCreate(BaseModel):
    name: str
    location: str
    responsible_managers: list[str] = Field(default_factory=list)


class Organisation(BaseModel):
    id: str
    name: str
    country: str
    city: str
    domain_verified: bool = False
    account_status: AccountStatus = AccountStatus.pending


# --------------------------------------------------------------------------- #
# Verification
# --------------------------------------------------------------------------- #
class OtpVerifyRequest(BaseModel):
    challenge_id: str
    code: str


class DomainVerificationRecord(BaseModel):
    record_type: str  # TXT or CNAME
    host: str
    value: str
    ttl_seconds: int


# --------------------------------------------------------------------------- #
# Payments
# --------------------------------------------------------------------------- #
class CardVerificationRequest(BaseModel):
    payment_method_token: str = Field(
        description="Tokenised by the gateway on the client; raw PAN never reaches us (PCI-DSS)."
    )


# --------------------------------------------------------------------------- #
# Subscriptions & licensing
# --------------------------------------------------------------------------- #
class SubscribeRequest(BaseModel):
    product: Product
    payment_method_token: Optional[str] = None


# --------------------------------------------------------------------------- #
# Onboarding saga
# --------------------------------------------------------------------------- #
class StartOnboardingRequest(RegisterRequest):
    organisation: OrganisationCreate
    sites: list[SiteCreate] = Field(default_factory=list)


class SagaStepLog(BaseModel):
    step: str
    status: str  # completed | compensated | failed
    detail: Optional[str] = None
    at: datetime


class OnboardingState(BaseModel):
    saga_id: str
    customer_id: Optional[str] = None
    organisation_id: Optional[str] = None
    phase: OnboardingPhase
    status: str  # in_progress | awaiting_input | completed | failed
    steps: list[SagaStepLog] = Field(default_factory=list)
    next_action: Optional[str] = None


# --------------------------------------------------------------------------- #
# Admin
# --------------------------------------------------------------------------- #
class AccountStatusUpdate(BaseModel):
    status: AccountStatus
    reason: Optional[str] = None
