"""Central configuration for the ViXa CIAM platform.

Values are read from the environment (see ``.env.example``) so the same image
runs in every environment without code changes. In production the secret keys
would be sourced from the secrets vault (see ``docs/recommendations.md``); here
they fall back to development defaults so the service boots with zero setup.
"""
from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="VIXA_", extra="ignore")

    # --- Service identity ---
    app_name: str = "ViXa CIAM"
    api_v1_prefix: str = "/api/v1"
    environment: str = "development"

    # --- JWT / token strategy -------------------------------------------------
    # Short-lived access token + long-lived rotating refresh token (section 12).
    jwt_secret: str = "dev-only-change-me-in-the-secrets-vault"
    jwt_algorithm: str = "HS256"
    access_token_ttl_seconds: int = 900           # 15 minutes
    refresh_token_ttl_seconds: int = 60 * 60 * 24 * 14  # 14 days
    jwt_issuer: str = "vixa-ciam"
    jwt_audience: str = "vixa-platform"

    # --- Rate limiting (gateway) ---------------------------------------------
    rate_limit_per_minute: int = 240          # default per-user / per-IP budget
    sensitive_rate_limit_per_minute: int = 40  # login, OTP, register, onboarding steps

    # --- MFA / OTP ------------------------------------------------------------
    otp_ttl_seconds: int = 300
    otp_length: int = 6

    # --- Payments -------------------------------------------------------------
    payment_hold_amount_cents: int = 100       # the "one-euro" verification hold
    payment_hold_currency: str = "EUR"
    payment_hold_days: int = 3

    # --- CORS -----------------------------------------------------------------
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
