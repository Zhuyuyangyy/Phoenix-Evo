"""Drift detection v2 with EWMA, CUSUM, Bayesian, and Ensemble detectors."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np


@dataclass
class DriftPoint:
    """Represents a detected drift point."""
    timestamp: int
    metric_name: str
    value: float
    threshold: float
    drift_type: str  # "gradual" or "sudden"
    severity: float  # 0.0 to 1.0
    confidence: float  # 0.0 to 1.0
    metadata: Dict[str, Any] = field(default_factory=dict)


class EWMADriftDetector:
    """Exponentially Weighted Moving Average drift detector.

    Detects gradual drift by tracking the EWMA of a metric
    and flagging when it deviates beyond control limits.
    """

    def __init__(
        self,
        alpha: float = 0.3,
        threshold_sigma: float = 3.0,
        warmup: int = 10,
    ):
        self.alpha = alpha
        self.threshold_sigma = threshold_sigma
        self.warmup = warmup
        self._ewma: Optional[float] = None
        self._ewma_var: Optional[float] = None
        self._baseline_std: Optional[float] = None
        self._n: int = 0
        self._history: List[float] = []

    def update(self, value: float) -> Optional[DriftPoint]:
        """Update the detector with a new value. Returns DriftPoint if drift detected."""
        self._n += 1
        self._history.append(value)

        if self._ewma is None:
            self._ewma = value
            self._ewma_var = 0.0
            return None

        # Update EWMA
        diff = value - self._ewma
        self._ewma = self.alpha * value + (1 - self.alpha) * self._ewma

        # Update EWMA variance
        self._ewma_var = self.alpha * (diff ** 2) + (1 - self.alpha) * (self._ewma_var)

        if self._n < self.warmup:
            return None

        # After warmup, compute baseline std from warmup data if not set
        if self._baseline_std is None and self._n >= self.warmup:
            warmup_data = self._history[:self.warmup]
            if len(warmup_data) > 1:
                self._baseline_std = float(np.std(warmup_data, ddof=1))
            if self._baseline_std is None or self._baseline_std < 1e-10:
                # If warmup data had zero variance, use a small default
                # but also check if the EWMA variance has built up
                self._baseline_std = 1e-10

        # For detection, use the baseline_std (from warmup) as the reference
        # This prevents the variance from adapting to the shift
        if self._baseline_std is not None and self._baseline_std > 0:
            std = self._baseline_std
        else:
            # Fall back to EWMA std if baseline is degenerate
            std = math.sqrt(self._ewma_var) if self._ewma_var > 0 else 1e-10

        # Check control limits using the deviation from EWMA
        z_score = abs(diff) / std

        if z_score > self.threshold_sigma:
            severity = min(z_score / (2 * self.threshold_sigma), 1.0)
            return DriftPoint(
                timestamp=self._n,
                metric_name="ewma",
                value=value,
                threshold=self._ewma + self.threshold_sigma * std,
                drift_type="gradual",
                severity=severity,
                confidence=min(z_score / self.threshold_sigma, 1.0),
            )
        return None

    def reset(self) -> None:
        """Reset the detector state."""
        self._ewma = None
        self._ewma_var = None
        self._baseline_std = None
        self._n = 0
        self._history = []


class CUSUMDriftDetector:
    """Cumulative Sum drift detector.

    Detects sudden shifts by tracking the cumulative sum
    of deviations from the reference mean.
    """

    def __init__(
        self,
        reference_mean: float = 0.0,
        reference_std: float = 1.0,
        threshold: float = 5.0,
        delta: float = 1.0,
        warmup: int = 10,
    ):
        self.reference_mean = reference_mean
        self.reference_std = max(reference_std, 1e-10)
        self.threshold = threshold
        self.delta = delta
        self.warmup = warmup
        self._pos_sum: float = 0.0
        self._neg_sum: float = 0.0
        self._n: int = 0
        self._values: List[float] = []

    def update(self, value: float) -> Optional[DriftPoint]:
        """Update the detector with a new value."""
        self._n += 1
        self._values.append(value)

        # Auto-calibrate reference from warmup period
        if self._n == self.warmup:
            self.reference_mean = float(np.mean(self._values))
            self.reference_std = max(float(np.std(self._values)), 1e-10)

        if self._n < self.warmup:
            return None

        # Standardize
        z = (value - self.reference_mean) / self.reference_std

        # Update CUSUM
        self._pos_sum = max(0, self._pos_sum + z - self.delta)
        self._neg_sum = max(0, self._neg_sum - z - self.delta)

        if self._pos_sum > self.threshold:
            severity = min(self._pos_sum / (2 * self.threshold), 1.0)
            self._pos_sum = 0  # Reset after detection
            return DriftPoint(
                timestamp=self._n,
                metric_name="cusum_positive",
                value=value,
                threshold=self.threshold,
                drift_type="sudden",
                severity=severity,
                confidence=min(self._pos_sum / self.threshold + 0.5, 1.0) if self._pos_sum > 0 else severity,
            )

        if self._neg_sum > self.threshold:
            severity = min(self._neg_sum / (2 * self.threshold), 1.0)
            self._neg_sum = 0
            return DriftPoint(
                timestamp=self._n,
                metric_name="cusum_negative",
                value=value,
                threshold=self.threshold,
                drift_type="sudden",
                severity=severity,
                confidence=severity,
            )

        return None

    def reset(self) -> None:
        """Reset the detector state."""
        self._pos_sum = 0.0
        self._neg_sum = 0.0
        self._n = 0
        self._values = []


class BayesianDriftDetector:
    """Bayesian change-point detection.

    Uses conjugate priors to detect distributional changes
    in streaming data.
    """

    def __init__(
        self,
        prior_mean: float = 0.0,
        prior_precision: float = 1.0,
        change_threshold: float = 0.95,
        warmup: int = 10,
    ):
        self.prior_mean = prior_mean
        self.prior_precision = prior_precision
        self.change_threshold = change_threshold
        self.warmup = warmup
        self._posterior_mean: float = prior_mean
        self._posterior_precision: float = prior_precision
        self._n: int = 0
        self._running_mean: float = 0.0
        self._running_var: float = 0.0

    def update(self, value: float) -> Optional[DriftPoint]:
        """Update the detector with a new value."""
        self._n += 1

        # Update running statistics
        old_mean = self._running_mean
        self._running_mean = old_mean + (value - old_mean) / self._n
        if self._n > 1:
            self._running_var = self._running_var + (value - old_mean) * (value - self._running_mean)

        if self._n < self.warmup:
            return None

        # Compute Bayes factor for change point
        data_var = self._running_var / (self._n - 1) if self._n > 1 else 1.0
        data_std = math.sqrt(max(data_var, 1e-10))

        # How likely is this value under the current posterior vs. a new segment?
        z_score = abs(value - self._posterior_mean) / (data_std + 1e-10)

        # Approximate change probability
        change_prob = 1.0 - math.exp(-0.5 * z_score ** 2)

        if change_prob > self.change_threshold:
            # Reset posterior for new segment
            self._posterior_mean = value
            self._posterior_precision = 1.0
            return DriftPoint(
                timestamp=self._n,
                metric_name="bayesian",
                value=value,
                threshold=self.change_threshold,
                drift_type="sudden",
                severity=change_prob,
                confidence=change_prob,
            )

        # Update posterior (conjugate normal-normal update)
        self._posterior_precision += 1.0 / (data_var + 1e-10)
        self._posterior_mean = (
            (self._posterior_precision - 1.0 / (data_var + 1e-10)) * self._posterior_mean
            + value / (data_var + 1e-10)
        ) / self._posterior_precision

        return None

    def reset(self) -> None:
        """Reset the detector state."""
        self._posterior_mean = self.prior_mean
        self._posterior_precision = self.prior_precision
        self._n = 0
        self._running_mean = 0.0
        self._running_var = 0.0


class EnsembleDriftDetector:
    """Ensemble of multiple drift detectors.

    Combines EWMA, CUSUM, and Bayesian detectors using
    majority voting or weighted averaging.
    """

    def __init__(
        self,
        detectors: Optional[List[Any]] = None,
        voting: str = "majority",
        weights: Optional[Dict[str, float]] = None,
    ):
        self.detectors = detectors or [
            EWMADriftDetector(),
            CUSUMDriftDetector(),
            BayesianDriftDetector(),
        ]
        self.voting = voting
        self.weights = weights or {
            "ewma": 0.3,
            "cusum": 0.4,
            "bayesian": 0.3,
        }

    def update(self, value: float) -> Optional[DriftPoint]:
        """Update all detectors and aggregate results."""
        detections = []
        for detector in self.detectors:
            result = detector.update(value)
            if result is not None:
                detections.append(result)

        if not detections:
            return None

        if self.voting == "majority":
            if len(detections) >= len(self.detectors) / 2:
                return self._aggregate_detections(detections)
            return None
        elif self.voting == "any":
            return self._aggregate_detections(detections)
        elif self.voting == "weighted":
            total_weight = sum(
                self.weights.get(d.metric_name.split("_")[0], 0.33)
                for d in detections
            )
            if total_weight >= 0.5:
                return self._aggregate_detections(detections)
            return None
        else:
            return self._aggregate_detections(detections)

    def _aggregate_detections(self, detections: List[DriftPoint]) -> DriftPoint:
        """Aggregate multiple detections into a single DriftPoint."""
        avg_severity = sum(d.severity for d in detections) / len(detections)
        avg_confidence = sum(d.confidence for d in detections) / len(detections)

        return DriftPoint(
            timestamp=detections[0].timestamp,
            metric_name="ensemble",
            value=detections[0].value,
            threshold=0.0,
            drift_type="sudden" if any(d.drift_type == "sudden" for d in detections) else "gradual",
            severity=avg_severity,
            confidence=avg_confidence,
            metadata={"n_detectors_triggered": len(detections)},
        )

    def reset(self) -> None:
        """Reset all detectors."""
        for detector in self.detectors:
            detector.reset()
