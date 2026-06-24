"""
Tests for RiskPolicy module.
"""

import pytest
from core.risk_policy import (
    RiskProfile, RiskPolicy, DANGEROUS_PATTERNS,
    HIGH_RISK_TAGS, MEDIUM_RISK_TAGS, IMMUNE_DECISION,
    SOURCE_FAILED_WEIGHT, SOURCE_SUCCESS_WEIGHT, SOURCE_UNKNOWN_WEIGHT,
    EVIDENCE_REQUIRED, EVIDENCE_RECOMMENDED,
    MIN_PROCEDURE_STEPS, MAX_GOAL_LENGTH, REPEAT_FAILURE_THRESHOLD,
)


class TestRiskProfile:
    """Test suite for RiskProfile."""

    def test_default_values(self):
        """Test default RiskProfile values."""
        profile = RiskProfile()
        assert profile.risk_level == "low"
        assert profile.tags == []
        assert profile.dangerous_patterns_found == []
        assert profile.source_failed is False
        assert profile.has_trajectory_id is False
        assert profile.has_artifacts is False
        assert profile.has_verification is False
        assert profile.procedure_step_count == 0
        assert profile.goal_length == 0
        assert profile.similar_skill_failures == 0
        assert profile.warnings == []
        assert profile.immune_decision == "draft"

    def test_has_high_risk_tag_true(self):
        """Test high risk tag detection."""
        profile = RiskProfile(tags=["privilege_escalation"])
        assert profile.has_high_risk_tag is True

    def test_has_high_risk_tag_false(self):
        """Test high risk tag detection with no high risk tags."""
        profile = RiskProfile(tags=["data_theft"])
        assert profile.has_high_risk_tag is False

    def test_has_medium_risk_tag_true(self):
        """Test medium risk tag detection."""
        profile = RiskProfile(tags=["data_theft"])
        assert profile.has_medium_risk_tag is True

    def test_has_medium_risk_tag_false(self):
        """Test medium risk tag detection with no medium risk tags."""
        profile = RiskProfile(tags=["privilege_escalation"])
        assert profile.has_medium_risk_tag is False

    def test_evidence_complete_true(self):
        """Test evidence complete when all conditions met."""
        profile = RiskProfile(
            has_trajectory_id=True,
            has_artifacts=True,
            procedure_step_count=3,
        )
        assert profile.evidence_complete is True

    def test_evidence_complete_false_no_trajectory(self):
        """Test evidence complete when no trajectory ID."""
        profile = RiskProfile(
            has_trajectory_id=False,
            has_artifacts=True,
            procedure_step_count=3,
        )
        assert profile.evidence_complete is False

    def test_evidence_complete_false_no_artifacts(self):
        """Test evidence complete when no artifacts."""
        profile = RiskProfile(
            has_trajectory_id=True,
            has_artifacts=False,
            procedure_step_count=3,
        )
        assert profile.evidence_complete is False

    def test_evidence_complete_false_few_steps(self):
        """Test evidence complete when too few steps."""
        profile = RiskProfile(
            has_trajectory_id=True,
            has_artifacts=True,
            procedure_step_count=1,
        )
        assert profile.evidence_complete is False

    def test_overgeneralized_true(self):
        """Test overgeneralized detection."""
        profile = RiskProfile(procedure_step_count=1)
        assert profile.overgeneralized is True

    def test_overgeneralized_false(self):
        """Test overgeneralized detection with enough steps."""
        profile = RiskProfile(procedure_step_count=3)
        assert profile.overgeneralized is False

    def test_compute_decision_high_risk_reject(self):
        """Test that high risk tags result in reject."""
        profile = RiskProfile(tags=["privilege_escalation"])
        profile.compute_decision()
        assert profile.immune_decision == "reject"
        assert any("高危" in w for w in profile.warnings)

    def test_compute_decision_dangerous_patterns_reject(self):
        """Test that dangerous patterns result in reject."""
        profile = RiskProfile(dangerous_patterns_found=["rm -rf"])
        profile.compute_decision()
        assert profile.immune_decision == "reject"

    def test_compute_decision_overgeneralized_quarantine(self):
        """Test that overgeneralized results in quarantine."""
        profile = RiskProfile(procedure_step_count=1)
        profile.compute_decision()
        assert profile.immune_decision == "quarantine"

    def test_compute_decision_failed_source_quarantine(self):
        """Test that failed source without artifacts results in quarantine."""
        profile = RiskProfile(source_failed=True, has_artifacts=False)
        profile.compute_decision()
        assert profile.immune_decision == "quarantine"

    def test_compute_decision_failed_source_no_verification_quarantine(self):
        """Test that failed source without verification results in quarantine."""
        profile = RiskProfile(source_failed=True, has_verification=False)
        profile.compute_decision()
        assert profile.immune_decision == "quarantine"

    def test_compute_decision_incomplete_evidence_quarantine(self):
        """Test that incomplete evidence results in quarantine."""
        profile = RiskProfile(
            has_trajectory_id=True,
            has_artifacts=False,
            procedure_step_count=3,
        )
        profile.compute_decision()
        assert profile.immune_decision == "quarantine"

    def test_compute_decision_repeat_failure_quarantine(self):
        """Test that repeat failures result in quarantine."""
        profile = RiskProfile(similar_skill_failures=3)
        profile.compute_decision()
        assert profile.immune_decision == "quarantine"

    def test_compute_decision_medium_risk_quarantine(self):
        """Test that medium risk tags result in quarantine."""
        profile = RiskProfile(tags=["data_theft"])
        profile.compute_decision()
        assert profile.immune_decision == "quarantine"

    def test_compute_decision_clean_draft(self):
        """Test that clean profile results in draft."""
        profile = RiskProfile(
            has_trajectory_id=True,
            has_artifacts=True,
            procedure_step_count=3,
            has_verification=True,
        )
        profile.compute_decision()
        assert profile.immune_decision == "draft"

    def test_compute_decision_missing_artifacts_warning(self):
        """Test that missing artifacts results in quarantine due to incomplete evidence."""
        profile = RiskProfile(
            has_trajectory_id=True,
            has_artifacts=False,
            procedure_step_count=3,
            has_verification=True,
        )
        profile.compute_decision()
        assert profile.immune_decision == "quarantine"
        assert any("证据" in w or "artifacts" in w.lower() or "不全" in w for w in profile.warnings)


