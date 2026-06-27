"""A/B testing framework for Phoenix-Evo self-repair system."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np


@dataclass
class ABTestConfig:
    """Configuration for an A/B test."""
    test_id: str
    name: str
    description: str = ""
    metric_name: str = ""
    control_config: dict[str, Any] = field(default_factory=dict)
    treatment_config: dict[str, Any] = field(default_factory=dict)
    min_samples: int = 30
    significance_level: float = 0.05
    max_duration_seconds: float = 86400.0  # 24 hours
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ABTestResult:
    """Result of an A/B test."""
    test_id: str
    control_mean: float
    treatment_mean: float
    control_std: float
    treatment_std: float
    control_n: int
    treatment_n: int
    p_value: float
    effect_size: float
    significant: bool
    winner: str | None  # "control", "treatment", or None
    confidence: float
    metadata: dict[str, Any] = field(default_factory=dict)


class ABTestFramework:
    """Framework for running A/B tests on repair candidates.

    Compares control (current) vs. treatment (repair) configurations
    and determines statistical significance.
    """

    def __init__(self):
        self._tests: dict[str, ABTestConfig] = {}
        self._control_data: dict[str, list[float]] = {}
        self._treatment_data: dict[str, list[float]] = {}

    def create_test(self, config: ABTestConfig) -> str:
        """Create a new A/B test. Returns the test ID."""
        self._tests[config.test_id] = config
        self._control_data[config.test_id] = []
        self._treatment_data[config.test_id] = []
        return config.test_id

    def record_control(self, test_id: str, value: float) -> None:
        """Record a control observation."""
        if test_id in self._control_data:
            self._control_data[test_id].append(value)

    def record_treatment(self, test_id: str, value: float) -> None:
        """Record a treatment observation."""
        if test_id in self._treatment_data:
            self._treatment_data[test_id].append(value)

    def analyze(self, test_id: str) -> ABTestResult | None:
        """Analyze the results of an A/B test."""
        if test_id not in self._tests:
            return None

        control = self._control_data.get(test_id, [])
        treatment = self._treatment_data.get(test_id, [])

        if not control or not treatment:
            return None

        config = self._tests[test_id]
        control_arr = np.array(control)
        treatment_arr = np.array(treatment)

        control_mean = float(np.mean(control_arr))
        treatment_mean = float(np.mean(treatment_arr))
        control_std = float(np.std(control_arr, ddof=1)) if len(control_arr) > 1 else 0.0
        treatment_std = float(np.std(treatment_arr, ddof=1)) if len(treatment_arr) > 1 else 0.0

        # Welch's t-test
        from scipy import stats as scipy_stats
        t_stat, p_value = scipy_stats.ttest_ind(control_arr, treatment_arr, equal_var=False)

        # Cohen's d
        pooled_std = np.sqrt((control_std**2 + treatment_std**2) / 2)
        effect_size = float((treatment_mean - control_mean) / pooled_std) if pooled_std > 0 else 0.0

        significant = p_value < config.significance_level
        winner = None
        if significant:
            winner = "treatment" if treatment_mean > control_mean else "control"

        confidence = 1.0 - p_value

        return ABTestResult(
            test_id=test_id,
            control_mean=control_mean,
            treatment_mean=treatment_mean,
            control_std=control_std,
            treatment_std=treatment_std,
            control_n=len(control),
            treatment_n=len(treatment),
            p_value=float(p_value),
            effect_size=effect_size,
            significant=significant,
            winner=winner,
            confidence=confidence,
        )

    def is_ready(self, test_id: str) -> bool:
        """Check if an A/B test has enough data for analysis."""
        config = self._tests.get(test_id)
        if not config:
            return False
        control_n = len(self._control_data.get(test_id, []))
        treatment_n = len(self._treatment_data.get(test_id, []))
        return control_n >= config.min_samples and treatment_n >= config.min_samples

    def list_tests(self) -> list[dict[str, Any]]:
        """List all A/B tests."""
        results = []
        for test_id, config in self._tests.items():
            control_n = len(self._control_data.get(test_id, []))
            treatment_n = len(self._treatment_data.get(test_id, []))
            results.append({
                "test_id": test_id,
                "name": config.name,
                "control_n": control_n,
                "treatment_n": treatment_n,
                "ready": self.is_ready(test_id),
            })
        return results
