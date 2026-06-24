"""Tests for replay v2 (case generator, orchestrator, comparator, report)."""


from core.replay.replay_case_generator import (
    ReplayCase,
    ReplayCaseGenerator,
    ReplayCaseType,
)
from core.replay.replay_comparator import ComparisonResult, ReplayComparator
from core.replay.replay_orchestrator import ReplayOrchestrator, ReplaySuiteResult
from core.replay.replay_report import ReplayReportGenerator


class TestReplayCaseType:
    def test_all_types(self):
        assert ReplayCaseType.POSITIVE.value == "positive"
        assert ReplayCaseType.NEGATIVE.value == "negative"
        assert ReplayCaseType.EDGE.value == "edge"
        assert ReplayCaseType.REGRESSION.value == "regression"


class TestReplayCase:
    def test_to_dict(self):
        case = ReplayCase(
            case_id="c1",
            case_type=ReplayCaseType.POSITIVE,
            task_description="test",
            original_trajectory={"success": True},
            expected_outcome={"success": True},
        )
        d = case.to_dict()
        assert d["case_type"] == "positive"
        assert d["case_id"] == "c1"

    def test_from_dict(self):
        d = {
            "case_id": "c2",
            "case_type": "negative",
            "task_description": "test",
            "original_trajectory": {},
            "expected_outcome": {},
        }
        case = ReplayCase.from_dict(d)
        assert case.case_type == ReplayCaseType.NEGATIVE


class TestReplayCaseGenerator:
    def test_generate_positive(self):
        gen = ReplayCaseGenerator()
        case = gen.generate_positive_case({"success": True, "events": []})
        assert case.case_type == ReplayCaseType.POSITIVE
        assert case.original_trajectory["success"] is True

    def test_generate_negative(self):
        gen = ReplayCaseGenerator()
        case = gen.generate_negative_case({"success": True, "events": [{"event_type": "tool_result", "tool_result_summary": "ok"}]})
        assert case.case_type == ReplayCaseType.NEGATIVE
        assert len(case.perturbations) > 0

    def test_generate_edge(self):
        gen = ReplayCaseGenerator()
        case = gen.generate_edge_case({"success": True, "events": []})
        assert case.case_type == ReplayCaseType.EDGE
        assert len(case.perturbations) > 0

    def test_generate_regression(self):
        gen = ReplayCaseGenerator()
        case = gen.generate_regression_case({"success": True, "events": []})
        assert case.case_type == ReplayCaseType.REGRESSION

    def test_generate_suite(self):
        gen = ReplayCaseGenerator()
        cases = gen.generate_suite(
            [{"success": True, "events": []}],
            n_positive=3, n_negative=2, n_edge=2, n_regression=2,
        )
        assert len(cases) == 9
        types = [c.case_type for c in cases]
        assert types.count(ReplayCaseType.POSITIVE) == 3
        assert types.count(ReplayCaseType.NEGATIVE) == 2

    def test_generate_suite_empty(self):
        gen = ReplayCaseGenerator()
        cases = gen.generate_suite([])
        assert cases == []

    def test_case_ids_unique(self):
        gen = ReplayCaseGenerator()
        cases = gen.generate_suite([{"success": True, "events": []}] * 5)
        ids = [c.case_id for c in cases]
        assert len(ids) == len(set(ids))


class TestReplayOrchestrator:
    def test_run_single_case(self):
        orch = ReplayOrchestrator()
        case = ReplayCase(
            case_id="c1",
            case_type=ReplayCaseType.POSITIVE,
            task_description="test",
            original_trajectory={"success": True, "events": []},
            expected_outcome={"success": True},
        )
        result = orch.run_case(case)
        assert result["case_id"] == "c1"

    def test_run_suite(self):
        orch = ReplayOrchestrator()
        gen = ReplayCaseGenerator()
        cases = gen.generate_suite(
            [{"success": True, "events": []}],
            n_positive=3, n_negative=2, n_edge=0, n_regression=0,
        )
        result = orch.run_suite(cases)
        assert result.total_cases == 5
        assert result.passed + result.failed + result.skipped == 5

    def test_pass_rate(self):
        result = ReplaySuiteResult(
            suite_id="s1", total_cases=10, passed=8, failed=2, skipped=0
        )
        assert result.pass_rate == 0.8

    def test_pass_rate_zero(self):
        result = ReplaySuiteResult(
            suite_id="s2", total_cases=0, passed=0, failed=0, skipped=0
        )
        assert result.pass_rate == 0.0

    def test_stop_on_failure(self):
        orch = ReplayOrchestrator()
        gen = ReplayCaseGenerator()
        cases = gen.generate_suite(
            [{"success": False, "events": []}],
            n_positive=5, n_negative=0, n_edge=0, n_regression=0,
        )
        result = orch.run_suite(cases, stop_on_failure=True)
        assert result.total_cases <= len(cases)


class TestReplayComparator:
    def test_matching_trajectories(self):
        comp = ReplayComparator()
        result = comp.compare(
            {"success": True, "events": []},
            {"success": True, "events": []},
            case_id="c1",
        )
        assert result.match is True
        assert result.similarity_score == 1.0

    def test_different_trajectories(self):
        comp = ReplayComparator()
        result = comp.compare(
            {"success": True, "events": []},
            {"success": False, "events": []},
            case_id="c2",
        )
        assert result.match is False
        assert len(result.critical_differences) > 0

    def test_safety_critical_comparison(self):
        comp = ReplayComparator()
        result = comp.compare_safety_critical(
            {"success": True, "events": [{"event_type": "risk_signal", "risk_signal": "high"}]},
            {"success": True, "safety_violations": 0},
            case_id="c3",
        )
        assert isinstance(result, ComparisonResult)

    def test_trajectory_hash(self):
        traj = {"success": True, "events": []}
        h1 = ReplayComparator.trajectory_hash(traj)
        h2 = ReplayComparator.trajectory_hash(traj)
        assert h1 == h2
        assert len(h1) == 16


class TestReplayReportGenerator:
    def test_suite_report(self):
        gen = ReplayReportGenerator()
        result = ReplaySuiteResult(
            suite_id="s1", total_cases=5, passed=4, failed=1, skipped=0
        )
        report = gen.generate_suite_report(result)
        assert report["summary"]["total_cases"] == 5
        assert report["summary"]["pass_rate"] == 0.8

    def test_comparison_report(self):
        gen = ReplayReportGenerator()
        comparisons = [
            ComparisonResult(case_id="c1", match=True, similarity_score=1.0, differences=[]),
            ComparisonResult(case_id="c2", match=False, similarity_score=0.5, differences=[{"field": "x"}]),
        ]
        report = gen.generate_comparison_report(comparisons)
        assert report["summary"]["matches"] == 1
        assert report["summary"]["mismatches"] == 1

    def test_format_report(self):
        gen = ReplayReportGenerator()
        result = ReplaySuiteResult(
            suite_id="s1", total_cases=3, passed=3, failed=0, skipped=0
        )
        report = gen.generate_suite_report(result)
        formatted = gen.format_report(report)
        assert "Replay Report" in formatted
        assert "total_cases" in formatted
