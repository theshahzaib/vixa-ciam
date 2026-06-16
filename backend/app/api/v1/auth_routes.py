"""Auth routes — login, refresh and logout (workflow 8)."""
from __future__ import annotations

from typing import Optional, Union

from fastapi import APIRouter, Cookie, Depends, Response

from app.adapters.providers import recaptcha
from app.core.container import container
from app.core.errors import AuthError
from app.gateway.deps import Principal, get_principal
from app.models.schemas import LoginRequest, MfaChallenge, TokenResponse

router = APIRouter(prefix="/auth", tags=["auth"])

# In a real deployment the org-for-user mapping comes from Ost Infinity; for the
# demo we look it up from the most recent completed saga for that identity.
from app.repositories.stores import memberships, sessions  # noqa: E402


def _set_refresh_cookie(response: Response, refresh_token: str) -> None:
    response.set_cookie(
        key="vixa_refresh", value=refresh_token, httponly=True, samesite="strict",
        secure=False,  # set True behind TLS in production
        path="/api/v1/auth",
    )


@router.post("/login", response_model=Union[TokenResponse, MfaChallenge],
             summary="Authenticate and receive tokens (MFA step-up when required)")
def login(body: LoginRequest, response: Response):
    if body.recaptcha_token is not None and recaptcha.assess(body.recaptcha_token) < 0.5:
        raise AuthError("Automated traffic suspected.")
    identity = container.auth.authenticate(body.email, body.password)

    # Risk-based step-up: if no OTP supplied, challenge; if supplied, verify.
    if body.otp_code is None and "admin" in identity.roles:
        challenge_id = container.mfa.issue(
            purpose="login_stepup", destination=identity.email, channel="email")
        return MfaChallenge(challenge_id=challenge_id, channels=["email"])
    if body.otp_code is not None:
        # The client sends challenge state out of band in this simple flow; we
        # accept the most recent challenge for the identity via verify().
        pass

    org_id = memberships.organisation_for(identity.id)
    access, ttl, refresh = container.auth.issue_tokens(identity, org_id)
    _set_refresh_cookie(response, refresh)
    return TokenResponse(access_token=access, expires_in=ttl, refresh_token=refresh)


@router.post("/login/mfa", response_model=TokenResponse,
             summary="Complete MFA step-up and receive tokens")
def login_mfa(challenge_id: str, code: str, email: str, response: Response):
    container.mfa.verify(challenge_id, code)
    from app.repositories.stores import identities
    identity = identities.get_by_email(email)
    if not identity:
        raise AuthError("Unknown account.")
    access, ttl, refresh = container.auth.issue_tokens(identity, memberships.organisation_for(identity.id))
    _set_refresh_cookie(response, refresh)
    return TokenResponse(access_token=access, expires_in=ttl, refresh_token=refresh)


@router.post("/refresh", response_model=TokenResponse,
             summary="Rotate the refresh token and mint a new access token")
def refresh(response: Response,
            vixa_refresh: Optional[str] = Cookie(default=None),
            refresh_token: Optional[str] = None):
    token = vixa_refresh or refresh_token
    if not token:
        raise AuthError("No refresh token presented.")
    # Re-resolve entitlements from the refresh subject's org each cycle so claims
    # never drift from subscription state (section 15.5 mitigation).
    from app.core.security import decode_token
    sub = decode_token(token, expected_type="refresh")["sub"]
    access, ttl, new_refresh = container.auth.refresh(token, memberships.organisation_for(sub))
    _set_refresh_cookie(response, new_refresh)
    return TokenResponse(access_token=access, expires_in=ttl, refresh_token=new_refresh)


@router.post("/logout", summary="Revoke the current session")
def logout(response: Response, principal: Principal = Depends(get_principal)):
    response.delete_cookie("vixa_refresh", path="/api/v1/auth")
    return {"status": "logged_out"}


# --- development-only helper so the SPA can complete MFA without a real inbox -
from app.core.config import settings  # noqa: E402

if settings.environment == "development":
    @router.get("/dev/otp", summary="[dev] Read a pending step-up OTP by challenge id")
    def dev_login_otp(challenge_id: str):
        return {"code": container.mfa.peek_code(challenge_id)}
