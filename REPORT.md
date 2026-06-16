# ViXa Platform — CIAM Onboarding Flow

## Solution Report & API Design

*Backend: Python / FastAPI · Frontend: React · v1.0 Developed By: [Shahzaib Asif @ AI Engineer](mailto:shahzaib.asif024@gmail.com)*

---

## 1. Purpose of this submission

The brief asked for a delivery that **respects the full, comprehensive ViXa CIAM
architecture without simplifying it**, built with a **FastAPI backend** and a
**React frontend**, with the **API layer enhanced** and **professional
recommendations** added where appropriate.

This report explains how the implementation in this repository meets that brief.
It maps every architectural tier and workflow to the code that realises it,
documents the API-design decisions and enhancements, and sets out the
recommendations on security, performance, validation, error handling and state
management that the brief invited.

Nothing in the original architecture has been removed or abstracted away. Where
the brief left something under-specified (section 14 of the architecture
document), the design has been *strengthened*, not reduced.

---

## 2. Fidelity to the architecture — tier by tier

The architecture defines **eight logical tiers**. All eight are present in the
backend, organised so the package structure reads as the architecture diagram.

| # | Tier (architecture) | Where it lives | Notes |
| - | --- | --- | --- |
| 1 | Clients | `frontend/` | React/Vite SPA; talks only to the gateway over `/api`, attaching the JWT. |
| 2 | Edge & security | `app/main.py`, `app/core/rate_limit.py`, `app/gateway/` | Single entry point, TLS-terminating in prod, JWT validation, per-identity rate limiting, entitlement gate. |
| 3 | CIAM core | `app/ciam/{auth,mfa,orchestrator}` | Auth service, MFA/session, onboarding **saga** orchestrator. |
| 4 | Domain services | `app/domains/{organisation,verification,payments,licensing}` | One microservice-shaped module per slice of business logic. |
| 5 | Event backbone | `app/core/events.py`, `app/core/workers.py` | Pub/sub bus, retries with back-off, **dead-letter queue**, async workers. |
| 6 | System of record | `app/acl/anti_corruption.py` | **Anti-corruption layer** + Ost Infinity client; idempotent writes only. |
| 7 | Platform | `app/repositories/`, `app/core/audit.py` | Identity store (PostgreSQL stand-in), sessions (Redis stand-in), immutable audit log. |
| — | External edge | `app/adapters/providers.py` | reCAPTCHA, SMS/email, payment gateway, DNS — the one synchronous edge that leaves the spine. |

### Identity-first and the separation of concerns

The most important architectural decision (sections 6 and 7) is faithfully
implemented:

- **CIAM owns only the digital identity** — credentials and the user principal —
  in `IdentityRepository`. Nothing else lives there.
- **Ost Infinity is the authoritative record** for customer master data,
  organisations, sites, licences, subscription state and account status. Every
  write to it passes through the anti-corruption layer, which enforces
  idempotency keys so a retried saga step can never create a duplicate
  organisation or double-charge.
- **Products are not a tier inside CIAM.** Entitlement is an check that spans
  three tiers: Ost Infinity holds subscription state, the Licensing service
  resolves it into entitlements and stamps them into the JWT as claims, and the
  gateway enforces those claims when a product is opened. The products home
  renders only entitled tiles. This is exactly the model in section 6.

---

## 3. The onboarding saga

The onboarding journey is implemented as an **orchestrated saga** with
**compensating actions** (`app/ciam/orchestrator/saga.py`), grouped into the
five phases the architecture defines:

1. **Identity & organisation** — register, create the customer in Ost Infinity,
   create the organisation and sites (idempotent writes via the ACL).
2. **Human & contact verification** — reCAPTCHA gate, email OTP, mobile OTP.
3. **Payment** — card verification with the **€1 hold** over 3-D Secure
   (tokenised; the platform never sees card data).
4. **Domain** — auto-generated TXT record + DNS confirmation.
5. **Activation** — account flipped to *active*, membership recorded so login
   resolves the right entitlements.

