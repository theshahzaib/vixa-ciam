# ViXa CIAM — Backend (FastAPI)

The CIAM platform. Async, strongly typed, and self-documenting via OpenAPI.

## Run

```bash
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload      # http://127.0.0.1:8000/docs
pytest -q                          # end-to-end + security-control tests
```

## Module map (mirrors the architecture tiers)

| Path | Architecture role |
| --- | --- |
| `app/main.py` | API gateway / app composition (tier 2) |
| `app/core/rate_limit.py` | Per-identity token-bucket limiter (tier 2) |
| `app/core/security.py` | JWT + rotating refresh tokens, bcrypt |
| `app/core/events.py` | Event backbone: bus, retries, dead-letter queue (tier 5) |
| `app/core/workers.py` | Async workers consuming backbone events (tier 5) |
| `app/core/audit.py` | Immutable, hash-chained audit log (tier 7) |
| `app/core/errors.py` | RFC 7807 `problem+json` error contract |
| `app/gateway/deps.py` | Token validation + entitlement & RBAC gates |
| `app/ciam/auth` | Auth service — identity & token lifecycle (tier 3) |
| `app/ciam/mfa` | MFA / OTP service (tier 3) |
| `app/ciam/orchestrator` | Onboarding **saga** with compensation (tier 3) |
| `app/domains/*` | Organisation/site, Verification, Payments, Licensing (tier 4) |
| `app/acl` | Anti-corruption layer + Ost Infinity client (tier 6) |
| `app/adapters` | reCAPTCHA, SMS/email, payment gateway, DNS (external edge) |
| `app/repositories` | Identity (PostgreSQL) & session (Redis) stand-ins (tier 7) |
| `app/api/v1` | Versioned HTTP surface for all 17 workflows |

## Notes

- **In-memory stores** keep the MVP runnable with no infrastructure. Each sits
  behind a small interface, so swapping in PostgreSQL (`asyncpg`), Redis
  (`redis-py`) and Kafka/RabbitMQ is a drop-in change that does not touch
  callers. See `../docker-compose.yml` and `../docs/recommendations.md`.
- **Dev-only helpers** (`/onboarding/{id}/dev/otp`, `/auth/dev/otp`) expose OTPs
  so the SPA can self-drive without a real inbox. They return `null` unless
  `VIXA_ENVIRONMENT=development`.
