"""Replay orchestrator for Phoenix-Evo regression testing."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from .replay_case_generator import ReplayCase, ReplayCaseType


@dataclass
class ReplaySuiteResult:
    """Result of running a full replay suite."""
    suite_id: str
    total_cases: int
    passed: int
    failed: int
    skipped: int
    results: List[Dict[str, Any]] = field(default_factory=list)
    duration_seconds: float = 0.0
    summary: Dict[str, Any] = field(default_factory=dict)

    @property
    def pass_rate(self) -> float:
        if self.total_cases == 0:
            return 0.0
        return self.passed / self.total_cases


class ReplayOrchestrator:
    """Orchestrates the execution of replay test suites.

    Manages the lifecycle of replay testing: loading cases,
    executing them against the current system, and collecting results.
    """

    def __init__(
        self,
        executor: Optional[Callable[[ReplayCase], Dict[str, Any]]] = None,
    ):
        self._executor = executor or self._default_executor
        self._results: List[Dict[str, Any]] = []

    def _default_executor(self, case: ReplayCase) -> Dict[str, Any]:
        """Default executor that validates case structure."""
        result = {
            "case_id": case.case_id,
            "case_type": case.case_type.value,
            "status": "passed",
            "details": {},
        }

        # Basic validation
        if not case.original_trajectory:
            result["status"] = "failed"
            result["details"]["reason"] = "Empty trajectory"
            return result

        events = case.original_trajectory.get("events", [])
        if case.case_type == ReplayCaseType.POSITIVE:
            if case.original_trajectory.get("success") != case.expected_outcome.get("success"):
                result["status"] = "failed"
                result["details"]["reason"] = "Outcome mismatch"

        elif case.case_type == ReplayCaseType.NEGATIVE:
            # Negative cases should have perturbations
            if not case.perturbations:
                result["status"] = "skipped"
                result["details"]["reason"] = "No perturbations defined"

        elif case.case_type == ReplayCaseType.EDGE:
            if not case.perturbations:
                result["status"] = "skipped"
                result["details"]["reason"] = "No edge conditions defined"

        elif case.case_type == ReplayCaseType.REGRESSION:
            # Regression cases verify previously fixed bugs
            pass

        return result

    def run_case(self, case: ReplayCase) -> Dict[str, Any]:
        """Run a single replay case."""
        return self._executor(case)

    def run_suite(
        self,
        cases: List[ReplayCase],
        suite_id: Optional[str] = None,
        stop_on_failure: bool = False,
    ) -> ReplaySuiteResult:
        """Run a full suite of replay cases."""
        import uuid
        if suite_id is None:
            suite_id = str(uuid.uuid4())[:8]

        start_time = time.time()
        results = []
        passed = 0
        failed = 0
        skipped = 0

        for case in cases:
            result = self.run_case(case)
            results.append(result)

            status = result.get("status", "failed")
            if status == "passed":
                passed += 1
            elif status == "skipped":
                skipped += 1
            else:
                failed += 1
                if stop_on_failure:
                    break

        duration = time.time() - start_time

        # Build summary by case type
        summary: Dict[str, Any] = {}
        for result in results:
            ct = result.get("case_type", "unknown")
            summary.setdefault(ct, {"passed": 0, "failed": 0, "skipped": 0})
            status = result.get("status", "failed")
            summary[ct][status] = summary[ct].get(status, 0) + 1

        return ReplaySuiteResult(
            suite_id=suite_id,
            total_cases=len(cases),
            passed=passed,
            failed=failed,
            skipped=skipped,
            results=results,
            duration_seconds=duration,
            summary=summary,
        )

    def run_regression_suite(
        self,
        cases: List[ReplayCase],
    ) -> ReplaySuiteResult:
        """Run only regression cases from a suite."""
        regression_cases = [
            c for c in cases if c.case_type == ReplayCaseType.REGRESSION
        ]
        return self.run_suite(regression_cases, suite_id="regression")
