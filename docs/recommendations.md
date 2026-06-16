# Recommendations

These expand on the architecture's section 14 ("gaps and recommendations") and
distinguish what is **already implemented** from what is **recommended next**.

## Implemented in this delivery

- **Onboarding saga with compensation.** The multi-step onboarding is a
  distributed transaction with reverse-order compensating actions, not a flat
  call sequence.
- **Anti-corruption layer.** An explicit, idempotent boundary between CIAM and
  Ost Infinity.
- **Async payment & provisioning.** Payment confirmation and licence
  provisioning run on the event backbone with retries and a dead-letter queue.
- **Defensive edge.** Per-identity rate limiting with a tighter sensitive-route
  budget. (WAF/CDN are infrastructure concerns, see below.)
- **Token strategy.** Short-lived access tokens + rotating refresh tokens with
  reuse detection.
- **Compliance posture.** Card tokenisation (PCI-DSS scope reduction), GDPR
  consent capture, hash-chained audit log.
- **API hygiene.** Versioning, RFC 7807 errors, typed contracts, OpenAPI docs.

## Recommended next (toward production)

### Data & messaging
- **PostgreSQL** for identity/credentials via `asyncpg` + SQLAlchemy, with
  Alembic migrations. The `IdentityRepository` interface already isolates this.
- **Redis** for sessions, cache and rate-limit buckets so state is shared across
  gateway instances.
- **Kafka or RabbitMQ** behind the existing `EventBus` interface; add a DLQ
  replay tool and consumer-group scaling.

### Security
- **Asymmetric JWT signing (RS256/EdDSA)** with a published **JWKS** endpoint so
  products verify tokens without sharing the signing secret; add key rotation.
- **Secrets vault** (e.g. HashiCorp Vault, AWS/GCP secrets manager) for the
  signing key and provider credentials — nothing hard-coded.
- **WAF + CDN** at the edge for DDoS and OWASP-class protection (infrastructure).
- **Step-up policy engine** driven by a real risk score (device, geo, velocity)
  rather than a role check.
- **Webhook signature verification** and replay protection on payment callbacks
  (handlers are already idempotent).

### Reliability & operations
- **Circuit breakers** and timeouts around every external provider call.
- **OpenTelemetry** traces/metrics into ELK or Datadog; alert on error rate and
  latency.
- **Outbox pattern** for the publish step so a crash between the DB write and the
  event publish cannot lose an event.

### Data modelling
- Promote the entitlement model to first-class **products × plans × features**
  so gating can be feature-level, not just product-level.
- Add **optimistic concurrency** (version columns) on organisation/site records
  in Ost Infinity to complement idempotency keys.
