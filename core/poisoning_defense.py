"""Poisoning defense mechanisms for Phoenix-Evo."""

from __future__ import annotations

import hashlib
import re
import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple


class PoisonType(Enum):
    DATA_POISONING = "data_poisoning"
    PROMPT_INJECTION = "prompt_injection"
    TRAJECTORY_MANIPULATION = "trajectory_manipulation"
    SKILL_POISONING = "skill_poisoning"
    FEEDBACK_MANIPULATION = "feedback_manipulation"
    CONTEXT_INJECTION = "context_injection"


class DefenseLayer(Enum):
    INPUT_VALIDATION = "input_validation"
    TRAJECTORY_MONITORING = "trajectory_monitoring"
    CONSISTENCY_CHECKING = "consistency_checking"
    ANOMALY_DETECTION = "anomaly_detection"
    OUTPUT_FILTERING = "output_filtering"
    FEEDBACK_VALIDATION = "feedback_validation"


@dataclass
class PoisoningThreatModel:
    """Models a specific poisoning threat."""
    threat_id: str
    poison_type: PoisonType
    attack_vector: str
    target_component: str
    severity: float  # 0.0 to 1.0
    likelihood: float  # 0.0 to 1.0
    affected_layers: List[DefenseLayer] = field(default_factory=list)
    mitigations: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def risk_score(self) -> float:
        return self.severity * self.likelihood


class TrajectoryConsistencyChecker:
    """Checks trajectory consistency to detect manipulation."""

    def __init__(
        self,
        max_tool_result_divergence: float = 0.5,
        max_step_time_variance: float = 10.0,
    ):
        self.max_tool_result_divergence = max_tool_result_divergence
        self.max_step_time_variance = max_step_time_variance

    def check_consistency(self, trajectory: Dict[str, Any]) -> Dict[str, Any]:
        """Check a trajectory for consistency anomalies."""
        events = trajectory.get("events", [])
        issues = []

        # Check for temporal anomalies
        timestamps = [e.get("timestamp", 0) for e in events if e.get("timestamp")]
        if len(timestamps) >= 2:
            deltas = [timestamps[i+1] - timestamps[i] for i in range(len(timestamps)-1)]
            if deltas:
                mean_delta = sum(deltas) / len(deltas)
                for i, delta in enumerate(deltas):
                    if mean_delta > 0 and abs(delta - mean_delta) / mean_delta > self.max_step_time_variance:
                        issues.append({
                            "type": "temporal_anomaly",
                            "step": i,
                            "delta": delta,
                            "expected": mean_delta,
                        })

        # Check for tool result inconsistencies
        for i, event in enumerate(events):
            if event.get("event_type") == "tool_result":
                result = event.get("tool_result_summary", "")
                if result and self._looks_tampered(result):
                    issues.append({
                        "type": "potential_tampering",
                        "step": i,
                        "evidence": "Result contains suspicious patterns",
                    })

        # Check for missing verification steps
        has_tool_calls = any(e.get("event_type") == "tool_call" for e in events)
        has_verification = any(e.get("event_type") == "verification" for e in events)
        if has_tool_calls and not has_verification:
            issues.append({
                "type": "missing_verification",
                "description": "Tool calls present but no verification steps",
            })

        return {
            "consistent": len(issues) == 0,
            "issues": issues,
            "consistency_score": max(0.0, 1.0 - len(issues) * 0.2),
        }

    def _looks_tampered(self, result: str) -> bool:
        """Heuristic check for tampered tool results."""
        tamper_indicators = [
            "all checks passed",
            "no issues found",
            "completely safe",
            "verified: safe",
        ]
        result_lower = result.lower()
        return any(ind in result_lower for ind in tamper_indicators)


