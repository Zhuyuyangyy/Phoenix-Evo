"""Tests for skill trust score."""

import time

import pytest

from core.skill_trust_score import (
    SkillTrustScore,
    TrustDimension,
    TrustScoreCalibrator,
    TrustScoreOptimizer,
    TrustThreshold,
)


class TestSkillTrustScore:
    def test_total_trust(self):
        score = SkillTrustScore(
            skill_id="s1",
            t_evidence=0.8,
            t_reliability=0.9,
            t_recency=0.7,
            t_impact=0.6,
        )
        expected = 0.8 * 0.9 * 0.7 * 0.6
        assert score.total_trust == pytest.approx(expected, abs=0.001)

    def test_total_trust_perfect(self):
        score = SkillTrustScore(skill_id="s1")
        assert score.total_trust == 1.0

    def test_total_trust_zero(self):
        score = SkillTrustScore(skill_id="s1", t_reliability=0.0)
        assert score.total_trust == 0.0

    def test_to_dict(self):
        score = SkillTrustScore(skill_id="s1", t_evidence=0.5)
        d = score.to_dict()
        assert d["skill_id"] == "s1"
        assert "total_trust" in d

    def test_update_dimension(self):
        score = SkillTrustScore(skill_id="s1")
        score.update_dimension(TrustDimension.EVIDENCE, 0.7)
        assert score.t_evidence == 0.7
        assert len(score.history) == 1

    def test_update_dimension_clamped(self):
        score = SkillTrustScore(skill_id="s1")
        score.update_dimension(TrustDimension.RELIABILITY, 1.5)
        assert score.t_reliability == 1.0
        score.update_dimension(TrustDimension.RELIABILITY, -0.5)
        assert score.t_reliability == 0.0

    def test_formula_components(self):
        """Test T(S) = T_ev × T_re × T_rt × T_im"""
        score = SkillTrustScore(
            skill_id="s1",
            t_evidence=0.5,
            t_reliability=0.8,
            t_recency=0.9,
            t_impact=0.7,
        )
        assert score.total_trust == pytest.approx(0.5 * 0.8 * 0.9 * 0.7, abs=0.001)


class TestTrustThreshold:
    def test_auto_approve(self):
        threshold = TrustThreshold()
        assert threshold.classify(0.95) == "auto_approve"

    def test_approved_with_warning(self):
        threshold = TrustThreshold()
        assert threshold.classify(0.75) == "approved_with_warning"

    def test_requires_review(self):
        threshold = TrustThreshold()
        assert threshold.classify(0.6) == "requires_review"

    def test_requires_manual_review(self):
        threshold = TrustThreshold()
        assert threshold.classify(0.3) == "requires_manual_review"

    def test_auto_revoke(self):
        threshold = TrustThreshold()
        assert threshold.classify(0.1) == "auto_revoke"

    def test_boundary_values(self):
        threshold = TrustThreshold()
        assert threshold.classify(0.9) == "auto_approve"
        assert threshold.classify(0.7) == "approved_with_warning"
        assert threshold.classify(0.5) == "requires_review"
        # 0.2 is at the auto_revoke boundary (>=0.2 means requires_manual_review)
        assert threshold.classify(0.2) == "requires_manual_review"
        assert threshold.classify(0.1) == "auto_revoke"


class TestTrustScoreOptimizer:
    def test_default_weights(self):
        opt = TrustScoreOptimizer()
        weights = opt.optimize_weights()
        assert abs(sum(weights.values()) - 1.0) < 0.01

    def test_with_observations(self):
        opt = TrustScoreOptimizer()
        for i in range(20):
            score = SkillTrustScore(
                skill_id="s1",
                t_evidence=0.8 if i < 10 else 0.3,
                t_reliability=0.9,
                t_recency=0.7,
                t_impact=0.6,
            )
            opt.add_observation(score, actual_outcome=(i < 10))
        weights = opt.optimize_weights()
        assert len(weights) == 4
        assert abs(sum(weights.values()) - 1.0) < 0.01

    def test_weights_sum_to_one(self):
        opt = TrustScoreOptimizer()
        for _i in range(15):
            score = SkillTrustScore(skill_id="s1")
            opt.add_observation(score, actual_outcome=True)
        weights = opt.optimize_weights()
        assert abs(sum(weights.values()) - 1.0) < 0.01


class TestTrustScoreCalibrator:
    def test_calibrate_no_data(self):
        cal = TrustScoreCalibrator()
        score = cal.calibrate("s1")
        assert score.skill_id == "s1"
        assert score.total_trust == 1.0  # Default

    def test_calibrate_with_data(self):
        cal = TrustScoreCalibrator()
        for _ in range(50):
            cal.record_outcome("s1", success=True)
        score = cal.calibrate("s1")
        assert score.t_reliability == 1.0
        assert score.t_evidence > 0

    def test_calibrate_with_failures(self):
        cal = TrustScoreCalibrator()
        for _ in range(40):
            cal.record_outcome("s1", success=True)
        for _ in range(10):
            cal.record_outcome("s1", success=False)
        score = cal.calibrate("s1")
        assert score.t_reliability == pytest.approx(0.8, abs=0.01)

    def test_recency_decay(self):
        cal = TrustScoreCalibrator(half_life_seconds=1.0)
        cal.record_outcome("s1", success=True, timestamp=time.time() - 10)
        score = cal.calibrate("s1")
        assert score.t_recency < 0.1  # Should be very low after 10 half-lives

    def test_get_all_scores(self):
        cal = TrustScoreCalibrator()
        cal.record_outcome("s1", success=True)
        cal.record_outcome("s2", success=False)
        scores = cal.get_all_scores()
        assert "s1" in scores
        assert "s2" in scores

    def test_evidence_trust_saturates(self):
        cal = TrustScoreCalibrator()
        for _ in range(200):
            cal.record_outcome("s1", success=True)
        score = cal.calibrate("s1")
        assert score.t_evidence == 1.0  # Saturated at 100

    def test_impact_trust_with_recent_failures(self):
        cal = TrustScoreCalibrator(half_life_seconds=86400)
        for _ in range(50):
            cal.record_outcome("s1", success=True)
        for _ in range(5):
            cal.record_outcome("s1", success=False)
        score = cal.calibrate("s1")
        assert score.t_impact < 1.0
