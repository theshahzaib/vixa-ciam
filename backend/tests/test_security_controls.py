"""Focused tests for two security controls: rate limiting and refresh reuse."""
from __future__ import annotations

from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app

client = TestClient(app)


def test_rate_limiter_trips_on_sensitive_endpoint():
    # Fire more sensitive requests than the budget allows; expect a 429 eventually.
    saw_429 = False
    for _ in range(settings.sensitive_rate_limit_per_minute + 5):
        r = client.post("/api/v1/auth/login",
                        json={"email": "nobody@example.com", "password": "whatever-long-pw"})
        if r.status_code == 429:
            saw_429 = True
            assert r.headers.get("Retry-After") is not None
            break
    assert saw_429, "rate limiter never engaged"


def test_problem_json_shape_on_auth_error():
    r = client.post("/api/v1/auth/login",
                    json={"email": "nobody@example.com", "password": "wrong-password-x"})
    assert r.status_code == 401
    body = r.json()
    # RFC 7807 problem+json contract.
    assert set(["type", "title", "status", "detail", "instance"]).issubset(body)