class PromptInjectionDetector:
    """Detects prompt injection attempts in inputs."""

    INJECTION_PATTERNS = [
        (r'ignore\s+(?:previous|above|all)\s+instructions?', "instruction_override"),
        (r'you\s+are\s+now\s+(?:a|an)\s+', "role_change"),
        (r'system\s*:\s*', "system_prompt_leak"),
        (r'(?:print|show|reveal|display)\s+(?:your|the|system)\s+(?:prompt|instructions?)', "prompt_extraction"),
        (r'</?(?:system|user|assistant|im_start|im_end)>', "token_injection"),
        (r'```(?:system|admin)', "code_block_injection"),
        (r'forget\s+(?:everything|all|previous)', "memory_wipe"),
        (r'new\s+instructions?\s*:', "instruction_replacement"),
        (r'(?:sudo|admin|root)\s+mode', "privilege_escalation"),
        (r'jailbreak', "explicit_jailbreak"),
    ]

    def __init__(self, sensitivity: float = 0.7):
        self.sensitivity = sensitivity

    def detect(self, text: str) -> Dict[str, Any]:
        """Detect prompt injection in text."""
        detections = []
        for pattern, injection_type in self.INJECTION_PATTERNS:
            matches = re.findall(pattern, text, re.IGNORECASE)
            if matches:
                detections.append({
                    "type": injection_type,
                    "pattern": pattern,
                    "matches": matches,
                    "confidence": min(len(matches) * 0.3 + 0.4, 1.0),
                })

        max_confidence = max((d["confidence"] for d in detections), default=0.0)
        is_injection = max_confidence >= self.sensitivity

        return {
            "is_injection": is_injection,
            "confidence": max_confidence,
            "detections": detections,
            "n_detections": len(detections),
        }


class PoisoningDefenseOrchestrator:
    """Orchestrates all poisoning defense layers."""

    def __init__(
        self,
        consistency_checker: Optional[TrajectoryConsistencyChecker] = None,
        injection_detector: Optional[PromptInjectionDetector] = None,
    ):
        self.consistency_checker = consistency_checker or TrajectoryConsistencyChecker()
        self.injection_detector = injection_detector or PromptInjectionDetector()
        self._threat_models: Dict[str, PoisoningThreatModel] = {}
        self._defense_log: List[Dict[str, Any]] = []

    def register_threat_model(self, threat: PoisoningThreatModel) -> None:
        """Register a threat model."""
        self._threat_models[threat.threat_id] = threat

    def analyze_input(self, text: str) -> Dict[str, Any]:
        """Analyze input for poisoning threats."""
        injection_result = self.injection_detector.detect(text)

        result = {
            "safe": not injection_result["is_injection"],
            "injection_analysis": injection_result,
            "threats_detected": [],
        }

        if injection_result["is_injection"]:
            threat = PoisoningThreatModel(
                threat_id=f"threat_{len(self._threat_models)}",
                poison_type=PoisonType.PROMPT_INJECTION,
                attack_vector="input_text",
                target_component="agent_prompt",
                severity=injection_result["confidence"],
                likelihood=0.8,
                affected_layers=[DefenseLayer.INPUT_VALIDATION],
                mitigations=["block_input", "sanitize_input"],
            )
            result["threats_detected"].append(threat)
            self._defense_log.append({
                "action": "input_blocked",
                "threat_type": "prompt_injection",
                "confidence": injection_result["confidence"],
            })

        return result

    def analyze_trajectory(self, trajectory: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze a trajectory for poisoning/manipulation."""
        consistency_result = self.consistency_checker.check_consistency(trajectory)

        result = {
            "safe": consistency_result["consistent"],
            "consistency_analysis": consistency_result,
            "threats_detected": [],
        }

        if not consistency_result["consistent"]:
            for issue in consistency_result["issues"]:
                threat = PoisoningThreatModel(
                    threat_id=f"threat_{len(self._threat_models) + len(result['threats_detected'])}",
                    poison_type=PoisonType.TRAJECTORY_MANIPULATION,
                    attack_vector=issue["type"],
                    target_component="trajectory",
                    severity=0.7,
                    likelihood=0.6,
                    affected_layers=[DefenseLayer.TRAJECTORY_MONITORING],
                    mitigations=["flag_for_review", "replay_verification"],
                )
                result["threats_detected"].append(threat)

        return result

    def get_defense_summary(self) -> Dict[str, Any]:
        """Get a summary of defense actions taken."""
        return {
            "total_threats_registered": len(self._threat_models),
            "total_defense_actions": len(self._defense_log),
            "recent_actions": self._defense_log[-10:],
        }
