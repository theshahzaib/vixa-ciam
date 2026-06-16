"""Immutable audit log (sections 5.7 and 12).

Every security-relevant action appends a record here. The log is append-only:
there is no update or delete method by design, which is what makes it suitable
for GDPR / PCI-DSS forensic requirements. Each entry chains to the previous one
via a hash so tampering is detectable.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional


@dataclass(frozen=True)
class AuditEntry:
    action: str
    actor: Optional[str]
    target: Optional[str]
    metadata: dict[str, Any]
    at: str
    prev_hash: str
    entry_hash: str = ""


class AuditLog:
    def __init__(self) -> None:
        self._entries: list[AuditEntry] = []

    def record(self, action: str, *, actor: str | None = None,
               target: str | None = None, **metadata: Any) -> AuditEntry:
        prev_hash = self._entries[-1].entry_hash if self._entries else "genesis"
        at = datetime.now(timezone.utc).isoformat()
        material = json.dumps(
            {"action": action, "actor": actor, "target": target,
             "metadata": metadata, "at": at, "prev_hash": prev_hash},
            sort_keys=True, default=str,
        )
        entry_hash = hashlib.sha256(material.encode()).hexdigest()
        entry = AuditEntry(action=action, actor=actor, target=target,
                           metadata=metadata, at=at, prev_hash=prev_hash,
                           entry_hash=entry_hash)
        self._entries.append(entry)
        return entry

    def verify_chain(self) -> bool:
        """Recompute the hash chain to detect tampering."""
        prev = "genesis"
        for e in self._entries:
            material = json.dumps(
                {"action": e.action, "actor": e.actor, "target": e.target,
                 "metadata": e.metadata, "at": e.at, "prev_hash": prev},
                sort_keys=True, default=str,
            )
            if hashlib.sha256(material.encode()).hexdigest() != e.entry_hash:
                return False
            prev = e.entry_hash
        return True

    def tail(self, n: int = 50) -> list[dict]:
        return [asdict(e) for e in self._entries[-n:]]


audit_log = AuditLog()
