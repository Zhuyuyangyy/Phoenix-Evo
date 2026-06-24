"""Replay report generator for Phoenix-Evo."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .replay_case_generator import ReplayCase, ReplayCaseType
from .replay_orchestrator import ReplaySuiteResult
from .replay_comparator import ComparisonResult


class ReplayReportGenerator:
    """Generates reports from replay test results."""

    def __init__(self):
        self._reports: List[Dict[str, Any]] = []

    def generate_suite_report(self, suite_result: ReplaySuiteResult) -> Dict[str, Any]:
        """Generate a report for a suite run."""
        report = {
            "report_type": "suite",
            "suite_id": suite_result.suite_id,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "summary": {
                "total_cases": suite_result.total_cases,
                "passed": suite_result.passed,
                "failed": suite_result.failed,
                "skipped": suite_result.skipped,
                "pass_rate": suite_result.pass_rate,
                "duration_seconds": suite_result.duration_seconds,
            },
            "by_case_type": suite_result.summary,
            "failures": [
                r for r in suite_result.results if r.get("status") == "failed"
            ],
        }
        self._reports.append(report)
        return report

    def generate_comparison_report(
        self,
        comparisons: List[ComparisonResult],
    ) -> Dict[str, Any]:
        """Generate a report from comparison results."""
        total = len(comparisons)
        matches = sum(1 for c in comparisons if c.match)
        mismatches = total - matches

        report = {
            "report_type": "comparison",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "summary": {
                "total_comparisons": total,
                "matches": matches,
                "mismatches": mismatches,
                "match_rate": matches / total if total > 0 else 0.0,
            },
            "mismatches_detail": [
                {
                    "case_id": c.case_id,
                    "similarity_score": c.similarity_score,
                    "critical_differences": c.critical_differences,
                    "differences_count": len(c.differences),
                }
                for c in comparisons if not c.match
            ],
        }
        self._reports.append(report)
        return report

    def generate_regression_report(
        self,
        suite_result: ReplaySuiteResult,
    ) -> Dict[str, Any]:
        """Generate a focused regression report."""
        regression_results = [
            r for r in suite_result.results
            if r.get("case_type") == "regression"
        ]
        regression_failures = [
            r for r in regression_results if r.get("status") == "failed"
        ]

        report = {
            "report_type": "regression",
            "suite_id": suite_result.suite_id,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "summary": {
                "regression_cases": len(regression_results),
                "regression_failures": len(regression_failures),
                "regressions_detected": len(regression_failures) > 0,
            },
            "regression_failures": regression_failures,
        }
        self._reports.append(report)
        return report

    def format_report(self, report: Dict[str, Any]) -> str:
        """Format a report as a human-readable string."""
        lines = []
        lines.append("=" * 60)
        lines.append(f"Replay Report: {report.get('report_type', 'unknown')}")
        lines.append("=" * 60)
        lines.append(f"Generated: {report.get('generated_at', 'unknown')}")
        lines.append("")

        summary = report.get("summary", {})
        for key, value in summary.items():
            if isinstance(value, float):
                lines.append(f"  {key}: {value:.4f}")
            else:
                lines.append(f"  {key}: {value}")

        if report.get("failures"):
            lines.append("")
            lines.append("Failures:")
            for failure in report["failures"]:
                lines.append(f"  - {failure.get('case_id', 'unknown')}: {failure.get('details', {})}")

        if report.get("mismatches_detail"):
            lines.append("")
            lines.append("Mismatches:")
            for mm in report["mismatches_detail"]:
                lines.append(f"  - {mm.get('case_id', 'unknown')}: similarity={mm.get('similarity_score', 0):.4f}")

        lines.append("")
        return "\n".join(lines)

    def save_report(self, report: Dict[str, Any], path: str) -> None:
        """Save a report to a JSON file."""
        with open(path, "w") as f:
            json.dump(report, f, indent=2, default=str)
