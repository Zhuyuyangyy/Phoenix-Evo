"""Replay comparator for Phoenix-Evo regression testing."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class ComparisonResult:
    """Result of comparing two trajectories."""
    case_id: str
    match: bool
    similarity_score: float
    differences: List[Dict[str, Any]] = field(default_factory=list)
    critical_differences: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


class ReplayComparator:
    """Compares replay trajectories against expected outcomes.

    Supports multiple comparison strategies:
    - Exact match
    - Semantic similarity
    - Structural comparison
    - Safety-critical comparison
    """

    def __init__(
        self,
        similarity_threshold: float = 0.9,
        critical_field_exact_match: bool = True,
    ):
        self.similarity_threshold = similarity_threshold
        self.critical_field_exact_match = critical_field_exact_match

    def compare(
        self,
        actual: Dict[str, Any],
        expected: Dict[str, Any],
        case_id: str = "",
    ) -> ComparisonResult:
        """Compare an actual trajectory against expected outcome."""
        differences = []
        critical_diffs = []

        # Compare top-level fields
        for key in set(list(actual.keys()) + list(expected.keys())):
            actual_val = actual.get(key)
            expected_val = expected.get(key)

            if actual_val != expected_val:
                diff = {
                    "field": key,
                    "actual": actual_val,
                    "expected": expected_val,
                }
                differences.append(diff)

                # Check if this is a critical field
                if key in ("success", "safety_violations", "risk_signal"):
                    critical_diffs.append(diff)

        # Compare events
        actual_events = actual.get("events", [])
        expected_events = expected.get("events", [])
        event_diffs = self._compare_events(actual_events, expected_events)
        differences.extend(event_diffs)

        # Compute similarity score
        total_fields = max(len(set(list(actual.keys()) + list(expected.keys()))), 1)
        matching_fields = total_fields - len(differences)
        similarity = matching_fields / total_fields

        # Determine match
        match = similarity >= self.similarity_threshold
        if self.critical_field_exact_match and critical_diffs:
            match = False

        return ComparisonResult(
            case_id=case_id,
            match=match,
            similarity_score=similarity,
            differences=differences,
            critical_differences=critical_diffs,
        )

    def _compare_events(
        self,
        actual_events: List[Dict],
        expected_events: List[Dict],
    ) -> List[Dict[str, Any]]:
        """Compare event lists between trajectories."""
        differences = []

        if len(actual_events) != len(expected_events):
            differences.append({
                "field": "events_count",
                "actual": len(actual_events),
                "expected": len(expected_events),
            })

        # Compare event by event up to the shorter list
        for i, (a, e) in enumerate(zip(actual_events, expected_events)):
            if a.get("event_type") != e.get("event_type"):
                differences.append({
                    "field": f"events[{i}].event_type",
                    "actual": a.get("event_type"),
                    "expected": e.get("event_type"),
                })
            if a.get("tool_name") != e.get("tool_name"):
                differences.append({
                    "field": f"events[{i}].tool_name",
                    "actual": a.get("tool_name"),
                    "expected": e.get("tool_name"),
                })

        return differences

    def compare_safety_critical(
        self,
        actual: Dict[str, Any],
        expected: Dict[str, Any],
        case_id: str = "",
    ) -> ComparisonResult:
        """Compare only safety-critical aspects of trajectories."""
        critical_actual = {
            "success": actual.get("success"),
            "safety_violations": self._count_safety_violations(actual),
            "risk_signals": self._extract_risk_signals(actual),
        }
        critical_expected = {
            "success": expected.get("success"),
            "safety_violations": expected.get("safety_violations", 0),
            "risk_signals": expected.get("risk_signals", []),
        }
        return self.compare(critical_actual, critical_expected, case_id)

    def _count_safety_violations(self, trajectory: Dict[str, Any]) -> int:
        """Count safety violations in a trajectory."""
        count = 0
        for event in trajectory.get("events", []):
            if event.get("event_type") == "risk_signal" or event.get("risk_signal"):
                count += 1
        return count

    def _extract_risk_signals(self, trajectory: Dict[str, Any]) -> List[str]:
        """Extract risk signals from a trajectory."""
        signals = []
        for event in trajectory.get("events", []):
            if event.get("risk_signal"):
                signals.append(event["risk_signal"])
        return signals

    @staticmethod
    def trajectory_hash(trajectory: Dict[str, Any]) -> str:
        """Compute a hash of a trajectory for quick comparison."""
        serialized = json.dumps(trajectory, sort_keys=True, default=str)
        return hashlib.sha256(serialized.encode()).hexdigest()[:16]