Each completed step pushes a **compensating action** onto a stack. If a later
step fails irrecoverably, the orchestrator runs those compensations in reverse
(delete the organisation, delete the customer, remove the identity), records the
outcome in the audit log, and marks the saga `compensated`. Recoverable failures
(a declined card, a wrong OTP) do **not** compensate — the user simply retries
the step, because the saga persists its progress between calls and exposes a
`next_action` telling the client what to do next.

This directly answers the architecture's section 9: a failed or abandoned
onboarding can be safely resumed or compensated from its recorded progress.

---

## 4. All seventeen workflows

Every workflow in the architecture's section 10 is implemented and reachable
over the API:

| # | Workflow | Endpoint / mechanism |
| - | --- | --- |
| 1 | Account register | `POST /onboarding` (saga phase 1) |
| 2 | Organisation creation | saga phase 1 → Organisation service → ACL |
| 3 | Site(s) creation | saga phase 1 → Organisation service → ACL |
| 4 | reCAPTCHA verification | gate inside `POST /onboarding` |
| 5 | Email verification | `POST /onboarding/{id}/email` |
| 6 | Mobile verification | `POST /onboarding/{id}/mobile` |
| 7 | Card verification (€1 hold) | `POST /onboarding/{id}/card` |
| 8 | Login | `POST /auth/login` (+ `/auth/login/mfa`) |
| 9 | Update payment preferences | `PUT /admin/payment-preferences` |
| 10 | Domain verification | `GET /onboarding/{id}/domain-record` |
| 11 | Domain verified | `POST /onboarding/{id}/domain` → activation |
| 12 | Admin console | `GET /admin/organisation` (RBAC-gated) |
| 13 | Products & services home | `GET /products` |
| 14 | Department / structure | `POST /admin/organisation/departments` |
| 15 | Subscribe | `POST /subscribe` (publishes `payment.confirmed`) |
| 16 | Assign licence | async worker on `payment.confirmed` → Licensing → ACL |
| 17 | Suspend / close account | `POST /admin/accounts/{id}/status` |

---

## 5. API design and enhancements

The brief specifically asked to **enhance the API layer**. The following design
choices go beyond a flat CRUD surface.

**Versioned contract.** Everything is mounted under `/api/v1`. A future `/api/v2`
can introduce breaking changes side-by-side without disrupting existing clients.

**Async by default.** FastAPI is used as intended: request handlers are async,
slow work is pushed to the event backbone, and the user-facing path never blocks
on the bank or on licence provisioning. A confirmed subscription returns `202
Accepted` semantics — the licence is provisioned in the background.

**Strong typing and auto-documentation.** Every request and response is a typed
Pydantic model (`app/models/schemas.py`), giving validation, coercion and a
complete OpenAPI document at `/docs` for free — the FastAPI principles the brief
named (speed, type validation, automatic documentation).

**Consistent error contract.** All errors are returned as RFC 7807
`application/problem+json` with `type/title/status/detail/instance`
(`app/core/errors.py`). Validation failures include the field-level errors. The
frontend handles every failure uniformly.

**Saga-aware responses.** Onboarding endpoints return the saga state plus a
`next_action`, so the client is a thin state machine driven by the server rather
than hard-coding the flow.

**Entitlement and RBAC as composable dependencies.** `require_entitlement(product)`
and `require_admin` are FastAPI dependencies, so gating a route is a one-line
declaration and the gate is visible in the OpenAPI schema.

**Idempotency at the integration boundary.** Writes to Ost Infinity carry an
idempotency key (the saga id), so retried steps are safe by construction.

---

## 6. Security, privacy and compliance

Implemented per the architecture's section 12:

- **Token strategy.** Short-lived access JWTs (15 min) carrying entitlement
  claims, plus **rotating refresh tokens** delivered in an HTTP-only cookie.
  Refresh rotation includes **reuse detection**: replay of a superseded refresh
  token revokes the whole token family (`AuthService.refresh`).
