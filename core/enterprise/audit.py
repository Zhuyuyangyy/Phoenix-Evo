"""Audit logging with SHA-256 hash chain for Phoenix-Evo enterprise features."""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class AuditEvent:
    """A single audit event."""
    event_id: str
    event_type: str
    actor_id: str
    resource_type: str
    resource_id: str
    action: str
    timestamp: float = field(default_factory=time.time)
    details: Dict[str, Any] = field(default_factory=dict)
    prev_hash: str = ""
    hash: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def compute_hash(self) -> str:
        """Compute the SHA-256 hash of this event."""
        payload = json.dumps({
            "event_id": self.event_id,
            "event_type": self.event_type,
            "actor_id": self.actor_id,
            "resource_type": self.resource_type,
            "resource_id": self.resource_id,
            "action": self.action,
            "timestamp": self.timestamp,
            "details": self.details,
            "prev_hash": self.prev_hash,
        }, sort_keys=True, default=str)
        return hashlib.sha256(payload.encode()).hexdigest()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "actor_id": self.actor_id,
            "resource_type": self.resource_type,
            "resource_id": self.resource_id,
            "action": self.action,
            "timestamp": self.timestamp,
            "details": self.details,
            "prev_hash": self.prev_hash,
            "hash": self.hash,
            "metadata": self.metadata,
        }


class AuditLog:
    """Immutable audit log with SHA-256 hash chain.

    Each event's hash includes the previous event's hash,
    creating a tamper-evident chain similar to a blockchain.
    """

    GENESIS_HASH = "0" * 64

    def __init__(self):
        self._events: List[AuditEvent] = []
        self._event_counter = 0

    def record(
        self,
        event_type: str,
        actor_id: str,
        resource_type: str,
        resource_id: str,
        action: str,
        details: Optional[Dict[str, Any]] = None,
    ) -> AuditEvent:
        """Record a new audit event."""
        self._event_counter += 1
        event_id = f"audit_{self._event_counter:06d}"

        prev_hash = self._events[-1].hash if self._events else self.GENESIS_HASH

        event = AuditEvent(
            event_id=event_id,
            event_type=event_type,
            actor_id=actor_id,
            resource_type=resource_type,
            resource_id=resource_id,
            action=action,
            details=details or {},
            prev_hash=prev_hash,
        )
        event.hash = event.compute_hash()
        self._events.append(event)
        return event

    def verify_chain(self) -> Dict[str, Any]:
        """Verify the integrity of the hash chain.

        Returns a dict with 'valid' (bool) and 'first_invalid' (int or None).
        """
        prev_hash = self.GENESIS_HASH
        for i, event in enumerate(self._events):
            # Check prev_hash linkage
            if event.prev_hash != prev_hash:
                return {"valid": False, "first_invalid": i, "reason": "prev_hash_mismatch"}

            # Recompute hash
            expected_hash = event.compute_hash()
            if event.hash != expected_hash:
                return {"valid": False, "first_invalid": i, "reason": "hash_mismatch"}

            prev_hash = event.hash

        return {"valid": True, "first_invalid": None, "chain_length": len(self._events)}

    def get_events(
        self,
        event_type: Optional[str] = None,
        actor_id: Optional[str] = None,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        start_time: Optional[float] = None,
        end_time: Optional[float] = None,
        limit: int = 100,
    ) -> List[AuditEvent]:
        """Query audit events with optional filters."""
        results = []
        for event in reversed(self._events):
            if event_type and event.event_type != event_type:
                continue
            if actor_id and event.actor_id != actor_id:
                continue
            if resource_type and event.resource_type != resource_type:
                continue
            if resource_id and event.resource_id != resource_id:
                continue
            if start_time and event.timestamp < start_time:
                continue
            if end_time and event.timestamp > end_time:
                continue
            results.append(event)
            if len(results) >= limit:
                break
        return list(reversed(results))

    def get_event(self, event_id: str) -> Optional[AuditEvent]:
        """Get a specific event by ID."""
        for event in self._events:
            if event.event_id == event_id:
                return event
        return None

    def export(self) -> List[Dict[str, Any]]:
        """Export all events as a list of dicts."""
        return [e.to_dict() for e in self._events]

    @property
    def size(self) -> int:
        """Number of events in the log."""
        return len(self._events)
