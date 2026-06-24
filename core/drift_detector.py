"""
drift_detector: Skill drift detection module
V0.3 -- Phoenix-Evo Curator

Responsibilities:
  - Detect skill behavior deviation from original specification
    (success rate drift / risk drift / content drift)
  - Track skill revision history and compute drift magnitude
  - Output risk levels: stable / warning / drift / critical

V1.1: Upgraded from fixed thresholds to adaptive thresholds computed from
      the population distribution (mean +/- k * std).  Fixed values are
      retained as fallback defaults when the sample is too small.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

# ----------------------------------------------------------------------
# Data structures
# ----------------------------------------------------------------------

@dataclass
class DriftRecord:
    """Single drift record."""
    skill_id: str = ""
    drift_type: str = ""        # "success_rate" | "risk_level" | "content" | "usage"
    drift_direction: str = ""   # "up" | "down" | "changed"
    drift_score: float = 0.0    # 0.0 ~ 1.0, higher means more severe drift
    previous_value: Any = None
    current_value: Any = None
    severity: str = ""          # "stable" | "warning" | "drift" | "critical"
    detected_at: str = ""
    reason: str = ""


@dataclass
class SkillHealthReport:
    """Skill health report."""
    skill_id: str
    skill_name: str
    overall_severity: str        # "stable" | "warning" | "drift" | "critical"
    drift_records: list[DriftRecord] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)
    analyzed_at: str = ""


# ----------------------------------------------------------------------
# Default thresholds (used when adaptive computation is not possible)
# ----------------------------------------------------------------------
_DEFAULT_STALENESS_DAYS = 30
_DEFAULT_SUCCESS_RATE_WARNING = 0.70
_DEFAULT_SUCCESS_RATE_CRITICAL = 0.50
_DEFAULT_USAGE_COUNT_CRITICAL = 10
_RISK_LEVEL_INCREASE_WEIGHT = 0.3
_MIN_USAGE_FOR_DRIFT = 3

# Minimum sample size before adaptive thresholds kick in.
# Below this we fall back to the fixed defaults.
_MIN_SAMPLE_FOR_ADAPTIVE = 5

# Backward-compatible aliases (used by existing tests and external code)
STALENESS_DAYS = _DEFAULT_STALENESS_DAYS
SUCCESS_RATE_WARNING = _DEFAULT_SUCCESS_RATE_WARNING
SUCCESS_RATE_CRITICAL = _DEFAULT_SUCCESS_RATE_CRITICAL
USAGE_COUNT_CRITICAL = _DEFAULT_USAGE_COUNT_CRITICAL
MIN_USAGE_FOR_DRIFT = _MIN_USAGE_FOR_DRIFT


# ----------------------------------------------------------------------
# Adaptive threshold computation
# ----------------------------------------------------------------------

@dataclass
class AdaptiveThresholds:
    """Container for adaptively computed thresholds."""
    success_rate_warning: float = _DEFAULT_SUCCESS_RATE_WARNING
    success_rate_critical: float = _DEFAULT_SUCCESS_RATE_CRITICAL
    staleness_days_warning: int = _DEFAULT_STALENESS_DAYS
    staleness_days_critical: int = _DEFAULT_STALENESS_DAYS * 2
    min_usage_for_drift: int = _MIN_USAGE_FOR_DRIFT

    # Metadata about how thresholds were derived
    sample_size: int = 0
    success_rate_mean: float = 0.0
    success_rate_std: float = 0.0
    staleness_mean: float = 0.0
    staleness_std: float = 0.0


def _compute_stats(values: list[float]) -> tuple[float, float]:
    """Return (mean, std) of a list of floats.  Returns (0.0, 0.0) for empty input."""
    if not values:
        return 0.0, 0.0
    n = len(values)
    mean = sum(values) / n
    if n < 2:
        return mean, 0.0
    variance = sum((v - mean) ** 2 for v in values) / (n - 1)
    return mean, math.sqrt(variance)


def compute_adaptive_thresholds(skill_index: dict[str, Any]) -> AdaptiveThresholds:
    """
    Compute adaptive thresholds from the population of active skills.

    Strategy:
      success_rate_warning  = mean - 1.0 * std   (clamped >= 0.30)
      success_rate_critical = mean - 2.0 * std   (clamped >= 0.10)
      staleness_days_warning  = mean + 1.5 * std (clamped >= 14)
      staleness_days_critical = mean + 2.5 * std (clamped >= 30)

    Falls back to fixed defaults when sample size < _MIN_SAMPLE_FOR_ADAPTIVE.
    """
    thresholds = AdaptiveThresholds()

    # Collect population statistics from active/draft skills
    success_rates: list[float] = []
    days_since_used: list[float] = []

    for _skill_id, entry in skill_index.items():
        status = entry.get("status", "")
        if status not in ("active", "draft"):
            continue

        usage_count = entry.get("usage_count", 0)
        sr = entry.get("success_rate")
        if sr is not None and usage_count >= _MIN_USAGE_FOR_DRIFT:
            success_rates.append(float(sr))

        # Staleness in days
        last_used = entry.get("last_used")
        if last_used:
            try:
                last_dt = datetime.fromisoformat(last_used)
                days = (datetime.now() - last_dt).days
                days_since_used.append(float(days))
            except (ValueError, TypeError):
                pass
        else:
            created_at = entry.get("created_at", "")
            if created_at:
                try:
                    created = datetime.fromisoformat(created_at)
                    days_since_used.append(float((datetime.now() - created).days))
                except (ValueError, TypeError):
                    pass

    # --- Success rate thresholds ---
    sr_mean, sr_std = _compute_stats(success_rates)
    thresholds.success_rate_mean = round(sr_mean, 4)
    thresholds.success_rate_std = round(sr_std, 4)

    if len(success_rates) >= _MIN_SAMPLE_FOR_ADAPTIVE and sr_std > 0:
        # Adaptive: warn at mean - 1*std, critical at mean - 2*std
        thresholds.success_rate_warning = max(round(sr_mean - 1.0 * sr_std, 4), 0.30)
        thresholds.success_rate_critical = max(round(sr_mean - 2.0 * sr_std, 4), 0.10)
        # Ensure critical < warning
        if thresholds.success_rate_critical >= thresholds.success_rate_warning:
            thresholds.success_rate_critical = thresholds.success_rate_warning - 0.10
    # else: keep defaults

    # --- Staleness thresholds ---
    st_mean, st_std = _compute_stats(days_since_used)
    thresholds.staleness_mean = round(st_mean, 1)
    thresholds.staleness_std = round(st_std, 1)

    if len(days_since_used) >= _MIN_SAMPLE_FOR_ADAPTIVE and st_std > 0:
        thresholds.staleness_days_warning = max(int(st_mean + 1.5 * st_std), 14)
        thresholds.staleness_days_critical = max(int(st_mean + 2.5 * st_std), 30)
    # else: keep defaults

    thresholds.sample_size = len(success_rates)
    return thresholds


# ----------------------------------------------------------------------
# DriftDetector
# ----------------------------------------------------------------------

class DriftDetector:
    """
    Detect drift across the skill corpus.

    Detection dimensions:
      1. Success rate drift: usage_count sufficient, success rate below threshold
      2. Risk level drift: skill risk level increased from initial value
      3. Staleness: skill unused for extended period
      4. Rapid failure: consecutive failures (all recent uses failed)

    V1.1: Thresholds are now adaptive -- computed from the population
    distribution (mean +/- k*std) when the sample is large enough,
    with fixed defaults as fallback.
    """

    def __init__(
        self,
        skill_index: dict[str, Any],
        thresholds: AdaptiveThresholds | None = None,
    ):
        """
        Args:
            skill_index: skill_registry.get_index() return value
            thresholds:  optional pre-computed AdaptiveThresholds; if None
                         they are computed automatically from skill_index.
        """
        self.index = skill_index
        self.records: list[DriftRecord] = []
        self.thresholds = thresholds or compute_adaptive_thresholds(skill_index)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def analyze_all(self) -> list[SkillHealthReport]:
        """
        Analyze health of all active / draft skills.

        Returns:
            list[SkillHealthReport] sorted by severity (critical first).
        """
        reports: list[SkillHealthReport] = []
        for skill_id, entry in self.index.items():
            status = entry.get("status", "")
            if status not in ("active", "draft"):
                continue
            report = self.analyze_skill(skill_id, entry)
            reports.append(report)
        # Sort by severity descending
        severity_order = {"critical": 0, "drift": 1, "warning": 2, "stable": 3}
        reports.sort(key=lambda r: severity_order.get(r.overall_severity, 3))
        return reports

    def analyze_skill(self, skill_id: str, entry: dict[str, Any]) -> SkillHealthReport:
        """Analyze a single skill's health."""
        skill_name = entry.get("skill_name", skill_id)
        records: list[DriftRecord] = []

        # 1. Success rate drift
        sr_record = self._check_success_rate(skill_id, entry)
        if sr_record:
            records.append(sr_record)

        # 2. Risk level drift
        risk_record = self._check_risk_drift(skill_id, entry)
        if risk_record:
            records.append(risk_record)

        # 3. Staleness
        stale_record = self._check_staleness(skill_id, entry)
        if stale_record:
            records.append(stale_record)

        # 4. Rapid consecutive failures
        fail_record = self._check_rapid_failure(skill_id, entry)
        if fail_record:
            records.append(fail_record)

        # Aggregate severity
        severity = self._overall_severity(records)
        recommendations = self._make_recommendations(records, severity, entry)

        return SkillHealthReport(
            skill_id=skill_id,
            skill_name=skill_name,
            overall_severity=severity,
            drift_records=records,
            recommendations=recommendations,
            analyzed_at=datetime.now().isoformat(),
        )

    # ------------------------------------------------------------------
    # Individual drift checks (adaptive)
    # ------------------------------------------------------------------

    def _check_success_rate(self, skill_id: str, entry: dict[str, Any]) -> DriftRecord | None:
        """
        Check if success rate has drifted below the adaptive threshold.

        Uses population-derived warning/critical thresholds when available,
        falling back to fixed defaults otherwise.
        """
        usage_count = entry.get("usage_count", 0)
        if usage_count < self.thresholds.min_usage_for_drift:
            return None

        success_rate = entry.get("success_rate")
        if success_rate is None:
            return None

        severity = "stable"
        reason = ""
        if success_rate < self.thresholds.success_rate_critical:
            severity = "critical"
            reason = (
                f"Success rate {success_rate:.1%} below critical threshold "
                f"{self.thresholds.success_rate_critical:.1%} "
                f"(pop mean={self.thresholds.success_rate_mean:.1%}, "
                f"std={self.thresholds.success_rate_std:.1%})"
            )
        elif success_rate < self.thresholds.success_rate_warning:
            severity = "warning"
            reason = (
                f"Success rate {success_rate:.1%} below warning threshold "
                f"{self.thresholds.success_rate_warning:.1%} "
                f"(pop mean={self.thresholds.success_rate_mean:.1%}, "
                f"std={self.thresholds.success_rate_std:.1%})"
            )

        if severity != "stable":
            return DriftRecord(
                skill_id=skill_id,
                drift_type="success_rate",
                drift_direction="down",
                drift_score=round(1 - success_rate, 4),
                previous_value=None,
                current_value=success_rate,
                severity=severity,
                detected_at=datetime.now().isoformat(),
                reason=reason,
            )
        return None

    def _check_risk_drift(self, skill_id: str, entry: dict[str, Any]) -> DriftRecord | None:
        """Check if risk level has increased from initial value."""
        current_risk = entry.get("risk_level", "low")
        risk_order = {"none": 0, "low": 1, "medium": 2, "high": 3, "critical": 4}
        current_score = risk_order.get(current_risk, 0)
        initial_risk = entry.get("initial_risk_level", current_risk)
        initial_score = risk_order.get(initial_risk, 0)
        if current_score > initial_score:
            drift_score = (current_score - initial_score) / 4.0
            severity = "drift" if drift_score < 0.75 else "critical"
            return DriftRecord(
                skill_id=skill_id,
                drift_type="risk_level",
                drift_direction="up",
                drift_score=round(drift_score, 4),
                previous_value=initial_risk,
                current_value=current_risk,
                severity=severity,
                detected_at=datetime.now().isoformat(),
                reason=f"Risk level increased from {initial_risk} to {current_risk}",
            )
        return None

    def _check_staleness(self, skill_id: str, entry: dict[str, Any]) -> DriftRecord | None:
        """
        Check if skill has been unused for too long.

        Uses adaptive staleness thresholds derived from the population.
        """
        staleness_warn = self.thresholds.staleness_days_warning
        staleness_crit = self.thresholds.staleness_days_critical

        last_used = entry.get("last_used")
        if not last_used:
            usage_count = entry.get("usage_count", 0)
            if usage_count == 0:
                created_at = entry.get("created_at", "")
                if created_at:
                    try:
                        created = datetime.fromisoformat(created_at)
                        days_since = (datetime.now() - created).days
                        if days_since > staleness_warn:
                            return DriftRecord(
                                skill_id=skill_id,
                                drift_type="usage",
                                drift_direction="down",
                                drift_score=min(days_since / (staleness_crit * 2), 1.0),
                                previous_value=None,
                                current_value=f"Never used (created {days_since} days ago)",
                                severity="warning",
                                detected_at=datetime.now().isoformat(),
                                reason=(
                                    f"Skill created {days_since} days ago but never used "
                                    f"(threshold={staleness_warn}d, "
                                    f"pop mean={self.thresholds.staleness_mean:.0f}d)"
                                ),
                            )
                    except ValueError:
                        pass
            return None

        try:
            last_dt = datetime.fromisoformat(last_used)
            days_ago = (datetime.now() - last_dt).days
            if days_ago > staleness_crit:
                severity = "drift"
                return DriftRecord(
                    skill_id=skill_id,
                    drift_type="usage",
                    drift_direction="down",
                    drift_score=min(days_ago / (staleness_crit * 2), 1.0),
                    previous_value=last_used,
                    current_value=f"Unused for {days_ago} days",
                    severity=severity,
                    detected_at=datetime.now().isoformat(),
                    reason=(
                        f"Skill unused for {days_ago} days "
                        f"(critical threshold={staleness_crit}d, "
                        f"pop mean={self.thresholds.staleness_mean:.0f}d)"
                    ),
                )
            if days_ago > staleness_warn:
                return DriftRecord(
                    skill_id=skill_id,
                    drift_type="usage",
                    drift_direction="down",
                    drift_score=min(days_ago / (staleness_crit * 2), 1.0),
                    previous_value=last_used,
                    current_value=f"Unused for {days_ago} days",
                    severity="warning",
                    detected_at=datetime.now().isoformat(),
                    reason=(
                        f"Skill unused for {days_ago} days "
                        f"(warning threshold={staleness_warn}d, "
                        f"pop mean={self.thresholds.staleness_mean:.0f}d)"
                    ),
                )
        except ValueError:
            pass
        return None

    def _check_rapid_failure(self, skill_id: str, entry: dict[str, Any]) -> DriftRecord | None:
        """
        Check for rapid consecutive failure pattern.
        Logic: if ALL recent uses failed (usage >= 3, success == 0).
        """
        usage_count = entry.get("usage_count", 0)
        success_count = entry.get("success_count", 0)
        if usage_count < 3:
            return None
        if usage_count >= 3 and success_count == 0:
            return DriftRecord(
                skill_id=skill_id,
                drift_type="success_rate",
                drift_direction="down",
                drift_score=1.0,
                previous_value=None,
                current_value=0.0,
                severity="critical",
                detected_at=datetime.now().isoformat(),
                reason=f"All {usage_count} recent uses failed (0% success rate)",
            )
        return None

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _overall_severity(self, records: list[DriftRecord]) -> str:
        """Return the most severe level among all records."""
        if any(r.severity == "critical" for r in records):
            return "critical"
        if any(r.severity == "drift" for r in records):
            return "drift"
        if any(r.severity == "warning" for r in records):
            return "warning"
        return "stable"

    def _make_recommendations(
        self,
        records: list[DriftRecord],
        severity: str,
        entry: dict[str, Any],
    ) -> list[str]:
        """Generate recommendations based on drift records."""
        recs: list[str] = []
        for r in records:
            if r.drift_type == "success_rate" and r.drift_direction == "down":
                if severity == "critical":
                    recs.append("Recommend immediate archival (success rate critically below safety threshold)")
                else:
                    recs.append("Recommend manual review of success rate; downgrade or archive if needed")
            elif r.drift_type == "risk_level" and r.drift_direction == "up":
                recs.append("Recommend manual review of risk level change; update risk policy")
            elif r.drift_type == "usage":
                if severity == "drift":
                    recs.append("Recommend archival (long-unused stale skill)")
                else:
                    recs.append("Recommend marking as stale; increase monitoring frequency")
            elif r.drift_type == "success_rate" and entry.get("success_count", 1) == 0:
                recs.append("Recommend immediate archival (consecutive failures, likely broken)")
        return recs
