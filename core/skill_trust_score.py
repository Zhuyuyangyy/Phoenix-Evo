"""Skill trust score system for Phoenix-Evo.

Implements T(S) = T_ev × T_re × T_rt × T_im
where:
  T_ev = evidence trust
  T_re = reliability trust
  T_rt = recency trust
  T_im = impact trust
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class TrustDimension(Enum):
    EVIDENCE = "evidence"       # T_ev
    RELIABILITY = "reliability"  # T_re
    RECENCY = "recency"         # T_rt
    IMPACT = "impact"           # T_im


@dataclass
class SkillTrustScore:
    """Trust score for a skill, computed as T(S) = T_ev × T_re × T_rt × T_im."""
    skill_id: str
    t_evidence: float = 1.0     # T_ev: based on evidence/usage count
    t_reliability: float = 1.0  # T_re: based on success rate
    t_recency: float = 1.0     # T_rt: based on time since last use
    t_impact: float = 1.0      # T_im: based on impact of failures
    last_updated: float = field(default_factory=time.time)
    history: list[dict[str, Any]] = field(default_factory=list)

    @property
    def total_trust(self) -> float:
        """Compute the composite trust score T(S) = T_ev × T_re × T_rt × T_im."""
        return self.t_evidence * self.t_reliability * self.t_recency * self.t_impact

    def to_dict(self) -> dict[str, Any]:
        return {
            "skill_id": self.skill_id,
            "t_evidence": self.t_evidence,
            "t_reliability": self.t_reliability,
            "t_recency": self.t_recency,
            "t_impact": self.t_impact,
            "total_trust": self.total_trust,
            "last_updated": self.last_updated,
        }

    def update_dimension(self, dimension: TrustDimension, value: float) -> None:
        """Update a single trust dimension."""
        value = max(0.0, min(1.0, value))
        if dimension == TrustDimension.EVIDENCE:
            self.t_evidence = value
        elif dimension == TrustDimension.RELIABILITY:
            self.t_reliability = value
        elif dimension == TrustDimension.RECENCY:
            self.t_recency = value
        elif dimension == TrustDimension.IMPACT:
            self.t_impact = value
        self.last_updated = time.time()
        self.history.append({
            "dimension": dimension.value,
            "value": value,
            "timestamp": self.last_updated,
        })


@dataclass
class TrustThreshold:
    """Thresholds for trust-based decisions."""
    min_trust: float = 0.5
    warn_trust: float = 0.7
    auto_approve: float = 0.9
    auto_revoke: float = 0.2

    def classify(self, trust_score: float) -> str:
        """Classify a trust score into a decision category."""
        if trust_score >= self.auto_approve:
            return "auto_approve"
        if trust_score >= self.warn_trust:
            return "approved_with_warning"
        if trust_score >= self.min_trust:
            return "requires_review"
        if trust_score >= self.auto_revoke:
            return "requires_manual_review"
        return "auto_revoke"


class TrustScoreOptimizer:
    """Optimizes trust score parameters based on calibration data."""

    def __init__(self):
        self._calibration_data: list[dict[str, Any]] = []

    def add_observation(
        self,
        trust_score: SkillTrustScore,
        actual_outcome: bool,  # True = success, False = failure
    ) -> None:
        """Add a calibration observation."""
        self._calibration_data.append({
            "total_trust": trust_score.total_trust,
            "t_evidence": trust_score.t_evidence,
            "t_reliability": trust_score.t_reliability,
            "t_recency": trust_score.t_recency,
            "t_impact": trust_score.t_impact,
            "actual_outcome": actual_outcome,
        })

    def optimize_weights(self) -> dict[str, float]:
        """Optimize dimension weights based on calibration data."""
        if len(self._calibration_data) < 10:
            return {
                "evidence": 0.25,
                "reliability": 0.25,
                "recency": 0.25,
                "impact": 0.25,
            }

        # Simple optimization: weight by correlation with outcomes
        outcomes = [d["actual_outcome"] for d in self._calibration_data]
        dimensions = {
            "evidence": [d["t_evidence"] for d in self._calibration_data],
            "reliability": [d["t_reliability"] for d in self._calibration_data],
            "recency": [d["t_recency"] for d in self._calibration_data],
            "impact": [d["t_impact"] for d in self._calibration_data],
        }

        weights = {}
        for dim_name, dim_values in dimensions.items():
            # Compute point-biserial correlation
            n = len(outcomes)
            if n < 2:
                weights[dim_name] = 0.25
                continue
            mean_success = sum(v for v, o in zip(dim_values, outcomes, strict=False) if o) / max(sum(outcomes), 1)
            mean_failure = sum(v for v, o in zip(dim_values, outcomes, strict=False) if not o) / max(n - sum(outcomes), 1)
            weights[dim_name] = abs(mean_success - mean_failure) + 0.1  # Add smoothing

        # Normalize
        total = sum(weights.values())
        if total > 0:
            weights = {k: v / total for k, v in weights.items()}

        return weights


class TrustScoreCalibrator:
    """Calibrates trust scores to match observed reality."""

    def __init__(self, half_life_seconds: float = 86400.0):
        self.half_life_seconds = half_life_seconds
        self._observations: dict[str, list[dict[str, Any]]] = {}

    def record_outcome(
        self,
        skill_id: str,
        success: bool,
        timestamp: float | None = None,
    ) -> None:
        """Record a skill execution outcome."""
        if skill_id not in self._observations:
            self._observations[skill_id] = []
        self._observations[skill_id].append({
            "success": success,
            "timestamp": timestamp or time.time(),
        })

    def calibrate(self, skill_id: str) -> SkillTrustScore:
        """Calibrate trust score for a skill based on observations."""
        observations = self._observations.get(skill_id, [])
        now = time.time()

        if not observations:
            return SkillTrustScore(skill_id=skill_id)

        # T_ev: Evidence trust (based on number of observations)
        n_obs = len(observations)
        t_evidence = min(1.0, n_obs / 100.0)  # Saturates at 100 observations

        # T_re: Reliability trust (success rate)
        successes = sum(1 for o in observations if o["success"])
        t_reliability = successes / n_obs if n_obs > 0 else 0.5

        # T_rt: Recency trust (exponential decay)
        latest = max(o["timestamp"] for o in observations)
        age = now - latest
        t_recency = math.exp(-0.693 * age / self.half_life_seconds)  # half-life decay

        # T_im: Impact trust (based on recent failure severity)
        recent_failures = [
            o for o in observations
            if not o["success"] and (now - o["timestamp"]) < self.half_life_seconds
        ]
        t_impact = max(0.0, 1.0 - len(recent_failures) * 0.1)

        return SkillTrustScore(
            skill_id=skill_id,
            t_evidence=t_evidence,
            t_reliability=t_reliability,
            t_recency=t_recency,
            t_impact=t_impact,
        )

    def get_all_scores(self) -> dict[str, SkillTrustScore]:
        """Get calibrated scores for all observed skills."""
        return {skill_id: self.calibrate(skill_id) for skill_id in self._observations}
