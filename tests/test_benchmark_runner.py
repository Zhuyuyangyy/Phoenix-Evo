"""Tests for BenchmarkMetrics and BenchmarkRunner."""

import os
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from core.benchmark_metrics import BenchmarkMetrics, MetricResult

# ── BenchmarkMetrics tests ──────────────────────────────────

def test_metrics_empty_results():
    """Empty run results should return zero metrics."""
    m = BenchmarkMetrics()
    result = m.compute([])
    assert result.task_success_rate == 0.0
    assert result.skill_reuse_rate == 0.0
    assert result.risk_blocking_rate == 0.0
    assert result.regression_rate == 0.0
    assert result.duplicate_skill_rate == 0.0
    assert result.avg_repair_steps == 0.0
    assert result.evidence_coverage == 0.0


def test_metrics_all_success():
    """All successful runs should yield high metrics."""
    m = BenchmarkMetrics()
    runs = [
        {
            "case_id": f"CASE-{i:03d}",
            "task_success": True,
            "skill_extracted": True,
            "skill_duplicate": False,
            "risk_blocked": False,
            "regression": False,
            "repair_steps": 2,
            "has_evidence": True,
        }
        for i in range(1, 6)
    ]
    result = m.compute(runs)
    assert result.task_success_rate == 1.0
    assert result.skill_reuse_rate == 1.0
    assert result.risk_blocking_rate == 0.0
    assert result.regression_rate == 0.0
    assert result.duplicate_skill_rate == 0.0
    assert result.avg_repair_steps == 2.0
    assert result.evidence_coverage == 1.0


def test_metrics_mixed_results():
    """Mixed results should compute correct averages."""
    m = BenchmarkMetrics()
    runs = [
        {"case_id": "CASE-001", "task_success": True,  "skill_extracted": True,  "skill_duplicate": False, "risk_blocked": False, "regression": False, "repair_steps": 2, "has_evidence": True},
        {"case_id": "CASE-002", "task_success": True,  "skill_extracted": True,  "skill_duplicate": True,  "risk_blocked": False, "regression": False, "repair_steps": 3, "has_evidence": True},
        {"case_id": "CASE-003", "task_success": False, "skill_extracted": False, "skill_duplicate": False, "risk_blocked": True,  "regression": False, "repair_steps": 0, "has_evidence": False},
        {"case_id": "CASE-004", "task_success": True,  "skill_extracted": True,  "skill_duplicate": False, "risk_blocked": False, "regression": True,  "repair_steps": 5, "has_evidence": False},
        {"case_id": "CASE-005", "task_success": True,  "skill_extracted": True,  "skill_duplicate": False, "risk_blocked": False, "regression": False, "repair_steps": 1, "has_evidence": True},
    ]
    result = m.compute(runs)
    assert result.task_success_rate == pytest.approx(0.8)      # 4/5
    assert result.skill_reuse_rate == pytest.approx(1.0)       # 4/4 success
    assert result.risk_blocking_rate == pytest.approx(0.2)     # 1/5
    assert result.regression_rate == pytest.approx(0.25)       # 1/4 extracted
    assert result.duplicate_skill_rate == pytest.approx(0.25)  # 1/4 extracted
    assert result.avg_repair_steps == pytest.approx(2.2)       # (2+3+0+5+1)/5
    assert result.evidence_coverage == pytest.approx(0.75)     # 3/4 extracted


def test_metrics_to_dict():
    """MetricResult.to_dict should exclude details."""
    m = BenchmarkMetrics()
    result = m.compute([{"task_success": True, "skill_extracted": True, "skill_duplicate": False,
                         "risk_blocked": False, "regression": False, "repair_steps": 1, "has_evidence": True}])
    d = result.to_dict()
    assert "details" not in d
    assert "task_success_rate" in d
    assert d["task_success_rate"] == 1.0


# ── PhoenixEvo config tests ────────────────────────────────

def test_phoenix_evo_configured_no_verifier():
    """PhoenixEvo with verifier disabled should skip verification."""
    from core import PhoenixEvo
    tmp = tempfile.mkdtemp(prefix="phoenix_cfg_")
    try:
        evo = PhoenixEvo.create_configured(base_dir=tmp, modules={
            "verifier": False,
            "immune_guard": False,
        })
        evo.run_full_loop(
            task_goal="test configured evo",
            task_type="debugging",
            risk_level="low",
        )
        evo.logger.log_action("read_file", {"path": "/tmp/test.py"}, "OK")
        report = evo.complete_task(success=True, final_output="OK", artifacts=["/tmp/test.py"])

        # With verifier disabled, verification should be skipped
        assert report["verification"] is None or report["verification"]["passed"] is True
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_phoenix_evo_configured_full():
    """PhoenixEvo with all modules enabled should work normally."""
    from core import PhoenixEvo
    tmp = tempfile.mkdtemp(prefix="phoenix_cfg_")
    try:
        evo = PhoenixEvo.create_configured(base_dir=tmp, modules={
            "evaluator": True,
            "miner": True,
            "verifier": True,
            "immune_guard": True,
        })
        evo.run_full_loop(
            task_goal="test full config",
            task_type="debugging",
            risk_level="low",
        )
        evo.logger.log_action("search_files", {"pattern": "test"}, "found")
        evo.logger.log_action("read_file", {"path": "/tmp/test.py"}, "OK")
        evo.logger.log_action("verify", {"path": "/tmp/test.py"}, "OK")
        report = evo.complete_task(success=True, final_output="OK", artifacts=["/tmp/test.py"])

        assert report["evaluation"]["should_extract"] is True
        assert report["verification"]["passed"] is True
        assert report["immune_guard"]["decision"] == "draft"
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ── BenchmarkRunner tests ──────────────────────────────────

def test_runner_group_a_baseline():
    """Group A (baseline) should run all cases with minimal modules."""
    from core.benchmark_runner import BenchmarkRunner, GroupConfig
    tmp = tempfile.mkdtemp(prefix="phoenix_bench_")
    try:
        runner = BenchmarkRunner(base_dir=tmp)
        group = GroupConfig(
            name="A",
            label="baseline",
            modules={"evaluator": True, "miner": True, "verifier": False, "immune_guard": False},
        )
        result = runner.run_group(group, case_ids=["CASE-001", "CASE-003"])
        assert result.total_cases == 2
        assert result.group_name == "A"
        assert len(result.run_results) == 2
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_runner_all_groups():
    """Running all 5 groups should produce 5 results."""
    from core.benchmark_runner import BenchmarkRunner
    tmp = tempfile.mkdtemp(prefix="phoenix_bench_")
    try:
        runner = BenchmarkRunner(base_dir=tmp)
        results = runner.run_all_groups(case_ids=["CASE-001"])
        assert len(results) == 5
        group_names = [r.group_name for r in results]
        assert "A" in group_names
        assert "E" in group_names
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_report_markdown_generation():
    """Report generator should produce valid markdown."""
    from core.benchmark_report import BenchmarkReport
    from core.benchmark_runner import GroupRunResult

    results = [
        GroupRunResult(
            group_name="A", group_label="baseline", total_cases=2,
            metrics=MetricResult(task_success_rate=0.5, skill_reuse_rate=0.5),
        ),
        GroupRunResult(
            group_name="B", group_label="+SkillRetrieval", total_cases=2,
            metrics=MetricResult(task_success_rate=0.75, skill_reuse_rate=0.75),
        ),
    ]

    report = BenchmarkReport()
    md = report.generate_markdown(results)
    assert "Phoenix-Bench V1.1 Report" in md
    assert "Task Success Rate" in md
    assert "50.0%" in md
    assert "75.0%" in md


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
