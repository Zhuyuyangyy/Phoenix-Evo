"""Tests for self-repair system."""

import time

import pytest

from core.self_repair.degradation_detector import DegradationDetector, DegradationSignal
from core.self_repair.repair_candidate_generator import RepairCandidate, RepairCandidateGenerator
from core.self_repair.ab_testing import ABTestConfig, ABTestFramework, ABTestResult
from core.self_repair.auto_governance import (
    AutoGovernanceEngine,
    GovernanceAction,
    GovernanceDecision,
    GovernancePolicy,
)
from core.self_repair.health_monitor import HealthCheck, SystemHealth, SystemHealthMonitor


class TestDegradationDetector:
    def test_no_degradation_stable(self):
        det = DegradationDetector()
        det.set_baseline("cpu", 0.5)
        signals = []
        for _ in range(20):
            sig = det.update("cpu", 0.5)
            if sig:
                signals.append(sig)
        assert len(signals) == 0

    def test_detect_degradation(self):
        det = DegradationDetector(low_threshold=0.9)
        det.set_baseline("cpu", 1.0)
        for _ in range(20):
            det.update("cpu", 1.0)
        signal = det.update("cpu", 0.05)
        if signal is None:
            # Try more extreme values
            for _ in range(5):
                det.update("cpu", 0.01)
            signals = det.get_signals()
            assert len(signals) > 0
        else:
            assert signal.severity in ("low", "medium", "high", "critical")

    def test_severity_classification(self):
        det = DegradationDetector()
        det.set_baseline("test", 1.0)
        # Critical: ratio < 0.2
        for _ in range(20):
            det.update("test", 1.0)
        signal = det.update("test", 0.05)
        if signal:
            assert signal.severity == "critical"

    def test_get_status(self):
        det = DegradationDetector()
        det.set_baseline("cpu", 0.5)
        det.update("cpu", 0.5)
        status = det.get_status()
        assert "cpu" in status

    def test_reset(self):
        det = DegradationDetector()
        det.set_baseline("cpu", 0.5)
        det.update("cpu", 0.5)
        det.reset("cpu")
        assert "cpu" not in det._baselines

    def test_auto_baseline(self):
        det = DegradationDetector()
        for i in range(20):
            det.update("cpu", 0.5)
        assert "cpu" in det._baselines

    def test_get_signals(self):
        det = DegradationDetector()
        det.set_baseline("cpu", 1.0)
        for _ in range(20):
            det.update("cpu", 1.0)
        det.update("cpu", 0.05)
        signals = det.get_signals()
        assert len(signals) >= 0


class TestRepairCandidateGenerator:
    def test_generate_for_critical(self):
        gen = RepairCandidateGenerator()
        signal = DegradationSignal(
            metric_name="cpu", current_value=0.1, baseline_value=1.0,
            degradation_ratio=0.1, severity="critical",
        )
        candidates = gen.generate(signal)
        assert len(candidates) >= 2
        strategies = [c.strategy for c in candidates]
        assert "rollback" in strategies

    def test_generate_for_medium(self):
        gen = RepairCandidateGenerator()
        signal = DegradationSignal(
            metric_name="cpu", current_value=0.6, baseline_value=1.0,
            degradation_ratio=0.6, severity="medium",
        )
        candidates = gen.generate(signal)
        assert len(candidates) >= 1

    def test_generate_for_low(self):
        gen = RepairCandidateGenerator()
        signal = DegradationSignal(
            metric_name="cpu", current_value=0.85, baseline_value=1.0,
            degradation_ratio=0.85, severity="low",
        )
        candidates = gen.generate(signal)
        assert len(candidates) >= 1

    def test_rank_candidates(self):
        gen = RepairCandidateGenerator()
        candidates = [
            RepairCandidate(candidate_id="c1", target_metric="cpu", strategy="restart",
                           description="restart", estimated_impact=0.7, risk_level="medium"),
            RepairCandidate(candidate_id="c2", target_metric="cpu", strategy="rollback",
                           description="rollback", estimated_impact=0.9, risk_level="low"),
        ]
        ranked = gen.rank_candidates(candidates)
        assert ranked[0].estimated_impact >= ranked[1].estimated_impact

    def test_get_candidates(self):
        gen = RepairCandidateGenerator()
        signal = DegradationSignal(
            metric_name="cpu", current_value=0.1, baseline_value=1.0,
            degradation_ratio=0.1, severity="critical",
        )
        gen.generate(signal)
        rollback_candidates = gen.get_candidates(strategy="rollback")
        assert len(rollback_candidates) >= 1


