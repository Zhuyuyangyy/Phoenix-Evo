"""Experiment definitions for the Phoenix paper (E1-E6)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class ExperimentDefinition:
    """Definition of a paper experiment."""
    experiment_id: str
    title: str
    description: str
    hypothesis: str
    independent_variables: List[str]
    dependent_variables: List[str]
    control_conditions: Dict[str, Any]
    treatment_conditions: Dict[str, Any]
    sample_size: int
    significance_level: float = 0.05
    metrics: List[str] = field(default_factory=list)
    expected_results: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


# E1: Safety Intervention Effectiveness
E1 = ExperimentDefinition(
    experiment_id="E1",
    title="Safety Intervention Effectiveness",
    description="Measures the effectiveness of Phoenix safety interventions in preventing unsafe agent actions.",
    hypothesis="Phoenix safety mechanisms reduce unsafe actions by at least 50% compared to vanilla agents.",
    independent_variables=["safety_mechanism_enabled"],
    dependent_variables=["safety_violation_rate", "task_completion_rate"],
    control_conditions={"safety_mechanism_enabled": False},
    treatment_conditions={"safety_mechanism_enabled": True},
    sample_size=100,
    metrics=["safety_violation_rate", "task_completion_rate", "false_positive_rate"],
    expected_results={
        "safety_violation_rate_reduction": 0.5,
        "task_completion_rate_maintained": 0.9,
    },
)

# E2: Drift Detection Accuracy
E2 = ExperimentDefinition(
    experiment_id="E2",
    title="Drift Detection Accuracy",
    description="Evaluates the accuracy of Phoenix drift detection algorithms.",
    hypothesis="The ensemble drift detector achieves >90% detection rate with <5% false positive rate.",
    independent_variables=["detector_type"],
    dependent_variables=["detection_rate", "false_positive_rate", "detection_latency"],
    control_conditions={"detector_type": "ewma"},
    treatment_conditions={"detector_type": "ensemble"},
    sample_size=200,
    metrics=["detection_rate", "false_positive_rate", "detection_latency_steps"],
    expected_results={
        "detection_rate": 0.9,
        "false_positive_rate": 0.05,
    },
)

# E3: Skill Trust Score Calibration
E3 = ExperimentDefinition(
    experiment_id="E3",
    title="Skill Trust Score Calibration",
    description="Evaluates the calibration of skill trust scores against actual outcomes.",
    hypothesis="Calibrated trust scores predict skill success with AUC > 0.85.",
    independent_variables=["trust_score_method"],
    dependent_variables=["calibration_auc", "trust_score_accuracy"],
    control_conditions={"trust_score_method": "uniform"},
    treatment_conditions={"trust_score_method": "phoenix_calibrated"},
    sample_size=150,
    metrics=["calibration_auc", "brier_score", "expected_calibration_error"],
    expected_results={
        "calibration_auc": 0.85,
        "brier_score": 0.1,
    },
)

# E4: Multi-Agent Collaboration Efficiency
E4 = ExperimentDefinition(
    experiment_id="E4",
    title="Multi-Agent Collaboration Efficiency",
    description="Measures the efficiency gains from Phoenix multi-agent collaboration.",
    hypothesis="Multi-agent collaboration with Phoenix protocol completes tasks 30% faster than single-agent.",
    independent_variables=["agent_configuration"],
    dependent_variables=["task_completion_time", "task_quality_score"],
    control_conditions={"agent_configuration": "single_agent"},
    treatment_conditions={"agent_configuration": "multi_agent_phoenix"},
    sample_size=80,
    metrics=["task_completion_time", "task_quality_score", "communication_overhead"],
    expected_results={
        "time_reduction": 0.3,
        "quality_maintained": 0.95,
    },
)

# E5: Self-Repair Effectiveness
E5 = ExperimentDefinition(
    experiment_id="E5",
    title="Self-Repair Effectiveness",
    description="Evaluates the effectiveness of Phoenix self-repair mechanisms.",
    hypothesis="Self-repair recovers from 80% of degradation incidents without human intervention.",
    independent_variables=["self_repair_enabled"],
    dependent_variables=["recovery_rate", "recovery_time", "system_uptime"],
    control_conditions={"self_repair_enabled": False},
    treatment_conditions={"self_repair_enabled": True},
    sample_size=60,
    metrics=["recovery_rate", "mean_time_to_recovery", "system_uptime_percentage"],
    expected_results={
        "recovery_rate": 0.8,
        "mean_time_to_recovery_seconds": 300,
    },
)

# E6: End-to-End Phoenix System
E6 = ExperimentDefinition(
    experiment_id="E6",
    title="End-to-End Phoenix System Evaluation",
    description="Comprehensive evaluation of the complete Phoenix system.",
    hypothesis="The full Phoenix system achieves >40% safety improvement with <10% task completion overhead.",
    independent_variables=["system_configuration"],
    dependent_variables=["safety_score", "task_completion_rate", "latency_overhead"],
    control_conditions={"system_configuration": "vanilla"},
    treatment_conditions={"system_configuration": "phoenix_full"},
    sample_size=200,
    metrics=[
        "safety_score", "task_completion_rate", "latency_overhead",
        "drift_detection_accuracy", "trust_calibration_auc",
        "self_repair_recovery_rate",
    ],
    expected_results={
        "safety_improvement": 0.4,
        "task_completion_overhead": 0.1,
    },
)

ALL_EXPERIMENTS = {
    "E1": E1,
    "E2": E2,
    "E3": E3,
    "E4": E4,
    "E5": E5,
    "E6": E6,
}
