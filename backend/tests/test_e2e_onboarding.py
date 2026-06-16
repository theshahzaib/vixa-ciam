"""End-to-end tests for the ViXa CIAM platform.

These drive the full onboarding saga through the public API, then exercise
login, entitlement gating and asynchronous licence provisioning. Running them is
the fastest way to see the whole architecture work end to end.
"""
from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

REG = {
    "email": "founder@acme-corp.com",
    "password": "Sup3rSecret!pw",
    "full_name": "Ada Founder",
    "recaptcha_token": "human",
    "consent_gdpr": True,
    "organisation": {
        "name": "Acme Corp", "country": "UK", "city": "London",
        "address": "1 High St", "postcode": "EC1A 1BB", "telephone": "+44 20 7946 0000",
        "directors": ["Ada Founder"],
    },
    "sites": [{"name": "HQ", "location": "London", "responsible_managers": ["Ada Founder"]}],
}


def _complete_onboarding() -> str:
    """Run the saga end to end and return the activated organisation id."""
    r = client.post("/api/v1/onboarding", json=REG)
    assert r.status_code == 201, r.text
    saga = r.json()
    sid = saga["saga_id"]
    assert saga["phase"] == "human_and_contact"
    assert saga["next_action"] == "verify_email"

    otps = client.get(f"/api/v1/onboarding/{sid}/dev/otp").json()
    r = client.post(f"/api/v1/onboarding/{sid}/email",
                    json={"challenge_id": "", "code": otps["email_code"]})
    assert r.json()["next_action"] == "verify_mobile", r.text

    otps = client.get(f"/api/v1/onboarding/{sid}/dev/otp").json()
    r = client.post(f"/api/v1/onboarding/{sid}/mobile",
                    json={"challenge_id": "", "code": otps["mobile_code"]})
    assert r.json()["next_action"] == "verify_card", r.text

    r = client.post(f"/api/v1/onboarding/{sid}/card",
                    json={"payment_method_token": "tok_visa_ok"})
    assert r.json()["next_action"] == "verify_domain", r.text

    r = client.post(f"/api/v1/onboarding/{sid}/domain")
    final = r.json()
    assert final["status"] == "completed", r.text
    assert final["phase"] == "completed"
    return final["organisation_id"]


def test_full_onboarding_saga_completes():
    org_id = _complete_onboarding()
    assert org_id.startswith("org_")


def test_recaptcha_failure_compensates():
    bad = {**REG, "email": "bot@example.org", "recaptcha_token": "bot"}
    r = client.post("/api/v1/onboarding", json=bad)
    assert r.status_code == 400
    assert "Automated traffic" in r.json()["detail"]


def test_login_entitlement_and_async_subscription():
    _complete_onboarding()

    # Admin login triggers MFA step-up.
    r = client.post("/api/v1/auth/login",
                    json={"email": REG["email"], "password": REG["password"]})
    body = r.json()
    assert body.get("mfa_required") is True, body
    challenge_id = body["challenge_id"]

    # Complete step-up. The dev OTP endpoint isn't tied to a saga here, so read it
    # from the notifications outbox instead.
    from app.adapters.providers import notifications
    code = [m.body for m in notifications.outbox if "verification code" in m.body][-1].split()[5]
    r = client.post("/api/v1/auth/login/mfa",
                    params={"challenge_id": challenge_id, "code": code, "email": REG["email"]})
    assert r.status_code == 200, r.text
    token = r.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Products home: base product entitled, others upsell.
    home = client.get("/api/v1/products", headers=headers).json()
    states = {t["id"]: t["state"] for t in home["tiles"]}
    assert states["vixa_platform"] == "active"
    assert states["vixa_vault"] == "upsell"

    # Gated resource refused before subscribing.
    assert client.get("/api/v1/products/vault/open", headers=headers).status_code == 403

    # Subscribe (async provisioning), then re-login to refresh entitlements.
    r = client.post("/api/v1/subscribe", headers=headers,
                    json={"product": "vixa_vault", "payment_method_token": "tok_ok"})
    assert r.json()["status"] == "accepted", r.text

    # Drain the event bus so the worker provisions the licence.
    client.get("/api/v1/system/events/dead-letter")

    # New token now carries the vault entitlement.
    r = client.post("/api/v1/auth/login",
                    json={"email": REG["email"], "password": REG["password"]})
    challenge_id = r.json()["challenge_id"]
    code = [m.body for m in notifications.outbox if "verification code" in m.body][-1].split()[5]
    token = client.post("/api/v1/auth/login/mfa",
                        params={"challenge_id": challenge_id, "code": code,
                                "email": REG["email"]}).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    assert client.get("/api/v1/products/vault/open", headers=headers).status_code == 200


def test_audit_chain_is_valid():
    _complete_onboarding()
    r = client.get("/api/v1/system/audit").json()
    assert r["chain_valid"] is True
    assert len(r["entries"]) > 0
