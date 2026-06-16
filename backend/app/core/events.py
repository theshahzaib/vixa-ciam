"""Event backbone (section 5.5) — the asynchronous spine of the platform.

This is an in-process implementation of the pattern the architecture describes
with Kafka/RabbitMQ: publishers emit events, workers consume them, failures are
retried with back-off, and events that exhaust their retries land in a
dead-letter queue (DLQ) rather than being lost.

Keeping it in-process means the whole platform boots with zero infrastructure
for the assessment, while the ``EventBus`` interface is deliberately broker-shaped
so a real Kafka/RabbitMQ adapter can be dropped in without touching publishers
or handlers.
"""
from __future__ import annotations

import asyncio
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Awaitable, Callable

Handler = Callable[["Event"], Awaitable[None]]


@dataclass
class Event:
    type: str
    payload: dict
    id: str = field(default_factory=lambda: uuid.uuid4().hex)
    occurred_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    attempts: int = 0


@dataclass
class DeadLetter:
    event: Event
    error: str
    failed_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class EventBus:
    """Async pub/sub with at-least-once delivery, bounded retries and a DLQ."""

    def __init__(self, *, max_attempts: int = 3, base_backoff: float = 0.05):
        self._subscribers: dict[str, list[Handler]] = defaultdict(list)
        self._dlq: list[DeadLetter] = []
        self._published: list[Event] = []
        self._max_attempts = max_attempts
        self._base_backoff = base_backoff
        self._tasks: set[asyncio.Task] = set()

    def subscribe(self, event_type: str, handler: Handler) -> None:
        self._subscribers[event_type].append(handler)

    async def publish(self, event_type: str, payload: dict) -> Event:
        event = Event(type=event_type, payload=payload)
        self._published.append(event)
        for handler in self._subscribers.get(event_type, []):
            task = asyncio.create_task(self._deliver(handler, event))
            self._tasks.add(task)
            task.add_done_callback(self._tasks.discard)
        return event

    async def _deliver(self, handler: Handler, event: Event) -> None:
        last_error = ""
        for attempt in range(1, self._max_attempts + 1):
            event.attempts = attempt
            try:
                await handler(event)
                return
            except Exception as exc:  # noqa: BLE001 — worker must not crash the bus
                last_error = f"{type(exc).__name__}: {exc}"
                await asyncio.sleep(self._base_backoff * attempt)  # linear back-off
        # Exhausted retries → dead-letter for later inspection / replay.
        self._dlq.append(DeadLetter(event=event, error=last_error))

    async def drain(self) -> None:
        """Await all in-flight handlers — used by tests and graceful shutdown."""
        while self._tasks:
            await asyncio.gather(*list(self._tasks), return_exceptions=True)

    @property
    def dead_letters(self) -> list[DeadLetter]:
        return list(self._dlq)

    @property
    def published(self) -> list[Event]:
        return list(self._published)


# Canonical event names (kept central so producers and consumers agree).
class Topics:
    PAYMENT_CONFIRMED = "payment.confirmed"
    PAYMENT_FAILED = "payment.failed"
    LICENCE_PROVISION_REQUESTED = "licence.provision_requested"
    LICENCE_PROVISIONED = "licence.provisioned"
    NOTIFICATION_REQUESTED = "notification.requested"
    ACCOUNT_ACTIVATED = "account.activated"


# Single shared bus for the running application (wired in app.main).
bus = EventBus()
