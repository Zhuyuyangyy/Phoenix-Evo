"""Conflict resolution for distributed Phoenix-Evo system."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ConflictType(Enum):
    VERSION_CONFLICT = "version_conflict"
    DATA_CONFLICT = "data_conflict"
    SIMULTANEOUS_UPDATE = "simultaneous_update"
    PARTITION_CONFLICT = "partition_conflict"


class ResolutionStrategy(Enum):
    LAST_WRITE_WINS = "last_write_wins"
    HIGHEST_VERSION = "highest_version"
    MERGE = "merge"
    MANUAL = "manual"
    SOURCE_PRIORITY = "source_priority"


@dataclass
class Conflict:
    """A conflict between distributed data."""
    conflict_id: str
    conflict_type: ConflictType
    resource_id: str
    left_version: dict[str, Any]
    right_version: dict[str, Any]
    detected_at: float = field(default_factory=time.time)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class Resolution:
    """A conflict resolution result."""
    resolution_id: str
    conflict_id: str
    strategy: ResolutionStrategy
    resolved_data: dict[str, Any]
    winner: str  # "left", "right", "merge", or "manual"
    resolved_at: float = field(default_factory=time.time)
    metadata: dict[str, Any] = field(default_factory=dict)


class ConflictResolver:
    """Resolves conflicts in distributed skill data.

    Supports multiple resolution strategies for different
    types of conflicts.
    """

    def __init__(
        self,
        default_strategy: ResolutionStrategy = ResolutionStrategy.LAST_WRITE_WINS,
        source_priorities: dict[str, int] | None = None,
    ):
        self.default_strategy = default_strategy
        self.source_priorities = source_priorities or {}
        self._conflicts: list[Conflict] = []
        self._resolutions: list[Resolution] = []
        self._conflict_counter = 0

    def detect_conflict(
        self,
        resource_id: str,
        left_version: dict[str, Any],
        right_version: dict[str, Any],
    ) -> Conflict | None:
        """Detect a conflict between two versions of a resource."""
        if left_version == right_version:
            return None

        # Determine conflict type
        left_ver = left_version.get("version", "0")
        right_ver = right_version.get("version", "0")
        left_ts = left_version.get("timestamp", 0)
        right_ts = right_version.get("timestamp", 0)

        if left_ver != right_ver:
            conflict_type = ConflictType.VERSION_CONFLICT
        elif abs(left_ts - right_ts) < 1.0:
            conflict_type = ConflictType.SIMULTANEOUS_UPDATE
        else:
            conflict_type = ConflictType.DATA_CONFLICT

        self._conflict_counter += 1
        conflict = Conflict(
            conflict_id=f"conflict_{self._conflict_counter:06d}",
            conflict_type=conflict_type,
            resource_id=resource_id,
            left_version=left_version,
            right_version=right_version,
        )
        self._conflicts.append(conflict)
        return conflict

    def resolve(
        self,
        conflict: Conflict,
        strategy: ResolutionStrategy | None = None,
    ) -> Resolution:
        """Resolve a conflict using the specified strategy."""
        strat = strategy or self.default_strategy

        if strat == ResolutionStrategy.LAST_WRITE_WINS:
            return self._resolve_last_write_wins(conflict)
        if strat == ResolutionStrategy.HIGHEST_VERSION:
            return self._resolve_highest_version(conflict)
        if strat == ResolutionStrategy.MERGE:
            return self._resolve_merge(conflict)
        if strat == ResolutionStrategy.SOURCE_PRIORITY:
            return self._resolve_source_priority(conflict)
        return self._resolve_manual(conflict)

    def _resolve_last_write_wins(self, conflict: Conflict) -> Resolution:
        """Resolve by selecting the most recently updated version."""
        left_ts = conflict.left_version.get("timestamp", 0)
        right_ts = conflict.right_version.get("timestamp", 0)

        if left_ts >= right_ts:
            winner = "left"
            resolved_data = dict(conflict.left_version)
        else:
            winner = "right"
            resolved_data = dict(conflict.right_version)

        return self._create_resolution(conflict, ResolutionStrategy.LAST_WRITE_WINS, winner, resolved_data)

    def _resolve_highest_version(self, conflict: Conflict) -> Resolution:
        """Resolve by selecting the highest version number."""
        left_ver = conflict.left_version.get("version", "0")
        right_ver = conflict.right_version.get("version", "0")

        if left_ver >= right_ver:
            winner = "left"
            resolved_data = dict(conflict.left_version)
        else:
            winner = "right"
            resolved_data = dict(conflict.right_version)

        return self._create_resolution(conflict, ResolutionStrategy.HIGHEST_VERSION, winner, resolved_data)

    def _resolve_merge(self, conflict: Conflict) -> Resolution:
        """Resolve by merging both versions (right takes precedence for conflicts)."""
        merged = dict(conflict.left_version)
        merged.update(conflict.right_version)
        return self._create_resolution(conflict, ResolutionStrategy.MERGE, "merge", merged)

    def _resolve_source_priority(self, conflict: Conflict) -> Resolution:
        """Resolve based on source priority."""
        left_source = conflict.left_version.get("source", "")
        right_source = conflict.right_version.get("source", "")

        left_priority = self.source_priorities.get(left_source, 0)
        right_priority = self.source_priorities.get(right_source, 0)

        if left_priority >= right_priority:
            winner = "left"
            resolved_data = dict(conflict.left_version)
        else:
            winner = "right"
            resolved_data = dict(conflict.right_version)

        return self._create_resolution(conflict, ResolutionStrategy.SOURCE_PRIORITY, winner, resolved_data)

    def _resolve_manual(self, conflict: Conflict) -> Resolution:
        """Mark conflict for manual resolution."""
        return self._create_resolution(
            conflict, ResolutionStrategy.MANUAL, "manual",
            {"status": "pending_manual_resolution"},
        )

    def _create_resolution(
        self,
        conflict: Conflict,
        strategy: ResolutionStrategy,
        winner: str,
        resolved_data: dict[str, Any],
    ) -> Resolution:
        """Create a resolution object."""
        resolution = Resolution(
            resolution_id=f"res_{len(self._resolutions) + 1:06d}",
            conflict_id=conflict.conflict_id,
            strategy=strategy,
            resolved_data=resolved_data,
            winner=winner,
        )
        self._resolutions.append(resolution)
        return resolution

    def get_conflicts(self, unresolved_only: bool = False) -> list[Conflict]:
        """Get conflicts, optionally only unresolved ones."""
        if unresolved_only:
            resolved_ids = {r.conflict_id for r in self._resolutions if r.winner != "manual"}
            return [c for c in self._conflicts if c.conflict_id not in resolved_ids]
        return list(self._conflicts)

    def get_resolutions(self) -> list[Resolution]:
        """Get all resolutions."""
        return list(self._resolutions)

    def get_stats(self) -> dict[str, Any]:
        """Get conflict resolution statistics."""
        return {
            "total_conflicts": len(self._conflicts),
            "total_resolutions": len(self._resolutions),
            "by_strategy": {
                s.value: sum(1 for r in self._resolutions if r.strategy == s)
                for s in ResolutionStrategy
            },
            "by_type": {
                t.value: sum(1 for c in self._conflicts if c.conflict_type == t)
                for t in ConflictType
            },
        }