- **Rate limiting.** Per-identity token-bucket limiter at the edge, with a
  tighter budget for sensitive routes (login, register, OTP, onboarding) to
  mitigate credential stuffing and OTP abuse.
- **MFA.** Risk-based step-up: admin sign-ins are challenged with an email OTP
  before tokens are issued.
- **PCI-DSS.** Card data is tokenised by the gateway adapter and never stored or
  logged by the platform, keeping it out of cardholder-data scope.
- **GDPR.** Explicit consent is captured and required at registration; the
  system-of-record separation supports erasure and subject-access requests.
- **Immutable audit log.** Every security-relevant action is appended to a
  **hash-chained** log (`app/core/audit.py`); `GET /system/audit` returns the
  tail and verifies the chain, so tampering is detectable.
- **No user enumeration.** Login returns an identical error for unknown-user and
  wrong-password.

---

## 7. Non-functional properties

- **Scalability.** Services are stateless; session/cache/rate-limit state is
  externalised (Redis in production). The event backbone absorbs load spikes.
- **Resilience.** The bus retries with back-off and dead-letters poison events;
  the saga's compensations keep the system consistent on failure.
- **Performance.** Authorisation on the hot path is a cheap claim check against
  the JWT — no database round-trip per navigation.
- **Observability.** Structured audit trail and a DLQ inspection endpoint
  (`GET /system/events/dead-letter`); health probe at `GET /system/health`.

---

## 8. Recommendations (delivered + forward-looking)

The brief invited professional recommendations. Those already **built in** are
marked ✓; the rest are the next steps for hardening toward production. The full
discussion is in [`docs/recommendations.md`](docs/recommendations.md).

- ✓ **API versioning** under `/api/v1`.
- ✓ **Idempotent integration** via the anti-corruption layer.
- ✓ **Async payment & provisioning** with retries and a DLQ.
- ✓ **Token strategy** with refresh rotation and reuse detection.
- ✓ **RFC 7807 error contract** and field-level validation.
- ✓ **Rate limiting** with a sensitive-route tier.
- ✓ **Hash-chained audit log**.
- → **Persistence**: swap the in-memory stores for PostgreSQL (`asyncpg` +
  SQLAlchemy/Alembic) and Redis; the interfaces already isolate this.
- → **Broker**: replace the in-process bus with Kafka/RabbitMQ (the `EventBus`
  interface is broker-shaped).
- → **Secrets**: source `JWT_SECRET` and provider keys from a vault.
- → **Key rotation / JWKS**: move to asymmetric signing (RS256) with a published
  JWKS endpoint so products can verify tokens without the shared secret.
- → **Observability**: OpenTelemetry traces + metrics into ELK/Datadog.
- → **DLQ replay UI** and circuit breakers around external providers.

---

## 9. What is mocked, and why it is safe to swap

To keep the MVP runnable with **zero infrastructure**, three categories are
in-memory stand-ins, each behind a narrow interface:

| Architecture component | Stand-in | Production drop-in |
| --- | --- | --- |
| PostgreSQL (identity) | `IdentityRepository` | `asyncpg` + SQLAlchemy |
| Redis (sessions, cache, rate limits) | `SessionRepository`, `_BUCKETS` | `redis-py` |
| Kafka/RabbitMQ (event backbone) | `EventBus` | broker client adapter |
| reCAPTCHA / SMS / email / gateway / DNS | `app/adapters/providers.py` | real SDKs |
| Ost Infinity | `OstInfinityClient` | HTTP client (ACL unchanged) |

Because callers depend on the interface, not the implementation, none of these
swaps touch business logic — which is the entire point of the layered, decoupled
design the architecture mandates.

---

## 10. How to verify the claims in this report

```bash
cd backend && pip install -r requirements.txt && pytest -q
```

The test suite drives the **complete saga** end-to-end (register → verify →
pay → domain → activate), proves **entitlement gating** before and after an
**asynchronous subscription**, exercises **refresh-token reuse detection** and
**rate limiting**, and verifies the **audit-log hash chain**. Then run the
backend and frontend (see the root README) to walk the same flow in the UI.
