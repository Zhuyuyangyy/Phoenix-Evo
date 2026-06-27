"""Case study analyzer for Phoenix paper experiments."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any


@dataclass
class CaseStudy:
    """A case study for qualitative analysis."""
    case_id: str
    title: str
    description: str
    scenario: dict[str, Any]
    expected_behavior: str
    actual_behavior: str = ""
    analysis: dict[str, Any] = field(default_factory=dict)
    lessons_learned: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class CaseStudyResult:
    """Result from analyzing a case study."""
    case_id: str
    findings: list[str]
    safety_implications: list[str]
    recommendations: list[str]
    severity: str  # "low", "medium", "high", "critical"
    confidence: float
    metadata: dict[str, Any] = field(default_factory=dict)


class CaseStudyAnalyzer:
    """Analyzes case studies for the Phoenix paper.

    Provides qualitative analysis of specific scenarios
    to complement quantitative experiments.
    """

    def __init__(self):
        self._cases: dict[str, CaseStudy] = {}
        self._results: dict[str, CaseStudyResult] = {}

    def create_case(
        self,
        title: str,
        description: str,
        scenario: dict[str, Any],
        expected_behavior: str,
    ) -> CaseStudy:
        """Create a new case study."""
        case_id = f"case_{uuid.uuid4().hex[:8]}"
        case = CaseStudy(
            case_id=case_id,
            title=title,
            description=description,
            scenario=scenario,
            expected_behavior=expected_behavior,
        )
        self._cases[case_id] = case
        return case

    def analyze(self, case: CaseStudy) -> CaseStudyResult:
        """Analyze a case study."""
        findings = []
        safety_implications = []
        recommendations = []

        # Analyze scenario
        scenario = case.scenario

        # Check for safety-related aspects
        if scenario.get("risk_level") in ("high", "critical"):
            findings.append(f"High-risk scenario detected: {scenario.get('risk_level')}")
            safety_implications.append("Requires enhanced safety monitoring")

        if scenario.get("tool_access") == "unrestricted":
            findings.append("Unrestricted tool access in scenario")
            safety_implications.append("Potential for unsafe tool usage")
            recommendations.append("Implement tool access restrictions")

        # Check actual vs expected behavior
        if case.actual_behavior and case.actual_behavior != case.expected_behavior:
            findings.append(f"Behavior deviation: expected '{case.expected_behavior}', got '{case.actual_behavior}'")
            safety_implications.append("Unexpected behavior may indicate safety gap")

        # Determine severity
        severity = scenario.get("risk_level", "low")
        if severity not in ("low", "medium", "high", "critical"):
            severity = "medium"

        # Compute confidence
        confidence = 0.8 if case.actual_behavior else 0.5

        result = CaseStudyResult(
            case_id=case.case_id,
            findings=findings,
            safety_implications=safety_implications,
            recommendations=recommendations,
            severity=severity,
            confidence=confidence,
        )
        self._results[case.case_id] = result
        return result

    def get_case(self, case_id: str) -> CaseStudy | None:
        """Get a case study by ID."""
        return self._cases.get(case_id)

    def get_result(self, case_id: str) -> CaseStudyResult | None:
        """Get the analysis result for a case."""
        return self._results.get(case_id)

    def list_cases(self) -> list[dict[str, Any]]:
        """List all case studies."""
        return [
            {
                "case_id": c.case_id,
                "title": c.title,
                "severity": c.scenario.get("risk_level", "unknown"),
                "analyzed": c.case_id in self._results,
            }
            for c in self._cases.values()
        ]

    def generate_summary(self) -> dict[str, Any]:
        """Generate a summary of all case studies."""
        severity_counts = {}
        for result in self._results.values():
            severity_counts[result.severity] = severity_counts.get(result.severity, 0) + 1

        all_findings = []
        all_recommendations = []
        for result in self._results.values():
            all_findings.extend(result.findings)
            all_recommendations.extend(result.recommendations)

        return {
            "total_cases": len(self._cases),
            "analyzed_cases": len(self._results),
            "by_severity": severity_counts,
            "total_findings": len(all_findings),
            "total_recommendations": len(all_recommendations),
            "unique_findings": len(set(all_findings)),
        }
