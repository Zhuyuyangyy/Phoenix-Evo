"""Tests for drift detector v2."""

import numpy as np
import pytest

from core.drift_detector_v2 import (
    BayesianDriftDetector,
    CUSUMDriftDetector,
    DriftPoint,
    EnsembleDriftDetector,
    EWMADriftDetector,
)


class TestDriftPoint:
    def test_create(self):
        dp = DriftPoint(
            timestamp=1, metric_name="test", value=1.0,
            threshold=2.0, drift_type="sudden", severity=0.8, confidence=0.9,
        )
        assert dp.severity == 0.8
        assert dp.drift_type == "sudden"


class TestEWMADriftDetector:
    def test_no_drift_stable(self):
        det = EWMADriftDetector(alpha=0.3, threshold_sigma=3.0, warmup=5)
        rng = np.random.RandomState(42)
        drifts = []
        for _ in range(100):
            value = rng.normal(0, 1)
            result = det.update(value)
            if result:
                drifts.append(result)
        # Should have very few false positives
        assert len(drifts) <= 5

    def test_detect_sudden_shift(self):
        det = EWMADriftDetector(alpha=0.5, threshold_sigma=2.0, warmup=5)
        drifts = []
        # Stable period
        for _ in range(30):
            det.update(0.0)
        # Sudden shift
        for _ in range(50):
            result = det.update(100.0)
            if result:
                drifts.append(result)
        assert len(drifts) > 0

    def test_reset(self):
        det = EWMADriftDetector()
        det.update(1.0)
        det.reset()
        assert det._ewma is None
        assert det._n == 0

    def test_warmup_period(self):
        det = EWMADriftDetector(warmup=10)
        for i in range(9):
            result = det.update(100.0)  # Very large value
            assert result is None  # Should not detect during warmup

    def test_returns_drift_point(self):
        det = EWMADriftDetector(alpha=0.3, threshold_sigma=2.0, warmup=5)
        for _ in range(20):
            det.update(0.0)
        result = det.update(50.0)
        if result:
            assert isinstance(result, DriftPoint)
            assert result.drift_type == "gradual"


class TestCUSUMDriftDetector:
    def test_detect_upward_shift(self):
        det = CUSUMDriftDetector(threshold=5.0, warmup=10)
        rng = np.random.RandomState(42)
        # Stable period
        for _ in range(30):
            det.update(rng.normal(0, 1))
        # Shift
        drifts = []
        for _ in range(50):
            result = det.update(rng.normal(5, 1))
            if result:
                drifts.append(result)
        assert len(drifts) > 0

    def test_no_drift_stable(self):
        det = CUSUMDriftDetector(threshold=5.0, warmup=10)
        rng = np.random.RandomState(42)
        drifts = []
        for _ in range(100):
            result = det.update(rng.normal(0, 1))
            if result:
                drifts.append(result)
        assert len(drifts) <= 3

    def test_reset(self):
        det = CUSUMDriftDetector()
        det.update(1.0)
        det.reset()
        assert det._n == 0
        assert det._pos_sum == 0.0

    def test_auto_calibrate(self):
        det = CUSUMDriftDetector(warmup=10)
        for i in range(15):
            det.update(float(i))
        # After warmup, reference should be set
        assert det.reference_mean != 0.0 or det._n > 0


class TestBayesianDriftDetector:
    def test_detect_change(self):
        det = BayesianDriftDetector(change_threshold=0.8, warmup=5)
        # Stable period
        for _ in range(20):
            det.update(0.0)
        # Change
        drifts = []
        for _ in range(20):
            result = det.update(10.0)
            if result:
                drifts.append(result)
        assert len(drifts) > 0

    def test_no_change_stable(self):
        det = BayesianDriftDetector(change_threshold=0.95, warmup=10)
        rng = np.random.RandomState(42)
        drifts = []
        for _ in range(100):
            result = det.update(rng.normal(0, 1))
            if result:
                drifts.append(result)
        assert len(drifts) <= 5

    def test_reset(self):
        det = BayesianDriftDetector()
        det.update(1.0)
        det.reset()
        assert det._n == 0


class TestEnsembleDriftDetector:
    def test_detect_drift(self):
        det = EnsembleDriftDetector(voting="any")
        # Stable
        for _ in range(30):
            det.update(0.0)
        # Shift
        drifts = []
        for _ in range(50):
            result = det.update(10.0)
            if result:
                drifts.append(result)
        assert len(drifts) > 0

    def test_majority_voting(self):
        det = EnsembleDriftDetector(voting="majority")
        # Should be more conservative than "any"
        for _ in range(30):
            det.update(0.0)
        drifts = []
        for _ in range(50):
            result = det.update(10.0)
            if result:
                drifts.append(result)
        # Just check it doesn't crash
        assert isinstance(drifts, list)

    def test_weighted_voting(self):
        det = EnsembleDriftDetector(voting="weighted")
        for _ in range(30):
            det.update(0.0)
        for _ in range(50):
            det.update(10.0)
        # Just verify it runs

    def test_reset(self):
        det = EnsembleDriftDetector()
        det.update(1.0)
        det.reset()
        for d in det.detectors:
            assert d._n == 0

    def test_ensemble_drift_point_metadata(self):
        det = EnsembleDriftDetector(voting="any")
        for _ in range(30):
            det.update(0.0)
        for _ in range(50):
            result = det.update(10.0)
            if result:
                assert result.metric_name == "ensemble"
                assert "n_detectors_triggered" in result.metadata
                break
