"""
Tests for DriftDetector module -- covers both legacy constant-based
behavior and the new V1.1 adaptive threshold mechanism.
"""

from datetime import datetime, timedelta

from core.drift_detector import (
    MIN_USAGE_FOR_DRIFT,
    # Backward-compatible constant aliases
    STALENESS_DAYS,
    SUCCESS_RATE_CRITICAL,
    SUCCESS_RATE_WARNING,
    USAGE_COUNT_CRITICAL,
    AdaptiveThresholds,
    DriftDetector,
    DriftRecord,
    SkillHealthReport,
    compute_adaptive_thresholds,
)

# ---------------------------------------------------------------------------
# Backward-compatible constants
# ---------------------------------------------------------------------------

class TestLegacyConstants:
    """Verify that the legacy module-level constants are still exported."""

    def test_staleness_days(self):
        assert isinstance(STALENESS_DAYS, int)
        assert STALENESS_DAYS > 0

    def test_success_rate_warning(self):
        assert isinstance(SUCCESS_RATE_WARNING, float)
        assert 0 < SUCCESS_RATE_WARNING < 1

    def test_success_rate_critical(self):
        assert isinstance(SUCCESS_RATE_CRITICAL, float)
        assert 0 < SUCCESS_RATE_CRITICAL < 1

    def test_usage_count_critical(self):
        assert isinstance(USAGE_COUNT_CRITICAL, int)
        assert USAGE_COUNT_CRITICAL > 0

    def test_min_usage_for_drift(self):
        assert isinstance(MIN_USAGE_FOR_DRIFT, int)
        assert MIN_USAGE_FOR_DRIFT > 0


# ---------------------------------------------------------------------------
# Adaptive threshold computation
# ---------------------------------------------------------------------------

class TestAdaptiveThresholds:
    """Test the adaptive threshold computation from population data."""

    def test_empty_index_returns_defaults(self):
        """Empty index should return default thresholds."""
        th = compute_adaptive_thresholds({})
        assert th.success_rate_warning == SUCCESS_RATE_WARNING
        assert th.success_rate_critical == SUCCESS_RATE_CRITICAL
        assert th.staleness_days_warning == STALENESS_DAYS
        assert th.sample_size == 0

    def test_small_sample_returns_defaults(self):
        """With fewer than 5 samples, defaults are kept."""
        index = {}
        for i in range(3):
            index[f"skill_{i}"] = {
                "skill_id": f"skill_{i}",
                "status": "active",
                "usage_count": 10,
                "success_rate": 0.8,
                "last_used": datetime.now().isoformat(),
            }
        th = compute_adaptive_thresholds(index)
        assert th.success_rate_warning == SUCCESS_RATE_WARNING
        assert th.sample_size == 3

    def test_large_sample_adapts(self):
        """With 5+ samples, thresholds should adapt to population."""
        index = {}
        # All skills with high success rate (mean ~0.90)
        for i in range(10):
            index[f"skill_{i}"] = {
                "skill_id": f"skill_{i}",
                "status": "active",
                "usage_count": 20,
                "success_rate": 0.85 + (i % 3) * 0.05,
                "last_used": (datetime.now() - timedelta(days=i * 3)).isoformat(),
            }
        th = compute_adaptive_thresholds(index)
        assert th.sample_size == 10
        # With mean ~0.90, warning threshold should be higher than the default 0.70
        assert th.success_rate_warning > 0.70

    def test_adaptive_critical_below_warning(self):
        """Critical threshold must always be below warning."""
        index = {}
        for i in range(8):
            index[f"skill_{i}"] = {
                "skill_id": f"skill_{i}",
                "status": "active",
                "usage_count": 15,
                "success_rate": 0.75,
                "last_used": datetime.now().isoformat(),
            }
        th = compute_adaptive_thresholds(index)
        assert th.success_rate_critical < th.success_rate_warning

    def test_staleness_adapts_to_population(self):
        """Staleness thresholds should adapt to usage patterns."""
        index = {}
        # Skills used very recently (mean days ~5, low std)
        for i in range(10):
            index[f"skill_{i}"] = {
                "skill_id": f"skill_{i}",
                "status": "active",
                "usage_count": 10,
                "success_rate": 0.8,
                "last_used": (datetime.now() - timedelta(days=i)).isoformat(),
            }
        th = compute_adaptive_thresholds(index)
        assert th.staleness_days_warning >= 14  # minimum floor

    def test_skips_archived_skills(self):
        """Archived skills should not be included in population stats."""
        index = {
            "active_1": {
                "skill_id": "active_1", "status": "active",
                "usage_count": 10, "success_rate": 0.9,
                "last_used": datetime.now().isoformat(),
            },
            "archived_1": {
                "skill_id": "archived_1", "status": "archived",
                "usage_count": 50, "success_rate": 0.2,
                "last_used": (datetime.now() - timedelta(days=200)).isoformat(),
            },
        }
        th = compute_adaptive_thresholds(index)
        assert th.sample_size == 1  # only the active skill


