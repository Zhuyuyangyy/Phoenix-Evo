"""Repair candidate generator for Phoenix-Evo self-repair system."""

from __future__ import annotations

import hashlib
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

from .degradation_detector import DegradationSignal


@dataclass
class RepairCandidate:
    """A candidate repair for a detected degradation."""
    candidate_id: str
    target_metric: str
    strategy: str  # "rollback", "parameter_adjust", "retrain", "fallback", "restart"
    description: str
    estimated_impact: float  # 0.0 to 1.0
    risk_level: str  # "low", "medium", "high"
    rollback_possible: bool = True
    created_at: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "target_metric": self.target_metric,
            "strategy": self.strategy,
            "description": self.description,
            "estimated_impact": self.estimated_impact,
            "risk_level": self.risk_level,
            "rollback_possible": self.rollback_possible,
            "created_at": self.created_at,
            "metadata": self.metadata,
        }


class RepairCandidateGenerator:
    """Generates repair candidates for detected degradations.

    Analyzes degradation signals and proposes repair strategies
    with estimated impact and risk levels.
    """

    def __init__(self):
        self._strategies: Dict[str, Callable] = {
            "rollback": self._generate_rollback,
            "parameter_adjust": self._generate_parameter_adjust,
            "retrain": self._generate_retrain,
            "fallback": self._generate_fallback,
            "restart": self._generate_restart,
        }
        self._candidates: List[RepairCandidate] = []

    def generate(self, signal: DegradationSignal) -> List[RepairCandidate]:
        """Generate repair candidates for a degradation signal."""
        candidates = []

        # Always generate rollback candidate
        if signal.severity in ("high", "critical"):
            candidates.append(self._strategies["rollback"](signal))

        # Generate parameter adjustment for medium severity
        if signal.severity in ("medium", "high"):
            candidates.append(self._strategies["parameter_adjust"](signal))

        # Generate retrain for persistent degradation
        if signal.degradation_ratio < 0.5:
            candidates.append(self._strategies["retrain"](signal))

        # Generate fallback for critical
        if signal.severity == "critical":
            candidates.append(self._strategies["fallback"](signal))
            candidates.append(self._strategies["restart"](signal))

        # Low severity gets parameter adjustment
        if signal.severity == "low":
            candidates.append(self._strategies["parameter_adjust"](signal))

        self._candidates.extend(candidates)
        return candidates

    def _generate_rollback(self, signal: DegradationSignal) -> RepairCandidate:
        """Generate a rollback repair candidate."""
        return RepairCandidate(
            candidate_id=f"repair_{uuid.uuid4().hex[:8]}",
            target_metric=signal.metric_name,
            strategy="rollback",
            description=f"Rollback {signal.metric_name} to previous known-good configuration",
            estimated_impact=0.8,
            risk_level="low",
            rollback_possible=True,
            metadata={"degradation_ratio": signal.degradation_ratio},
        )

    def _generate_parameter_adjust(self, signal: DegradationSignal) -> RepairCandidate:
        """Generate a parameter adjustment repair candidate."""
        return RepairCandidate(
            candidate_id=f"repair_{uuid.uuid4().hex[:8]}",
            target_metric=signal.metric_name,
            strategy="parameter_adjust",
            description=f"Adjust parameters for {signal.metric_name} to compensate for degradation",
            estimated_impact=0.5,
            risk_level="low",
            rollback_possible=True,
            metadata={"degradation_ratio": signal.degradation_ratio},
        )

    def _generate_retrain(self, signal: DegradationSignal) -> RepairCandidate:
        """Generate a retrain repair candidate."""
        return RepairCandidate(
            candidate_id=f"repair_{uuid.uuid4().hex[:8]}",
            target_metric=signal.metric_name,
            strategy="retrain",
            description=f"Retrain model for {signal.metric_name} with recent data",
            estimated_impact=0.9,
            risk_level="medium",
            rollback_possible=True,
            metadata={"degradation_ratio": signal.degradation_ratio},
        )

    def _generate_fallback(self, signal: DegradationSignal) -> RepairCandidate:
        """Generate a fallback repair candidate."""
        return RepairCandidate(
            candidate_id=f"repair_{uuid.uuid4().hex[:8]}",
            target_metric=signal.metric_name,
            strategy="fallback",
            description=f"Switch {signal.metric_name} to fallback/safe mode",
            estimated_impact=0.6,
            risk_level="low",
            rollback_possible=True,
            metadata={"degradation_ratio": signal.degradation_ratio},
        )

    def _generate_restart(self, signal: DegradationSignal) -> RepairCandidate:
        """Generate a restart repair candidate."""
        return RepairCandidate(
            candidate_id=f"repair_{uuid.uuid4().hex[:8]}",
            target_metric=signal.metric_name,
            strategy="restart",
            description=f"Restart the {signal.metric_name} component",
            estimated_impact=0.7,
            risk_level="medium",
            rollback_possible=False,
            metadata={"degradation_ratio": signal.degradation_ratio},
        )

    def get_candidates(
        self,
        strategy: Optional[str] = None,
        risk_level: Optional[str] = None,
    ) -> List[RepairCandidate]:
        """Get repair candidates, optionally filtered."""
        candidates = self._candidates
        if strategy:
            candidates = [c for c in candidates if c.strategy == strategy]
        if risk_level:
            candidates = [c for c in candidates if c.risk_level == risk_level]
        return candidates

    def rank_candidates(self, candidates: List[RepairCandidate]) -> List[RepairCandidate]:
        """Rank repair candidates by estimated impact (descending) and risk (ascending)."""
        risk_order = {"low": 0, "medium": 1, "high": 2}
        return sorted(
            candidates,
            key=lambda c: (-c.estimated_impact, risk_order.get(c.risk_level, 1)),
        )