class TestRiskPolicy:
    """Test suite for RiskPolicy."""

    def test_evaluate_high_risk(self):
        """Test evaluation with high risk tags."""
        policy = RiskPolicy()
        profile = RiskProfile(tags=["privilege_escalation"])
        result = policy.evaluate(profile)
        assert result.risk_level == "critical"

    def test_evaluate_dangerous_patterns(self):
        """Test evaluation with dangerous patterns."""
        policy = RiskPolicy()
        profile = RiskProfile(dangerous_patterns_found=["rm -rf"])
        result = policy.evaluate(profile)
        assert result.risk_level == "high"

    def test_evaluate_medium_risk(self):
        """Test evaluation with medium risk tags."""
        policy = RiskPolicy()
        profile = RiskProfile(tags=["data_theft"])
        result = policy.evaluate(profile)
        assert result.risk_level == "medium"

    def test_evaluate_low_risk(self):
        """Test evaluation with no risk tags."""
        policy = RiskPolicy()
        profile = RiskProfile()
        result = policy.evaluate(profile)
        assert result.risk_level == "low"

    def test_compute_decision(self):
        """Test that compute_decision delegates to profile."""
        policy = RiskPolicy()
        profile = RiskProfile(tags=["privilege_escalation"])
        result = policy.compute_decision(profile)
        assert result.immune_decision == "reject"


class TestConstants:
    """Test suite for module constants."""

    def test_high_risk_tags(self):
        """Test that high risk tags are defined."""
        assert "privilege_escalation" in HIGH_RISK_TAGS
        assert "destruction" in HIGH_RISK_TAGS
        assert "payment_fraud" in HIGH_RISK_TAGS
        assert "persistence" in HIGH_RISK_TAGS
        assert "ai_harm" in HIGH_RISK_TAGS

    def test_medium_risk_tags(self):
        """Test that medium risk tags are defined."""
        assert "data_theft" in MEDIUM_RISK_TAGS
        assert "network_attack" in MEDIUM_RISK_TAGS
        assert "privacy_violation" in MEDIUM_RISK_TAGS

    def test_dangerous_patterns_count(self):
        """Test that dangerous patterns are defined."""
        assert len(DANGEROUS_PATTERNS) >= 8

    def test_evidence_required(self):
        """Test evidence required fields."""
        assert "trajectory_id" in EVIDENCE_REQUIRED
        assert "task_success" in EVIDENCE_REQUIRED

    def test_thresholds(self):
        """Test threshold values."""
        assert REPEAT_FAILURE_THRESHOLD == 3
        assert MIN_PROCEDURE_STEPS == 2
        assert SOURCE_FAILED_WEIGHT > SOURCE_SUCCESS_WEIGHT

    def test_dangerous_patterns_structure(self):
        """Test dangerous patterns have correct structure."""
        for category, description, keywords in DANGEROUS_PATTERNS:
            assert isinstance(category, str)
            assert isinstance(description, str)
            assert isinstance(keywords, list)
            assert len(keywords) > 0