# ---------------------------------------------------------------------------
# DriftDetector core tests (legacy-compatible + adaptive)
# ---------------------------------------------------------------------------

class TestDriftDetector:
    """Test suite for DriftDetector."""

    def _make_index(self, **kwargs):
        """Helper to create a test skill index."""
        index = {
            "skill_001": {
                "skill_id": "skill_001",
                "skill_name": "test_skill",
                "status": "active",
                "usage_count": 10,
                "success_count": 8,
                "success_rate": 0.8,
                "last_used": datetime.now().isoformat(),
                "created_at": (datetime.now() - timedelta(days=10)).isoformat(),
                "risk_level": "low",
            },
        }
        index.update(kwargs)
        return index

    def test_analyze_all_returns_reports(self):
        """Test that analyze_all returns health reports."""
        index = self._make_index()
        detector = DriftDetector(index)
        reports = detector.analyze_all()
        assert len(reports) > 0
        assert isinstance(reports[0], SkillHealthReport)

    def test_analyze_all_skips_archived(self):
        """Test that analyze_all skips archived skills."""
        index = self._make_index()
        index["skill_001"]["status"] = "archived"
        detector = DriftDetector(index)
        reports = detector.analyze_all()
        assert len(reports) == 0

    def test_analyze_skill_stable(self):
        """Test analysis of a stable skill."""
        index = self._make_index()
        detector = DriftDetector(index)
        report = detector.analyze_skill("skill_001", index["skill_001"])
        assert report.overall_severity == "stable"

    def test_check_success_rate_below_critical(self):
        """Test success rate detection below critical threshold."""
        index = self._make_index()
        index["skill_001"]["success_rate"] = 0.3
        index["skill_001"]["usage_count"] = 10
        detector = DriftDetector(index)
        record = detector._check_success_rate("skill_001", index["skill_001"])
        assert record is not None
        assert record.severity == "critical"

    def test_check_success_rate_below_warning(self):
        """Test success rate detection below warning threshold."""
        index = self._make_index()
        index["skill_001"]["success_rate"] = 0.6
        index["skill_001"]["usage_count"] = 10
        detector = DriftDetector(index)
        record = detector._check_success_rate("skill_001", index["skill_001"])
        assert record is not None
        assert record.severity == "warning"

    def test_check_success_rate_above_thresholds(self):
        """Test success rate detection above thresholds."""
        index = self._make_index()
        index["skill_001"]["success_rate"] = 0.9
        index["skill_001"]["usage_count"] = 10
        detector = DriftDetector(index)
        record = detector._check_success_rate("skill_001", index["skill_001"])
        assert record is None

    def test_check_success_rate_insufficient_usage(self):
        """Test that insufficient usage skips check."""
        index = self._make_index()
        index["skill_001"]["success_rate"] = 0.3
        index["skill_001"]["usage_count"] = 1
        detector = DriftDetector(index)
        record = detector._check_success_rate("skill_001", index["skill_001"])
        assert record is None

    def test_check_risk_drift_increased(self):
        """Test risk level drift detection."""
        index = self._make_index()
        index["skill_001"]["risk_level"] = "high"
        index["skill_001"]["initial_risk_level"] = "low"
        detector = DriftDetector(index)
        record = detector._check_risk_drift("skill_001", index["skill_001"])
        assert record is not None
        assert record.drift_direction == "up"

    def test_check_risk_drift_no_change(self):
        """Test risk level drift detection with no change."""
        index = self._make_index()
        index["skill_001"]["risk_level"] = "low"
        index["skill_001"]["initial_risk_level"] = "low"
        detector = DriftDetector(index)
        record = detector._check_risk_drift("skill_001", index["skill_001"])
        assert record is None

    def test_check_staleness_old_skill(self):
        """Test staleness detection for old unused skill."""
        index = self._make_index()
        index["skill_001"]["last_used"] = (datetime.now() - timedelta(days=60)).isoformat()
        detector = DriftDetector(index)
        record = detector._check_staleness("skill_001", index["skill_001"])
        assert record is not None
        assert record.drift_type == "usage"

    def test_check_staleness_recent_skill(self):
        """Test staleness detection for recently used skill."""
        index = self._make_index()
        index["skill_001"]["last_used"] = datetime.now().isoformat()
        detector = DriftDetector(index)
        record = detector._check_staleness("skill_001", index["skill_001"])
        assert record is None

    def test_check_staleness_never_used(self):
        """Test staleness detection for never-used skill."""
        index = self._make_index()
        index["skill_001"]["last_used"] = None
        index["skill_001"]["usage_count"] = 0
        index["skill_001"]["created_at"] = (datetime.now() - timedelta(days=60)).isoformat()
        detector = DriftDetector(index)
        record = detector._check_staleness("skill_001", index["skill_001"])
        assert record is not None

    def test_check_rapid_failure_all_failed(self):
        """Test rapid failure detection when all uses failed."""
        index = self._make_index()
        index["skill_001"]["usage_count"] = 5
        index["skill_001"]["success_count"] = 0
        detector = DriftDetector(index)
        record = detector._check_rapid_failure("skill_001", index["skill_001"])
        assert record is not None
        assert record.severity == "critical"

    def test_check_rapid_failure_some_succeeded(self):
        """Test rapid failure detection when some uses succeeded."""
        index = self._make_index()
        index["skill_001"]["usage_count"] = 5
        index["skill_001"]["success_count"] = 3
        detector = DriftDetector(index)
        record = detector._check_rapid_failure("skill_001", index["skill_001"])
        assert record is None

    def test_check_rapid_failure_insufficient_usage(self):
        """Test rapid failure detection with insufficient usage."""
        index = self._make_index()
        index["skill_001"]["usage_count"] = 2
        index["skill_001"]["success_count"] = 0
        detector = DriftDetector(index)
        record = detector._check_rapid_failure("skill_001", index["skill_001"])
        assert record is None

    def test_overall_severity_critical(self):
        """Test overall severity calculation for critical."""
        detector = DriftDetector({})
        records = [
            DriftRecord(severity="warning"),
            DriftRecord(severity="critical"),
        ]
        assert detector._overall_severity(records) == "critical"

    def test_overall_severity_drift(self):
        """Test overall severity calculation for drift."""
        detector = DriftDetector({})
        records = [
            DriftRecord(severity="warning"),
            DriftRecord(severity="drift"),
        ]
        assert detector._overall_severity(records) == "drift"

    def test_overall_severity_warning(self):
        """Test overall severity calculation for warning."""
        detector = DriftDetector({})
        records = [
            DriftRecord(severity="stable"),
            DriftRecord(severity="warning"),
        ]
        assert detector._overall_severity(records) == "warning"

    def test_overall_severity_stable(self):
        """Test overall severity calculation for stable."""
        detector = DriftDetector({})
        records = [DriftRecord(severity="stable")]
        assert detector._overall_severity(records) == "stable"

    def test_make_recommendations_critical_success_rate(self):
        """Test recommendations for critical success rate."""
        detector = DriftDetector({})
        records = [DriftRecord(
            drift_type="success_rate",
            drift_direction="down",
            severity="critical",
        )]
        recs = detector._make_recommendations(records, "critical", {})
        assert len(recs) > 0

    def test_make_recommendations_stale(self):
        """Test recommendations for stale skill."""
        detector = DriftDetector({})
        records = [DriftRecord(drift_type="usage", severity="drift")]
        recs = detector._make_recommendations(records, "drift", {})
        assert len(recs) > 0

    def test_reports_sorted_by_severity(self):
        """Test that reports are sorted by severity."""
        index = {
            "skill_stable": {
                "skill_id": "skill_stable",
                "skill_name": "stable_skill",
                "status": "active",
                "usage_count": 10,
                "success_count": 9,
                "success_rate": 0.9,
                "last_used": datetime.now().isoformat(),
                "risk_level": "low",
            },
            "skill_critical": {
                "skill_id": "skill_critical",
                "skill_name": "critical_skill",
                "status": "active",
                "usage_count": 10,
                "success_count": 0,
                "success_rate": 0.0,
                "last_used": datetime.now().isoformat(),
                "risk_level": "low",
            },
        }
        detector = DriftDetector(index)
        reports = detector.analyze_all()
        # Critical should come first
        assert reports[0].overall_severity == "critical"

    def test_drift_record_fields(self):
        """Test DriftRecord has all required fields."""
        record = DriftRecord(
            skill_id="test",
            drift_type="success_rate",
            drift_direction="down",
            drift_score=0.5,
            severity="warning",
            detected_at=datetime.now().isoformat(),
            reason="test reason",
        )
        assert record.skill_id == "test"
        assert record.drift_score == 0.5

    def test_skill_health_report_fields(self):
        """Test SkillHealthReport has all required fields."""
        report = SkillHealthReport(
            skill_id="test",
            skill_name="test_skill",
            overall_severity="stable",
            drift_records=[],
            recommendations=[],
            analyzed_at=datetime.now().isoformat(),
        )
        assert report.skill_id == "test"
        assert report.overall_severity == "stable"


