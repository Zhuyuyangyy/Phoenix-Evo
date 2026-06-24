"""Shared safety memory for multi-agent systems."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class SafetyMemoryEntry:
    """An entry in the shared safety memory."""
    entry_id: str
    category: str  # e.g., "violation", "near_miss", "best_practice"
    description: str
    reporter_id: str
    timestamp: float = field(default_factory=time.time)
    severity: float = 0.5  # 0.0 to 1.0
    context: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)


class SharedSafetyMemory:
    """Shared memory for safety-related information across agents.

    Allows agents to share safety violations, near-misses, and
    best practices so that all agents can learn from each other's
    experiences.
    """

    def __init__(self, max_entries: int = 10000):
        self.max_entries = max_entries
        self._entries: Dict[str, SafetyMemoryEntry] = {}
        self._category_index: Dict[str, List[str]] = {}
        self._tag_index: Dict[str, List[str]] = {}

    def store(self, entry: SafetyMemoryEntry) -> None:
        """Store a safety memory entry."""
        self._entries[entry.entry_id] = entry

        # Update category index
        self._category_index.setdefault(entry.category, []).append(entry.entry_id)

        # Update tag index
        for tag in entry.tags:
            self._tag_index.setdefault(tag, []).append(entry.entry_id)

        # Evict oldest if over limit
        if len(self._entries) > self.max_entries:
            oldest_id = min(self._entries, key=lambda k: self._entries[k].timestamp)
            self._remove(oldest_id)

    def _remove(self, entry_id: str) -> None:
        """Remove an entry and clean up indices."""
        entry = self._entries.pop(entry_id, None)
        if entry:
            if entry.category in self._category_index:
                self._category_index[entry.category] = [
                    e for e in self._category_index[entry.category] if e != entry_id
                ]
            for tag in entry.tags:
                if tag in self._tag_index:
                    self._tag_index[tag] = [
                        e for e in self._tag_index[tag] if e != entry_id
                    ]

    def retrieve(self, entry_id: str) -> Optional[SafetyMemoryEntry]:
        """Retrieve a specific entry."""
        return self._entries.get(entry_id)

    def query_by_category(self, category: str) -> List[SafetyMemoryEntry]:
        """Query entries by category."""
        entry_ids = self._category_index.get(category, [])
        return [self._entries[eid] for eid in entry_ids if eid in self._entries]

    def query_by_tag(self, tag: str) -> List[SafetyMemoryEntry]:
        """Query entries by tag."""
        entry_ids = self._tag_index.get(tag, [])
        return [self._entries[eid] for eid in entry_ids if eid in self._entries]

    def query_recent(self, n: int = 10) -> List[SafetyMemoryEntry]:
        """Get the N most recent entries."""
        sorted_entries = sorted(
            self._entries.values(), key=lambda e: e.timestamp, reverse=True
        )
        return sorted_entries[:n]

    def query_by_severity(self, min_severity: float = 0.0) -> List[SafetyMemoryEntry]:
        """Query entries above a severity threshold."""
        return [
            e for e in self._entries.values()
            if e.severity >= min_severity
        ]

    def get_violations(self) -> List[SafetyMemoryEntry]:
        """Get all violation entries."""
        return self.query_by_category("violation")

    def get_near_misses(self) -> List[SafetyMemoryEntry]:
        """Get all near-miss entries."""
        return self.query_by_category("near_miss")

    def get_best_practices(self) -> List[SafetyMemoryEntry]:
        """Get all best practice entries."""
        return self.query_by_category("best_practice")

    def summary(self) -> Dict[str, Any]:
        """Get a summary of the shared safety memory."""
        return {
            "total_entries": len(self._entries),
            "categories": {
                cat: len(ids) for cat, ids in self._category_index.items()
            },
            "top_tags": {
                tag: len(ids) for tag, ids in sorted(
                    self._tag_index.items(),
                    key=lambda x: len(x[1]),
                    reverse=True,
                )[:10]
            },
        }
