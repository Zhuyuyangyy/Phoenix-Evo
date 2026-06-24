"""Auto-governance engine for Phoenix-Evo self-repair system."""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

from .degradation_detector import DegradationDetector, DegradationSignal
from .repair_candidate_generator import RepairCandidate, RepairCandidateGenerator


class GovernanceAction(Enum):
    MONITOR = "monitor"
    ALERT = "alert"
    AUTO_REPAIR = "auto_repair"
    ROLLBACK = "rollback"
    SHUTDOWN = "shutdown"


@dataclass
class GovernanceDecision:
    """A governance decision made by the auto-governance engine."""
    decision_id: str
    action: GovernanceAction
    target_metric: str
    reason: str
    repair_candidate: Optional[RepairCandidate] = None
    confidence: float = 0.0
    auto_approved: bool = False
    timestamp: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class GovernancePolicy:
    """Policy for auto-governance decisions."""
    max_auto_repair_severity: str = "medium"  # Max severity for auto-repair
    require_approval_for: List[str] = field(default_factory=lambda: ["rollback", "shutdown"])
    cooldown_seconds: float = 300.0  # Minimum time between auto-repairs
    max_auto_repairs_per_hour: int = 3
    enable_auto_repair: bool = True


class AutoGovernanceEngine:
    """Automated governance engine for self-repair decisions.

    Makes decisions about when and how to repair degradations,
    with configurable policies for auto-approval vs. human review.
    """

    SEVERITY_ORDER = {"low": 0, "medium": 1, "high": 2, "critical": 3}

    def __init__(
        self,
        detector: Optional[DegradationDetector] = None,
        generator: Optional[RepairCandidateGenerator] = None,
        policy: Optional[GovernancePolicy] = None,
    ):
        self.detector = detector or DegradationDetector()
        self.generator = generator or RepairCandidateGenerator()
        self.policy = policy or GovernancePolicy()
        self._decisions: List[GovernanceDecision] = []
        self._last_repair_time: float = 0.0
        self._repairs_this_hour: int = 0
        self._hour_start: float = time.time()

    def evaluate(self, signal: DegradationSignal) -> GovernanceDecision:
        """Evaluate a degradation signal and make a governance decision."""
        decision_id = f"gov_{uuid.uuid4().hex[:8]}"

        # Determine action based on severity
        action = self._determine_action(signal)

        # Generate repair candidates if needed
        repair = None
        if action in (GovernanceAction.AUTO_REPAIR, GovernanceAction.ROLLBACK):
            candidates = self.generator.generate(signal)
            if candidates:
                ranked = self.generator.rank_candidates(candidates)
                repair = ranked[0]

        # Check if auto-approval is allowed
        auto_approved = self._can_auto_approve(action, signal)

        decision = GovernanceDecision(
            decision_id=decision_id,
            action=action,
            target_metric=signal.metric_name,
            reason=f"Degradation detected: {signal.severity} severity, ratio={signal.degradation_ratio:.2f}",
            repair_candidate=repair,
            confidence=self._compute_confidence(signal),
            auto_approved=auto_approved,
            metadata={
                "severity": signal.severity,
                "degradation_ratio": signal.degradation_ratio,
            },
        )

        self._decisions.append(decision)
        return decision

    def _determine_action(self, signal: DegradationSignal) -> GovernanceAction:
        """Determine the governance action based on signal severity."""
        if signal.severity == "critical":
            return GovernanceAction.ROLLBACK
        elif signal.severity == "high":
            return GovernanceAction.AUTO_REPAIR
        elif signal.severity == "medium":
            return GovernanceAction.ALERT
        else:
            return GovernanceAction.MONITOR

    def _can_auto_approve(self, action: GovernanceAction, signal: DegradationSignal) -> bool:
        """Check if an action can be auto-approved."""
        if not self.policy.enable_auto_repair:
            return False

        # Check if action requires manual approval
        if action.value in self.policy.require_approval_for:
            return False

        # Check severity limit
        max_sev = self.SEVERITY_ORDER.get(self.policy.max_auto_repair_severity, 0)
        signal_sev = self.SEVERITY_ORDER.get(signal.severity, 0)
        if signal_sev > max_sev:
            return False

        # Check cooldown
        now = time.time()
        if now - self._last_repair_time < self.policy.cooldown_seconds:
            return False

        # Check rate limit
        if now - self._hour_start > 3600:
            self._repairs_this_hour = 0
            self._hour_start = now
        if self._repairs_this_hour >= self.policy.max_auto_repairs_per_hour:
            return False

        return True

    def _compute_confidence(self, signal: DegradationSignal) -> float:
        """Compute confidence in the governance decision."""
        # Higher severity = higher confidence in action needed
        severity_confidence = {
            "low": 0.3,
            "medium": 0.6,
            "high": 0.8,
            "critical": 0.95,
        }
        return severity_confidence.get(signal.severity, 0.5)

    def get_decisions(self, action: Optional[GovernanceAction] = None) -> List[GovernanceDecision]:
        """Get governance decisions, optionally filtered by action."""
        if action:
            return [d for d in self._decisions if d.action == action]
        return list(self._decisions)

    def get_pending_approvals(self) -> List[GovernanceDecision]:
        """Get decisions that require manual approval."""
        return [d for d in self._decisions if not d.auto_approved]

    def approve(self, decision_id: str) -> bool:
        """Manually approve a governance decision."""
        for d in self._decisions:
            if d.decision_id == decision_id:
                d.auto_approved = True
                self._last_repair_time = time.time()
                self._repairs_this_hour += 1
                return True
        return False
