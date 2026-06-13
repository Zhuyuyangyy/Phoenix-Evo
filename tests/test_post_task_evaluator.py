"""
Tests for PostTaskEvaluator module.
"""

import pytest
from core.post_task_evaluator import PostTaskEvaluator, EvaluationResult, FailureType, WEIGHTS


class TestPostTaskEvaluator:
    """Test suite for PostTaskEvaluator."""

    def _make_trajectory(self, **kwargs):
        """Helper to create a test trajectory."""
        traj = {
            "task_id": "test_001",
            "task_goal": "Fix WSL Chinese path encoding",
            "task_type": "coding",
            "success": True,
            "actions": [
                {"action": "read_file", "params": {"path": "/tmp/test.py"}},
                {"action": "write_file", "params": {"path": "/tmp/test.py"}},
                {"action": "verify_result", "params": {}},
            ],
            "tool_calls": [
                {"tool": "terminal", "args": {"command": "ls"}},
            ],
            "errors": [],
            "fixes": [],
            "artifacts": ["/tmp/test.py"],
            "final_output": "File fixed successfully",
        }
        traj.update(kwargs)
        return traj

    def test_evaluate_success_trajectory(self):
        """Test evaluation of a successful trajectory."""
        traj = self._make_trajectory()
        result = PostTaskEvaluator.evaluate(traj)

        assert result.task_success is True
        assert result.quality_score > 0.7
        assert result.reuse_potential > 0.5
        assert result.should_extract_skill is True
        assert result.failure_type == FailureType.NONE
        assert result.skill_candidate_name is not None

    def test_evaluate_failed_trajectory(self):
        """Test evaluation of a failed trajectory."""
        traj = self._make_trajectory(
            success=False,
            errors=[{"phase": "exec", "message": "SyntaxError: invalid syntax"}],
        )
        result = PostTaskEvaluator.evaluate(traj)

        assert result.task_success is False
        assert result.quality_score < 0.8
        assert result.failure_type == FailureType.EXECUTION

    def test_evaluate_trajectory_with_fixes(self):
        """Test evaluation of trajectory with fix attempts."""
        traj = self._make_trajectory(
            errors=[{"phase": "patch", "message": "FileNotFoundError"}],
            fixes=[{"phase": "patch", "strategy": "retry with absolute path", "succeeded": True}],
        )
        result = PostTaskEvaluator.evaluate(traj)

        assert result.should_extract_skill is True
        assert "修复轨迹" in result.reason or "修复" in result.reason

    def test_classify_failure_context_incomplete(self):
        """Test failure classification for context incomplete."""
        traj = self._make_trajectory(
            success=False,
            errors=[{"phase": "read", "message": "ENOENT: no such file or directory"}],
        )
        result = PostTaskEvaluator.evaluate(traj)
        assert result.failure_type == FailureType.CONTEXT_INCOMPLETE

    def test_classify_failure_permission(self):
        """Test failure classification for permission errors."""
        traj = self._make_trajectory(
            success=False,
            errors=[{"phase": "exec", "message": "Permission denied"}],
        )
        result = PostTaskEvaluator.evaluate(traj)
        assert result.failure_type == FailureType.SAFETY

    def test_classify_failure_timeout(self):
        """Test failure classification for timeout errors."""
        traj = self._make_trajectory(
            success=False,
            errors=[{"phase": "tool", "message": "Connection timed out"}],
        )
        result = PostTaskEvaluator.evaluate(traj)
        assert result.failure_type == FailureType.TOOL_CALL

    def test_classify_failure_planning(self):
        """Test failure classification for planning errors."""
        traj = self._make_trajectory(
            success=False,
            errors=[{"phase": "plan", "message": "Cannot parse intent"}],
        )
        result = PostTaskEvaluator.evaluate(traj)
        assert result.failure_type == FailureType.PLANNING

    def test_classify_failure_unknown(self):
        """Test failure classification for unknown errors."""
        traj = self._make_trajectory(
            success=False,
            errors=[{"phase": "unknown", "message": "Something weird happened"}],
        )
        result = PostTaskEvaluator.evaluate(traj)
        assert result.failure_type == FailureType.UNKNOWN

    def test_no_extraction_for_safety_failure(self):
        """Test that safety failures are not extracted as skills."""
        traj = self._make_trajectory(
            success=False,
            errors=[{"phase": "exec", "message": "Permission denied"}],
        )
        result = PostTaskEvaluator.evaluate(traj)
        assert result.should_extract_skill is False
        assert "safety" in result.reason.lower() or "安全" in result.reason

    def test_quality_score_range(self):
        """Test that quality score is in valid range."""
        traj = self._make_trajectory()
        result = PostTaskEvaluator.evaluate(traj)
        assert 0.0 <= result.quality_score <= 1.0

    def test_reuse_potential_range(self):
        """Test that reuse potential is in valid range."""
        traj = self._make_trajectory()
        result = PostTaskEvaluator.evaluate(traj)
        assert 0.0 <= result.reuse_potential <= 1.0

    def test_score_dimensions_success(self):
        """Test individual scoring dimensions."""
        evaluator = PostTaskEvaluator()
        traj = self._make_trajectory()
        scores = evaluator._score_dimensions(traj)

        assert scores["success"] == 1.0
        assert scores["no_error"] == 1.0
        assert scores["no_fix"] == 1.0
        assert scores["verification"] == 1.0
        assert scores["tool_efficiency"] == 1.0  # <= 5 tool calls
        assert scores["no_repeat"] == 1.0

    def test_score_dimensions_with_errors(self):
        """Test scoring with errors present."""
        evaluator = PostTaskEvaluator()
        traj = self._make_trajectory(
            errors=[{"phase": "exec", "message": "error"}],
        )
        scores = evaluator._score_dimensions(traj)
        assert scores["no_error"] == 0.0

    def test_tool_efficiency_scoring(self):
        """Test tool efficiency scoring for different call counts."""
        evaluator = PostTaskEvaluator()

        # <= 5 calls: 1.0
        traj = self._make_trajectory(tool_calls=[{"tool": "t"}] * 5)
        scores = evaluator._score_dimensions(traj)
        assert scores["tool_efficiency"] == 1.0

        # <= 15 calls: 0.8
        traj = self._make_trajectory(tool_calls=[{"tool": "t"}] * 10)
        scores = evaluator._score_dimensions(traj)
        assert scores["tool_efficiency"] == 0.8

        # <= 25 calls: 0.5
        traj = self._make_trajectory(tool_calls=[{"tool": "t"}] * 20)
        scores = evaluator._score_dimensions(traj)
        assert scores["tool_efficiency"] == 0.5

        # > 25 calls: 0.2
        traj = self._make_trajectory(tool_calls=[{"tool": "t"}] * 30)
        scores = evaluator._score_dimensions(traj)
        assert scores["tool_efficiency"] == 0.2

    def test_has_verification_detects_check(self):
        """Test that verification detection works."""
        evaluator = PostTaskEvaluator()

        # With verify action
        traj = self._make_trajectory(actions=[{"action": "verify_result"}])
        assert evaluator._has_verification(traj) is True

        # Without verify action
        traj = self._make_trajectory(actions=[{"action": "read_file"}])
        assert evaluator._has_verification(traj) is False

    def test_has_verification_detects_test_tool(self):
        """Test that verification detection works for test tools."""
        evaluator = PostTaskEvaluator()
        traj = self._make_trajectory(
            actions=[],
            tool_calls=[{"tool": "pytest", "args": {}}],
        )
        assert evaluator._has_verification(traj) is True

    def test_infer_skill_name(self):
        """Test skill name inference from trajectory."""
        evaluator = PostTaskEvaluator()
        traj = self._make_trajectory(task_goal="Fix WSL path encoding", task_type="coding")
        name = evaluator._infer_skill_name(traj)
        assert "code" in name or "coding" in name

    def test_gen_improvement_suggestions(self):
        """Test improvement suggestion generation."""
        evaluator = PostTaskEvaluator()
        traj = self._make_trajectory(
            errors=[{"phase": "exec", "message": "error"}],
            fixes=[],
        )
        suggestion = evaluator._gen_improvement(traj, FailureType.EXECUTION, "test cause")
        assert len(suggestion) > 0

    def test_weights_sum_to_one(self):
        """Test that scoring weights sum to 1.0."""
        total = sum(WEIGHTS.values())
        assert abs(total - 1.0) < 0.001

    def test_evaluate_no_actions(self):
        """Test evaluation with empty actions list."""
        traj = self._make_trajectory(actions=[], tool_calls=[])
        result = PostTaskEvaluator.evaluate(traj)
        assert result.quality_score >= 0.0

    def test_evaluate_no_artifacts(self):
        """Test evaluation without artifacts."""
        traj = self._make_trajectory(artifacts=[])
        result = PostTaskEvaluator.evaluate(traj)
        assert result.reuse_potential < 1.0
