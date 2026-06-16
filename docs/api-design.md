# API design reference

Base URL: `/api/v1` · Interactive docs: `/docs` · Schema: `/api/v1/openapi.json`

## Conventions

- **Auth:** `Authorization: Bearer <access_token>`. The refresh token is an
  HTTP-only cookie (`vixa_refresh`); `POST /auth/refresh` rotates it.
- **Errors:** RFC 7807 `application/problem+json`
  (`{type, title, status, detail, instance}`); validation errors add `errors`.
- **Versioning:** breaking changes ship under a new prefix (`/api/v2`).
- **Idempotency:** saga writes to the system of record are idempotent on the
  saga id.

## Endpoints

### Onboarding (the saga)

| Method | Path | Purpose |
| --- | --- | --- |
| POST | `/onboarding` | Start: register identity, create org + sites. Returns saga state. |
| POST | `/onboarding/{id}/email` | Verify email OTP. |
| POST | `/onboarding/{id}/mobile` | Verify mobile OTP. |
| POST | `/onboarding/{id}/card` | Card verification (€1 hold, 3-D Secure). |
| GET  | `/onboarding/{id}/domain-record` | Fetch the TXT record to publish. |
| POST | `/onboarding/{id}/domain` | Confirm DNS and activate the account. |
| GET  | `/onboarding/{id}` | Current saga state + `next_action`. |

### Auth

| Method | Path | Purpose |
| --- | --- | --- |
| POST | `/auth/login` | Authenticate; returns tokens or an MFA challenge. |
| POST | `/auth/login/mfa` | Complete step-up; returns tokens. |
| POST | `/auth/refresh` | Rotate refresh token, mint new access token. |
| POST | `/auth/logout` | Revoke the session. |

### Products & subscriptions

| Method | Path | Purpose |
| --- | --- | --- |
| GET  | `/products` | Products home — entitled tiles active, others upsell. |
| POST | `/subscribe` | Subscribe (async provisioning). |
| GET  | `/products/vault/open` | Example entitlement-gated resource. |

### Admin (RBAC: admin role required)

| Method | Path | Purpose |
| --- | --- | --- |
| GET  | `/admin/organisation` | Organisation overview. |
| POST | `/admin/organisation/departments` | Create department/structure. |
| PUT  | `/admin/payment-preferences` | Update payment preferences. |
| POST | `/admin/accounts/{id}/status` | Suspend / close an account. |

### System / observability

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/system/health` | Liveness/readiness probe. |
| GET | `/system/audit` | Audit-log tail + hash-chain validity. |
| GET | `/system/events/dead-letter` | DLQ contents + published count. |

## JWT claims

```jsonc
{
  "iss": "vixa-ciam", "aud": "vixa-platform",
  "sub": "usr_…",            // identity id
  "typ": "access",
  "roles": ["admin"],         // RBAC
  "ent":  ["vixa_platform"],  // entitlements — what the gateway gate checks
  "org":  "org_…",            // organisation context
  "exp": 0, "iat": 0, "jti": "…"
}
```

Refresh tokens carry `typ: "refresh"` and a `fam` (family) claim used for
rotation and reuse detection.
