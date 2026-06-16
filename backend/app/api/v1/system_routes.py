"""System & observability routes (section 13) — health, audit, DLQ visibility."""
from __future__ import annotations

from fastapi import APIRouter

from app.core.audit import audit_log
from app.core.events import bus

router = APIRouter(prefix="/system", tags=["system"])


@router.get("/health", summary="Liveness/readiness probe")
def health():
    return {"status": "ok"}


@router.get("/audit", summary="Tail of the immutable audit log (verifiable hash chain)")
def audit(n: int = 50):
    return {"chain_valid": audit_log.verify_chain(), "entries": audit_log.tail(n)}


@router.get("/events/dead-letter", summary="Dead-letter queue contents")
async def dead_letter():
    await bus.drain()
    return {
        "dead_letters": [
            {"event_type": dl.event.type, "attempts": dl.event.attempts,
             "error": dl.error, "failed_at": dl.failed_at.isoformat()}
            for dl in bus.dead_letters
        ],
        "published_count": len(bus.published),
    }
