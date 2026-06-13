"""
Tests for TrajectoryLogger module.
"""

import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from core.trajectory_logger import TrajectoryLogger


class TestTrajectoryLogger:
    """Test suite for TrajectoryLogger."""

    def test_init_creates_logger(self):
        """Test that TrajectoryLogger initializes correctly."""
        logger = TrajectoryLogger(task_goal="test goal", task_type="coding")
        assert logger.task_goal == "test goal"
        assert logger.task_type == "coding"
        assert logger.risk_level == "low"
        assert logger.task_id.startswith("task_")

    def test_init_with_custom_session_id(self):
        """Test initialization with custom session ID."""
        logger = TrajectoryLogger(task_goal="test", session_id="custom_session")
        assert logger.session_id == "custom_session"

    def test_start_sets_started_at(self):
        """Test that start() sets the started_at timestamp."""
        logger = TrajectoryLogger(task_goal="test")
        logger.start()
        assert logger._started_at is not None

    def test_log_action(self):
        """Test logging an action."""
        logger = TrajectoryLogger(task_goal="test")
        logger.log_action("read_file", {"path": "/tmp/test.py"}, "success")
        assert len(logger._actions) == 1
        assert logger._actions[0]["action"] == "read_file"
        assert logger._actions[0]["params"] == {"path": "/tmp/test.py"}

    def test_log_tool_call(self):
        """Test logging a tool call."""
        logger = TrajectoryLogger(task_goal="test")
        logger.log_tool_call("terminal", {"command": "ls"}, "file1.txt")
        assert len(logger._tool_calls) == 1
        assert logger._tool_calls[0]["tool"] == "terminal"

    def test_log_error(self):
        """Test logging an error."""
        logger = TrajectoryLogger(task_goal="test")
        logger.log_error("patch", "FileNotFoundError", recoverable=True)
        assert len(logger._errors) == 1
        assert logger._errors[0]["phase"] == "patch"
        assert logger._errors[0]["recoverable"] is True

    def test_log_fix(self):
        """Test logging a fix."""
        logger = TrajectoryLogger(task_goal="test")
        logger.log_fix("patch", "retry with absolute path", succeeded=True)
        assert len(logger._fixes) == 1
        assert logger._fixes[0]["strategy"] == "retry with absolute path"

    def test_log_plan_step(self):
        """Test logging a plan step."""
        logger = TrajectoryLogger(task_goal="test")
        logger.log_plan_step("Read file", "Get file content")
        assert len(logger._plan) == 1
        assert logger._plan[0]["step"] == "Read file"

    def test_complete_generates_trajectory(self, tmp_path):
        """Test that complete() generates a valid trajectory."""
        logger = TrajectoryLogger(task_goal="test goal", task_type="coding")
        logger.start()
        logger.log_action("read_file", {"path": "/tmp/test.py"})
        logger.log_tool_call("terminal", {"command": "ls"})

        with patch.object(Path, 'parent', new_callable=lambda: property(lambda self: tmp_path)):
            trajectory = logger.complete(
                success=True,
                final_output="Task completed",
                artifacts=["/tmp/output.txt"]
            )

        assert trajectory["task_goal"] == "test goal"
        assert trajectory["success"] is True
        assert trajectory["final_output"] == "Task completed"
        assert "/tmp/output.txt" in trajectory["artifacts"]

    def test_complete_calculates_duration(self):
        """Test that complete() calculates duration."""
        logger = TrajectoryLogger(task_goal="test")
        logger.start()
        trajectory = logger.complete(success=True)
        assert "duration" in trajectory
        assert trajectory["duration"] != ""

    def test_tool_call_logs_error_on_failure(self):
        """Test that tool_call with error also logs an error."""
        logger = TrajectoryLogger(task_goal="test")
        logger.log_tool_call("terminal", {"command": "fail"}, error="Command failed")
        assert len(logger._errors) == 1
        assert logger._errors[0]["message"] == "Command failed"

    def test_tool_call_result_truncation(self):
        """Test that tool call results are truncated to 500 chars."""
        logger = TrajectoryLogger(task_goal="test")
        long_result = "x" * 1000
        logger.log_tool_call("terminal", {"command": "test"}, raw_result=long_result)
        assert len(logger._tool_calls[0]["raw_result"]) == 500

    def test_load_trajectory(self, tmp_path):
        """Test loading a trajectory from file."""
        # Create a test trajectory file
        traj_dir = tmp_path / "data" / "trajectories"
        traj_dir.mkdir(parents=True)
        test_traj = {"task_id": "test_123", "task_goal": "test"}
        (traj_dir / "test_123.json").write_text(json.dumps(test_traj))

        with patch('core.trajectory_logger.Path') as mock_path:
            mock_path.return_value.parent.parent = tmp_path
            result = TrajectoryLogger.load("test_123")
            assert result["task_id"] == "test_123"

    def test_list_trajectories_empty(self, tmp_path):
        """Test listing trajectories when none exist."""
        with patch('core.trajectory_logger.Path') as mock_path:
            mock_path.return_value.parent.parent = tmp_path
            result = TrajectoryLogger.list_trajectories()
            assert result == []

    def test_log_artifact(self):
        """Test logging an artifact."""
        logger = TrajectoryLogger(task_goal="test")
        logger.log_action("write_file", {"path": "/tmp/out.txt"})
        logger.log_artifact("/tmp/out.txt")
        assert logger._actions[-1].get("artifact") == "/tmp/out.txt"
