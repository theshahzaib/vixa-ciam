# Architecture — implementation notes

This document records how the runtime architecture behaves, complementing the
tier-by-tier mapping in [`../REPORT.md`](../REPORT.md).

## Communication model (section 8)

The platform communicates in two ways, and the code keeps them distinct:

- **Synchronous spine.** Client → gateway → CIAM core → domain service → ACL →
  Ost Infinity, with each hop returning up the chain. Used whenever the user is
  waiting: login, loading the admin console, submitting a saga step.
- **Asynchronous loop.** A domain service that completes work with downstream
  consequences (a confirmed payment) publishes an event rather than calling the
  next step directly. Workers then provision the licence and send notifications,
  writing results back through the ACL.

The single synchronous edge that leaves the spine is the domain services' call
to external providers (SMS, card redirect, DNS), because those genuinely wait on
a third party.

## Runtime flow of a subscription (workflows 15 → 16)

```
POST /subscribe
   └─ PaymentsService.subscribe()
        ├─ gateway.charge_subscription()          (sync, external edge)
        └─ bus.publish("payment.confirmed")       (async hand-off)
                 │
                 ▼  worker (app/core/workers.py)
        LicensingService.provision_licence()
        ├─ ACL.record_subscription() → Ost Infinity
        └─ bus.publish("notification.requested")
                 │
                 ▼  worker
        NotificationAdapter.send_email()
```

The user's request returns immediately after the event is published. The new
entitlement is picked up on the next token cycle (re-login or refresh), so a slow
provider never blocks the UI — exactly the behaviour section 8 describes.

## Saga state machine

```
identity_and_org ──▶ human_and_contact ──▶ payment ──▶ domain ──▶ activation ──▶ completed
        │                    │                 │           │
        └──────────── compensate (reverse-order rollback) ─┘   (irrecoverable failures only)
```

`next_action` is returned on every saga response so the client never hard-codes
the order of steps.

## Why the anti-corruption layer matters

Without it, the CIAM domain model and the Ost Infinity data model would couple,
and a change on either side would ripple across the platform. The ACL translates
between the two and enforces idempotency keys, so:

- the two models evolve independently, and
- a retried registration step cannot create a duplicate organisation or customer.

This is called out in the architecture as the single most important decision for
maintainability (section 7), and it is implemented as the *only* path from CIAM
into the system of record.
