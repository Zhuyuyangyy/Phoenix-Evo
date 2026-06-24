"""Ablation runner for Phoenix paper experiments."""

from __future__ import annotations

import itertools
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

from .experiment_definitions import ExperimentDefinition


@dataclass
class AblationConfig:
    """Configuration for an ablation study."""
    ablation_id: str
    experiment_id: str
    components: List[str]
    enabled_combinations: List[List[str]] = field(default_factory=list)
    baseline: List[str] = field(default_factory=list)  # All components enabled
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AblationResult:
    """Result from a single ablation run."""
    ablation_id: str
    enabled_components: List[str]
    disabled_components: List[str]
    metrics: Dict[str, float]
    duration_seconds: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


class AblationRunner:
    """Runs ablation studies for paper experiments.

    Systematically enables/disables components to measure
    their individual and combined contributions.
    """

    def __init__(self):
        self._results: List[AblationResult] = []

    def create_ablation(
        self,
        experiment: ExperimentDefinition,
        components: Optional[List[str]] = None,
    ) -> AblationConfig:
        """Create an ablation configuration for an experiment."""
        if components is None:
            components = [
                "safety_intervention",
                "drift_detection",
                "trust_scoring",
                "self_repair",
                "context_injection",
            ]

        # Generate all combinations (2^n - 1, excluding empty)
        combinations = []
        for r in range(1, len(components) + 1):
            for combo in itertools.combinations(components, r):
                combinations.append(list(combo))

        return AblationConfig(
            ablation_id=f"ablation_{uuid.uuid4().hex[:8]}",
            experiment_id=experiment.experiment_id,
            components=components,
            enabled_combinations=combinations,
            baseline=components,  # All components enabled
        )

    def run_ablation(
        self,
        config: AblationConfig,
        evaluator: Optional[Callable[[List[str]], Dict[str, float]]] = None,
    ) -> List[AblationResult]:
        """Run the ablation study."""
        results = []

        for combo in config.enabled_combinations:
            disabled = [c for c in config.components if c not in combo]

            start_time = time.time()
            if evaluator:
                metrics = evaluator(combo)
            else:
                # Default: compute a simple metric based on enabled components
                metrics = {
                    "component_coverage": len(combo) / len(config.components),
                    "enabled_count": float(len(combo)),
                    "disabled_count": float(len(disabled)),
                }

            duration = time.time() - start_time

            result = AblationResult(
                ablation_id=config.ablation_id,
                enabled_components=combo,
                disabled_components=disabled,
                metrics=metrics,
                duration_seconds=duration,
            )
            results.append(result)
            self._results.append(result)

        return results

    def get_results(
        self,
        ablation_id: Optional[str] = None,
    ) -> List[AblationResult]:
        """Get ablation results, optionally filtered by ablation ID."""
        if ablation_id:
            return [r for r in self._results if r.ablation_id == ablation_id]
        return list(self._results)

    def analyze_contributions(self, results: List[AblationResult]) -> Dict[str, float]:
        """Analyze the contribution of each component.

        Computes the average performance drop when each component
        is disabled across all ablation runs.
        """
        component_impacts: Dict[str, List[float]] = {}

        for result in results:
            for component in result.disabled_components:
                # Use the first metric as the performance indicator
                if result.metrics:
                    metric_val = list(result.metrics.values())[0]
                    component_impacts.setdefault(component, []).append(metric_val)

        contributions = {}
        for component, impacts in component_impacts.items():
            contributions[component] = sum(impacts) / len(impacts) if impacts else 0.0

        return contributions