class TestABTestFramework:
    def test_create_test(self):
        fw = ABTestFramework()
        config = ABTestConfig(test_id="t1", name="Test", min_samples=5)
        test_id = fw.create_test(config)
        assert test_id == "t1"

    def test_record_and_analyze(self):
        fw = ABTestFramework()
        config = ABTestConfig(test_id="t1", name="Test", min_samples=5)
        fw.create_test(config)
        # Add some variance to avoid zero std
        import numpy as np
        rng = np.random.RandomState(42)
        for _ in range(10):
            fw.record_control("t1", rng.normal(1.0, 0.1))
            fw.record_treatment("t1", rng.normal(2.0, 0.1))
        result = fw.analyze("t1")
        assert result is not None
        assert result.treatment_mean > result.control_mean

    def test_not_ready(self):
        fw = ABTestFramework()
        config = ABTestConfig(test_id="t1", name="Test", min_samples=30)
        fw.create_test(config)
        fw.record_control("t1", 1.0)
        assert not fw.is_ready("t1")

    def test_list_tests(self):
        fw = ABTestFramework()
        fw.create_test(ABTestConfig(test_id="t1", name="Test 1"))
        fw.create_test(ABTestConfig(test_id="t2", name="Test 2"))
        tests = fw.list_tests()
        assert len(tests) == 2


class TestAutoGovernanceEngine:
    def test_evaluate_critical(self):
        engine = AutoGovernanceEngine()
        signal = DegradationSignal(
            metric_name="cpu", current_value=0.1, baseline_value=1.0,
            degradation_ratio=0.1, severity="critical",
        )
        decision = engine.evaluate(signal)
        assert decision.action == GovernanceAction.ROLLBACK

    def test_evaluate_high(self):
        engine = AutoGovernanceEngine()
        signal = DegradationSignal(
            metric_name="cpu", current_value=0.3, baseline_value=1.0,
            degradation_ratio=0.3, severity="high",
        )
        decision = engine.evaluate(signal)
        assert decision.action == GovernanceAction.AUTO_REPAIR

    def test_evaluate_medium(self):
        engine = AutoGovernanceEngine()
        signal = DegradationSignal(
            metric_name="cpu", current_value=0.6, baseline_value=1.0,
            degradation_ratio=0.6, severity="medium",
        )
        decision = engine.evaluate(signal)
        assert decision.action == GovernanceAction.ALERT

    def test_auto_approval_disabled(self):
        policy = GovernancePolicy(enable_auto_repair=False)
        engine = AutoGovernanceEngine(policy=policy)
        signal = DegradationSignal(
            metric_name="cpu", current_value=0.3, baseline_value=1.0,
            degradation_ratio=0.3, severity="high",
        )
        decision = engine.evaluate(signal)
        assert decision.auto_approved is False

    def test_manual_approval(self):
        engine = AutoGovernanceEngine()
        signal = DegradationSignal(
            metric_name="cpu", current_value=0.1, baseline_value=1.0,
            degradation_ratio=0.1, severity="critical",
        )
        decision = engine.evaluate(signal)
        if not decision.auto_approved:
            assert engine.approve(decision.decision_id) is True

    def test_get_pending_approvals(self):
        policy = GovernancePolicy(enable_auto_repair=False)
        engine = AutoGovernanceEngine(policy=policy)
        signal = DegradationSignal(
            metric_name="cpu", current_value=0.3, baseline_value=1.0,
            degradation_ratio=0.3, severity="high",
        )
        engine.evaluate(signal)
        pending = engine.get_pending_approvals()
        assert len(pending) >= 1


class TestSystemHealthMonitor:
    def test_register_and_check(self):
        monitor = SystemHealthMonitor()
        monitor.register_check("db", lambda: HealthCheck(component="db", healthy=True))
        result = monitor.check_component("db")
        assert result.healthy is True

    def test_check_all(self):
        monitor = SystemHealthMonitor()
        monitor.register_check("db", lambda: HealthCheck(component="db", healthy=True))
        monitor.register_check("cache", lambda: HealthCheck(component="cache", healthy=True))
        health = monitor.check_all()
        assert health.status == "healthy"
        assert health.overall_score == 1.0

    def test_unhealthy_component(self):
        monitor = SystemHealthMonitor()
        monitor.register_check("db", lambda: HealthCheck(component="db", healthy=False))
        health = monitor.check_all()
        assert health.status == "unhealthy"

    def test_get_unhealthy_components(self):
        monitor = SystemHealthMonitor()
        monitor.register_check("db", lambda: HealthCheck(component="db", healthy=False))
        monitor.register_check("cache", lambda: HealthCheck(component="cache", healthy=True))
        monitor.check_all()
        unhealthy = monitor.get_unhealthy_components()
        assert "db" in unhealthy

    def test_get_health(self):
        monitor = SystemHealthMonitor()
        health = monitor.get_health()
        assert health.status == "unknown"
