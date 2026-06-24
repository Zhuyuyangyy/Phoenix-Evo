"""Degradation detector for Phoenix-Evo self-repair system."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

import numpy as np


@dataclass
class DegradationSignal:
    """A detected degradation signal."""
    metric_name: str
    current_value: float
    baseline_value: float
    degradation_ratio: float
    severity: str  # "low", "medium", "high", "critical"
    detected_at: float = field(default_factory=time.time)
    metadata: dict[str, Any] = field(default_factory=dict)


class DegradationDetector:
    """Detects performance degradation in system metrics.

    Monitors metrics over time and detects when they deviate
    significantly from established baselines.
    """

    def __init__(
        self,
        window_size: int = 50,
        low_threshold: float = 0.8,
        medium_threshold: float = 0.6,
        high_threshold: float = 0.4,
        critical_threshold: float = 0.2,
    ):
        self.window_size = window_size
        self.low_threshold = low_threshold
        self.medium_threshold = medium_threshold
        self.high_threshold = high_threshold
        self.critical_threshold = critical_threshold
        self._metrics: dict[str, list[float]] = {}
        self._baselines: dict[str, float] = {}
        self._signals: list[DegradationSignal] = []

    def set_baseline(self, metric_name: str, baseline: float) -> None:
        """Set the baseline value for a metric."""
        self._baselines[metric_name] = baseline

    def update(self, metric_name: str, value: float) -> DegradationSignal | None:
        """Update a metric with a new value. Returns DegradationSignal if degradation detected."""
        if metric_name not in self._metrics:
            self._metrics[metric_name] = []

        self._metrics[metric_name].append(value)

        # Keep only the last window_size values
        if len(self._metrics[metric_name]) > self.window_size:
            self._metrics[metric_name] = self._metrics[metric_name][-self.window_size:]

        # Need at least a few data points
        if len(self._metrics[metric_name]) < 5:
            return None

        # Auto-set baseline if not set
        if metric_name not in self._baselines:
            self._baselines[metric_name] = float(np.mean(self._metrics[metric_name][:10]))

        baseline = self._baselines[metric_name]
        if baseline == 0:
            return None

        # Compute degradation ratio
        current_avg = float(np.mean(self._metrics[metric_name][-5:]))
        degradation_ratio = current_avg / baseline

        # Determine severity
        severity = self._classify_severity(degradation_ratio)

        if severity != "none":
            signal = DegradationSignal(
                metric_name=metric_name,
                current_value=current_avg,
                baseline_value=baseline,
                degradation_ratio=degradation_ratio,
                severity=severity,
            )
            self._signals.append(signal)
            return signal

        return None

    def _classify_severity(self, ratio: float) -> str:
        """Classify the severity of degradation based on ratio."""
        if ratio < self.critical_threshold:
            return "critical"
        if ratio < self.high_threshold:
            return "high"
        if ratio < self.medium_threshold:
            return "medium"
        if ratio < self.low_threshold:
            return "low"
        return "none"

    def get_signals(self, severity: str | None = None) -> list[DegradationSignal]:
        """Get degradation signals, optionally filtered by severity."""
        if severity:
            return [s for s in self._signals if s.severity == severity]
        return list(self._signals)

    def get_status(self) -> dict[str, Any]:
        """Get the current degradation status for all metrics."""
        status = {}
        for metric_name, values in self._metrics.items():
            baseline = self._baselines.get(metric_name, 0)
            current = float(np.mean(values[-5:])) if len(values) >= 5 else 0
            ratio = current / baseline if baseline > 0 else 1.0
            status[metric_name] = {
                "current": current,
                "baseline": baseline,
                "ratio": ratio,
                "severity": self._classify_severity(ratio),
            }
        return status

    def reset(self, metric_name: str | None = None) -> None:
        """Reset metrics and baselines."""
        if metric_name:
            self._metrics.pop(metric_name, None)
            self._baselines.pop(metric_name, None)
        else:
            self._metrics.clear()
            self._baselines.clear()
            self._signals.clear()
