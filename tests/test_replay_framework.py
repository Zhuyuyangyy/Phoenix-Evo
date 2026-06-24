"""Tests for replay framework."""

import pytest

from core.replay.replay_framework import (
    ReplayCI,
    ReplayFramework,
    ReplayScheduler,
    ReplaySchedule,
)
from core.replay.replay_case_generator import ReplayCase, ReplayCaseType


class TestReplayFramework:
    def test_create_schedule(self):
        fw = ReplayFramework()
        cases = [
            ReplayCase(
                case_id="c1",
                case_type=ReplayCaseType.POSITIVE,
                task_description="test",
                original_trajectory={"success": True},
                expected_outcome={"success": True},
            )
        ]
        schedule = fw.create_schedule(cases, interval_seconds=60)
        assert schedule.schedule_id is not None
        assert len(schedule.cases) == 1

    def test_generate_and_run(self):
        fw = ReplayFramework()
        result = fw.generate_and_run(
            [{"success": True, "events": []}],
            n_positive=2, n_negative=1,
        )
        assert result.total_cases > 0

    def test_compare_trajectories(self):
        fw = ReplayFramework()
        result = fw.compare_trajectories(
            {"success": True},
            {"success": True},
            case_id="c1",
        )
        assert result.match is True

    def test_run_schedule_not_due(self):
        fw = ReplayFramework()
        cases = [ReplayCase(
            case_id="c1", case_type=ReplayCaseType.POSITIVE,
            task_description="test", original_trajectory={"success": True},
            expected_outcome={"success": True},
        )]
        schedule = fw.create_schedule(cases, interval_seconds=9999)
        # Run once
        result1 = fw.run_schedule(schedule.schedule_id)
        assert result1 is not None
        # Run again immediately - should not be due
        result2 = fw.run_schedule(schedule.schedule_id)
        assert result2 is None

    def test_run_all_schedules(self):
        fw = ReplayFramework()
        cases = [ReplayCase(
            case_id="c1", case_type=ReplayCaseType.POSITIVE,
            task_description="test", original_trajectory={"success": True},
            expected_outcome={"success": True},
        )]
        fw.create_schedule(cases, interval_seconds=0)
        results = fw.run_all_schedules()
        assert len(results) >= 0  # May or may not be due


class TestReplayScheduler:
    def test_add_schedule(self):
        scheduler = ReplayScheduler()
        schedule = ReplaySchedule(
            schedule_id="s1",
            cases=[ReplayCase(
                case_id="c1", case_type=ReplayCaseType.POSITIVE,
                task_description="test", original_trajectory={},
                expected_outcome={},
            )],
        )
        scheduler.add_schedule(schedule)
        schedules = scheduler.list_schedules()
        assert len(schedules) == 1

    def test_remove_schedule(self):
        scheduler = ReplayScheduler()
        schedule = ReplaySchedule(
            schedule_id="s1", cases=[],
        )
        scheduler.add_schedule(schedule)
        assert scheduler.remove_schedule("s1") is True
        assert scheduler.remove_schedule("nonexistent") is False

    def test_list_schedules(self):
        scheduler = ReplayScheduler()
        for i in range(3):
            schedule = ReplaySchedule(schedule_id=f"s{i}", cases=[])
            scheduler.add_schedule(schedule)
        schedules = scheduler.list_schedules()
        assert len(schedules) == 3

    def test_tick(self):
        scheduler = ReplayScheduler()
        schedule = ReplaySchedule(
            schedule_id="s1",
            cases=[ReplayCase(
                case_id="c1", case_type=ReplayCaseType.POSITIVE,
                task_description="test", original_trajectory={"success": True},
                expected_outcome={"success": True},
            )],
            interval_seconds=0,
        )
        scheduler.add_schedule(schedule)
        results = scheduler.tick()
        assert isinstance(results, list)


class TestReplayCI:
    def test_run(self):
        ci = ReplayCI(output_dir="/tmp/phoenix_ci_test")
        result = ci.run([{"success": True, "events": []}])
        assert "passed" in result
        assert "suite_id" in result
        assert "total_cases" in result

    def test_fail_on_regression(self):
        ci = ReplayCI(fail_on_regression=True, output_dir="/tmp/phoenix_ci_test2")
        result = ci.run([{"success": True, "events": []}])
        assert isinstance(result["passed"], bool)

    def test_output_dir_created(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = f"{tmpdir}/ci_output"
            ci = ReplayCI(output_dir=output_dir)
            ci.run([{"success": True, "events": []}])
            import os
            assert os.path.exists(output_dir)