# ---------------------------------------------------------------------------
# Adaptive-specific behavior tests
# ---------------------------------------------------------------------------

class TestAdaptiveDriftBehavior:
    """Test that adaptive thresholds actually change detection outcomes."""

    def test_adaptive_threshold_changes_detection(self):
        """A skill at 0.65 success rate: detected with defaults, may pass with adaptive."""
        # Build a population with high success rates (mean ~0.90)
        index = {}
        for i in range(10):
            index[f"high_{i}"] = {
                "skill_id": f"high_{i}", "status": "active",
                "usage_count": 20, "success_rate": 0.85 + (i % 4) * 0.04,
                "last_used": datetime.now().isoformat(),
            }
        # Add the test skill
        index["test_skill"] = {
            "skill_id": "test_skill", "status": "active",
            "usage_count": 10, "success_rate": 0.65,
            "last_used": datetime.now().isoformat(),
        }

        detector = DriftDetector(index)
        # The adaptive warning threshold should be higher than 0.70
        # so 0.65 should still be flagged (below adaptive warning)
        report = detector.analyze_skill("test_skill", index["test_skill"])
        # Verify that the adaptive thresholds are actually in effect
        assert detector.thresholds.sample_size == 11
        # 0.65 is below even the adaptive warning (mean ~0.90, std ~0.03 -> warning ~0.87)
        assert report.overall_severity in ("warning", "critical")

    def test_custom_thresholds_override(self):
        """Pre-computed thresholds can be injected."""
        custom = AdaptiveThresholds(
            success_rate_warning=0.95,
            success_rate_critical=0.90,
            staleness_days_warning=7,
            staleness_days_critical=14,
        )
        index = {
            "skill_001": {
                "skill_id": "skill_001", "status": "active",
                "usage_count": 10, "success_rate": 0.92,
                "last_used": datetime.now().isoformat(),
            },
        }
        detector = DriftDetector(index, thresholds=custom)
        record = detector._check_success_rate("skill_001", index["skill_001"])
        # 0.92 < 0.95 (warning) but > 0.90 (critical)
        assert record is not None
        assert record.severity == "warning"

    def test_reason_contains_population_stats(self):
        """Drift records should include population statistics in their reason."""
        index = {}
        for i in range(8):
            index[f"skill_{i}"] = {
                "skill_id": f"skill_{i}", "status": "active",
                "usage_count": 15, "success_rate": 0.80,
                "last_used": datetime.now().isoformat(),
            }
        index["bad_skill"] = {
            "skill_id": "bad_skill", "status": "active",
            "usage_count": 10, "success_rate": 0.30,
            "last_used": datetime.now().isoformat(),
        }
        detector = DriftDetector(index)
        report = detector.analyze_skill("bad_skill", index["bad_skill"])
        # Should have a drift record with population stats in reason
        sr_records = [r for r in report.drift_records if r.drift_type == "success_rate"]
        assert len(sr_records) > 0
        assert "pop mean=" in sr_records[0].reason
