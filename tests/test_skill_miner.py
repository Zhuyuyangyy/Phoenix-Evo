"""
Tests for SkillMiner module.
"""

from core.post_task_evaluator import EvaluationResult
from core.skill_miner import SkillMiner


class TestSkillMiner:
    """Test suite for SkillMiner."""

    def _make_trajectory(self, **kwargs):
        """Helper to create a test trajectory."""
        traj = {
            "task_id": "traj_001",
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
        }
        traj.update(kwargs)
        return traj

    def _make_eval_result(self, **kwargs):
        """Helper to create an EvaluationResult."""
        er = EvaluationResult(
            task_success=True,
            quality_score=0.85,
            reuse_potential=0.7,
            should_extract_skill=True,
            reason="high quality trajectory",
            failure_type="none",
            root_cause=None,
            improvement_suggestion="looks good",
            skill_candidate_name="fix_wsl_path",
        )
        for k, v in kwargs.items():
            setattr(er, k, v)
        return er

    def test_mine_returns_skill_dict(self):
        """Test that mine returns a valid skill dict."""
        miner = SkillMiner()
        traj = self._make_trajectory()
        eval_result = self._make_eval_result()

        skill = miner.mine(traj, eval_result)

        assert "skill_id" in skill
        assert "skill_name" in skill
        assert "skill_md" in skill
        assert "source_trajectory" in skill
        assert "quality_score" in skill

    def test_mine_uses_eval_skill_name(self):
        """Test that mine uses the skill name from evaluation."""
        miner = SkillMiner()
        traj = self._make_trajectory()
        eval_result = self._make_eval_result(skill_candidate_name="custom_skill_name")

        skill = miner.mine(traj, eval_result)
        assert skill["skill_name"] == "custom_skill_name"

    def test_mine_generates_default_name(self):
        """Test that mine generates a default name when not specified."""
        miner = SkillMiner()
        traj = self._make_trajectory()
        eval_result = self._make_eval_result(skill_candidate_name=None)

        skill = miner.mine(traj, eval_result)
        assert skill["skill_name"].startswith("code_") or skill["skill_name"].startswith("task_") or skill["skill_name"].startswith("skill_")

    def test_mine_extracts_inputs(self):
        """Test that mine extracts inputs from tool calls."""
        miner = SkillMiner()
        traj = self._make_trajectory(tool_calls=[
            {"tool": "read_file", "args": {"path": "/tmp/test.py"}},
        ])
        eval_result = self._make_eval_result()

        skill = miner.mine(traj, eval_result)
        assert len(skill["inputs"]) > 0

    def test_mine_extracts_procedure(self):
        """Test that mine extracts procedure steps."""
        miner = SkillMiner()
        traj = self._make_trajectory()
        eval_result = self._make_eval_result()

        skill = miner.mine(traj, eval_result)
        assert len(skill["procedure"]) > 0

    def test_mine_extracts_validation(self):
        """Test that mine extracts validation steps."""
        miner = SkillMiner()
        traj = self._make_trajectory(actions=[
            {"action": "verify_result", "params": {}},
        ])
        eval_result = self._make_eval_result()

        skill = miner.mine(traj, eval_result)
        assert len(skill["validation"]) > 0

    def test_mine_extracts_failure_cases(self):
        """Test that mine extracts failure cases."""
        miner = SkillMiner()
        traj = self._make_trajectory(
            errors=[{"phase": "exec", "message": "FileNotFoundError"}],
            fixes=[{"phase": "exec", "strategy": "retry", "succeeded": True}],
        )
        eval_result = self._make_eval_result()

        skill = miner.mine(traj, eval_result)
        assert len(skill["failure_cases"]) > 0

    def test_mine_skill_md_contains_metadata(self):
        """Test that generated skill_md contains metadata."""
        miner = SkillMiner()
        traj = self._make_trajectory()
        eval_result = self._make_eval_result()

        skill = miner.mine(traj, eval_result)
        assert "## Metadata" in skill["skill_md"]
        assert "## Procedure" in skill["skill_md"]
        assert "## Validation" in skill["skill_md"]

    def test_mine_skill_md_contains_safety_note(self):
        """Test that generated skill_md contains safety note."""
        miner = SkillMiner()
        traj = self._make_trajectory()
        eval_result = self._make_eval_result()

        skill = miner.mine(traj, eval_result)
        assert "## Safety Note" in skill["skill_md"]

    def test_default_name_from_goal(self):
        """Test default name generation from task goal."""
        miner = SkillMiner()
        traj = {"task_goal": "Fix WSL Chinese path encoding"}
        name = miner._default_name(traj)
        assert "Fix" in name or "fix" in name or "WSL" in name

    def test_extract_inputs_from_tool_calls(self):
        """Test input extraction from tool calls."""
        miner = SkillMiner()
        traj = {
            "tool_calls": [
                {"args": {"path": "/tmp/test.py", "content": "hello"}},
            ],
            "task_goal": "test goal",
        }
        inputs = miner._extract_inputs(traj)
        assert len(inputs) > 0
        assert any(i["name"] == "path" for i in inputs)

    def test_extract_procedure_from_actions(self):
        """Test procedure extraction from actions."""
        miner = SkillMiner()
        traj = {
            "actions": [
                {"action": "read_file", "params": {"path": "/tmp/test.py"}},
                {"action": "write_file", "params": {"content": "hello"}},
            ],
        }
        procedure = miner._extract_procedure(traj)
        assert len(procedure) == 2
        assert "1." in procedure[0]

    def test_extract_validation_detects_verify(self):
        """Test validation extraction detects verify actions."""
        miner = SkillMiner()
        traj = {
            "actions": [
                {"action": "verify_result", "result": "OK"},
            ],
        }
        validations = miner._extract_validation(traj)
        assert len(validations) > 0
        assert any("verify" in v.lower() for v in validations)

    def test_extract_validation_no_verify(self):
        """Test validation extraction with no verify actions."""
        miner = SkillMiner()
        traj = {
            "actions": [
                {"action": "read_file", "result": "OK"},
            ],
        }
        validations = miner._extract_validation(traj)
        assert any("WARNING" in v for v in validations)

    def test_extract_failure_cases(self):
        """Test failure case extraction."""
        miner = SkillMiner()
        traj = {
            "errors": [{"phase": "exec", "message": "error"}],
            "fixes": [{"phase": "exec", "strategy": "retry", "succeeded": True}],
        }
        cases = miner._extract_failure_cases(traj)
        assert len(cases) == 1
        assert cases[0]["succeeded"] is True

    def test_quality_score_preserved(self):
        """Test that quality score is preserved in output."""
        miner = SkillMiner()
        traj = self._make_trajectory()
        eval_result = self._make_eval_result(quality_score=0.95)

        skill = miner.mine(traj, eval_result)
        assert skill["quality_score"] == 0.95
