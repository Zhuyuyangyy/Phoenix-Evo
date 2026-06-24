"""Replay framework with scheduling and CI integration for Phoenix-Evo."""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from .replay_case_generator import ReplayCase, ReplayCaseGenerator, ReplayCaseType
from .replay_orchestrator import ReplayOrchestrator, ReplaySuiteResult
from .replay_comparator import ReplayComparator, ComparisonResult
from .replay_report import ReplayReportGenerator


@dataclass
class ReplaySchedule:
    """Schedule for periodic replay testing."""
    schedule_id: str
    cases: List[ReplayCase]
    interval_seconds: float = 3600.0  # Default: hourly
    last_run: Optional[float] = None
    enabled: bool = True
    stop_on_failure: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)


class ReplayFramework:
    """Main framework class that ties together all replay components."""

    def __init__(
        self,
        generator: Optional[ReplayCaseGenerator] = None,
        orchestrator: Optional[ReplayOrchestrator] = None,
        comparator: Optional[ReplayComparator] = None,
        reporter: Optional[ReplayReportGenerator] = None,
    ):
        self.generator = generator or ReplayCaseGenerator()
        self.orchestrator = orchestrator or ReplayOrchestrator()
        self.comparator = comparator or ReplayComparator()
        self.reporter = reporter or ReplayReportGenerator()
        self._schedules: Dict[str, ReplaySchedule] = {}

    def create_schedule(
        self,
        cases: List[ReplayCase],
        interval_seconds: float = 3600.0,
        schedule_id: Optional[str] = None,
    ) -> ReplaySchedule:
        """Create a new replay schedule."""
        import uuid
        if schedule_id is None:
            schedule_id = str(uuid.uuid4())[:8]
        schedule = ReplaySchedule(
            schedule_id=schedule_id,
            cases=cases,
            interval_seconds=interval_seconds,
        )
        self._schedules[schedule_id] = schedule
        return schedule

    def run_schedule(self, schedule_id: str) -> Optional[ReplaySuiteResult]:
        """Run a specific schedule if it's due."""
        schedule = self._schedules.get(schedule_id)
        if not schedule or not schedule.enabled:
            return None

        now = time.time()
        if schedule.last_run and (now - schedule.last_run) < schedule.interval_seconds:
            return None

        result = self.orchestrator.run_suite(
            schedule.cases,
            suite_id=schedule_id,
            stop_on_failure=schedule.stop_on_failure,
        )
        schedule.last_run = now
        return result

    def run_all_schedules(self) -> List[ReplaySuiteResult]:
        """Run all due schedules."""
        results = []
        for schedule_id in list(self._schedules.keys()):
            result = self.run_schedule(schedule_id)
            if result:
                results.append(result)
        return results

    def compare_trajectories(
        self,
        actual: Dict[str, Any],
        expected: Dict[str, Any],
        case_id: str = "",
    ) -> ComparisonResult:
        """Compare two trajectories."""
        return self.comparator.compare(actual, expected, case_id)

    def generate_and_run(
        self,
        trajectories: List[Dict[str, Any]],
        n_positive: int = 5,
        n_negative: int = 3,
        n_edge: int = 2,
        n_regression: int = 2,
    ) -> ReplaySuiteResult:
        """Generate cases and run them in one step."""
        cases = self.generator.generate_suite(
            trajectories,
            n_positive=n_positive,
            n_negative=n_negative,
            n_edge=n_edge,
            n_regression=n_regression,
        )
        return self.orchestrator.run_suite(cases)


class ReplayScheduler:
    """Scheduler for periodic replay execution."""

    def __init__(self, framework: Optional[ReplayFramework] = None):
        self.framework = framework or ReplayFramework()
        self._running = False

    def add_schedule(self, schedule: ReplaySchedule) -> None:
        """Add a schedule to the framework."""
        self.framework._schedules[schedule.schedule_id] = schedule

    def remove_schedule(self, schedule_id: str) -> bool:
        """Remove a schedule."""
        if schedule_id in self.framework._schedules:
            del self.framework._schedules[schedule_id]
            return True
        return False

    def list_schedules(self) -> List[Dict[str, Any]]:
        """List all schedules."""
        schedules = []
        for sid, schedule in self.framework._schedules.items():
            schedules.append({
                "schedule_id": sid,
                "n_cases": len(schedule.cases),
                "interval_seconds": schedule.interval_seconds,
                "enabled": schedule.enabled,
                "last_run": schedule.last_run,
            })
        return schedules

    def tick(self) -> List[ReplaySuiteResult]:
        """Execute all due schedules (call this periodically)."""
        return self.framework.run_all_schedules()


class ReplayCI:
    """CI integration for replay testing."""

    def __init__(
        self,
        framework: Optional[ReplayFramework] = None,
        fail_on_regression: bool = True,
        output_dir: str = "replay_results",
    ):
        self.framework = framework or ReplayFramework()
        self.fail_on_regression = fail_on_regression
        self.output_dir = output_dir

    def run(self, trajectories: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Run replay CI check.

        Returns a CI result dict with pass/fail status.
        """
        os.makedirs(self.output_dir, exist_ok=True)

        # Generate and run suite
        suite_result = self.framework.generate_and_run(trajectories)

        # Generate report
        report = self.framework.reporter.generate_suite_report(suite_result)

        # Save report
        report_path = os.path.join(self.output_dir, f"ci_{suite_result.suite_id}.json")
        with open(report_path, "w") as f:
            json.dump(report, f, indent=2, default=str)

        # Determine CI result
        ci_result = {
            "passed": suite_result.failed == 0,
            "suite_id": suite_result.suite_id,
            "total_cases": suite_result.total_cases,
            "passed_cases": suite_result.passed,
            "failed_cases": suite_result.failed,
            "pass_rate": suite_result.pass_rate,
            "report_path": report_path,
        }

        # Check for regressions specifically
        if self.fail_on_regression:
            regression_result = self.framework.orchestrator.run_regression_suite(
                self.framework.generator.generate_suite(trajectories, n_regression=5)
            )
            if regression_result.failed > 0:
                ci_result["passed"] = False
                ci_result["regression_failures"] = regression_result.failed

        return ci_result
