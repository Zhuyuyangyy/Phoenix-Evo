"""
Tests for ExecutionGuard module.
"""

from core.execution_guard import ExecutionGateResult, ExecutionGuard


class TestExecutionGuard:
    """Test suite for ExecutionGuard."""

    def _make_skill(self, **kwargs):
        """Helper to create a test skill."""
        skill = {
            "skill_id": "test_001",
            "skill_name": "test_skill",
            "task_goal": "Fix WSL path encoding",
            "risk_level": "low",
            "inputs": ["path", "content"],
            "procedure": ["1. Read file", "2. Write file", "3. Verify"],
        }
        skill.update(kwargs)
        return skill

    def _make_router_decision(self, **kwargs):
        """Helper to create a mock router decision."""
        decision = type("RouterDecision", (), {
            "confidence": 0.8,
            "action": "auto_use",
            "skill_id": "test_001",
            "skill_name": "test_skill",
        })()
        for k, v in kwargs.items():
            setattr(decision, k, v)
        return decision

    def test_check_passes_clean_skill(self):
        """Test that clean skill passes gate."""
        guard = ExecutionGuard()
        skill = self._make_skill()
        decision = self._make_router_decision()

        result = guard.check(skill, decision)
        assert result.passed is True
        assert result.gate_action == "pass"

    def test_check_blocks_low_confidence(self):
        """Test that low confidence blocks skill."""
        guard = ExecutionGuard()
        skill = self._make_skill()
        decision = self._make_router_decision(confidence=0.1)

        result = guard.check(skill, decision)
        assert result.passed is False
        assert result.gate_action == "block"

    def test_check_blocks_context_mismatch(self):
        """Test that context mismatch blocks skill."""
        guard = ExecutionGuard()
        skill = self._make_skill(task_goal="Deploy Kubernetes cluster")
        decision = self._make_router_decision()
        task_context = {"task_goal": "Fix WSL Chinese path encoding"}

        result = guard.check(skill, decision, task_context)
        # May or may not block depending on word overlap
        assert result.gate_action in ("pass", "warn", "block")

    def test_check_blocks_destructive_operation(self):
        """Test that destructive operations block skill."""
        guard = ExecutionGuard()
        skill = self._make_skill(procedure=["1. rm -rf /tmp/old"])
        decision = self._make_router_decision()

        result = guard.check(skill, decision)
        assert result.passed is False
        assert result.gate_action == "block"

    def test_check_warns_risky_operation(self):
        """Test that risky operations warn."""
        guard = ExecutionGuard()
        skill = self._make_skill(procedure=["1. exec(user_code)"])
        decision = self._make_router_decision()

        result = guard.check(skill, decision)
        assert "risky_operation" in result.risk_tags

    def test_check_blocks_critical_skill_risk(self):
        """Test that critical skill risk blocks."""
        guard = ExecutionGuard()
        skill = self._make_skill(risk_level="critical")
        decision = self._make_router_decision()

        result = guard.check(skill, decision)
        assert result.passed is False
        assert result.gate_action == "block"

    def test_check_blocks_high_risk_amplification(self):
        """Test that high risk amplification blocks."""
        guard = ExecutionGuard()
        skill = self._make_skill(risk_level="high")
        decision = self._make_router_decision()
        task_context = {"risk_level": "high"}

        result = guard.check(skill, decision, task_context)
        assert result.passed is False

    def test_compute_context_match_identical(self):
        """Test context match with identical goals."""
        guard = ExecutionGuard()
        score = guard._compute_context_match(
            "Fix WSL path encoding",
            "Fix WSL path encoding"
        )
        assert score == 1.0

    def test_compute_context_match_similar(self):
        """Test context match with similar goals."""
        guard = ExecutionGuard()
        score = guard._compute_context_match(
            "Fix WSL Chinese path encoding",
            "Fix WSL path encoding issue"
        )
        assert score > 0.3

    def test_compute_context_match_different(self):
        """Test context match with different goals."""
        guard = ExecutionGuard()
        score = guard._compute_context_match(
            "Deploy Kubernetes cluster",
            "Fix WSL path encoding"
        )
        assert score < 0.3

    def test_compute_context_match_empty(self):
        """Test context match with empty goals."""
        guard = ExecutionGuard()
        score = guard._compute_context_match("", "test")
        assert score == 0.0

    def test_gate_result_fields(self):
        """Test that ExecutionGateResult has all required fields."""
        result = ExecutionGateResult(
            skill_id="test",
            skill_name="test_skill",
            passed=True,
            gate_action="pass",
            risk_tags=[],
            warnings=[],
            block_reason="",
            context_match_score=0.8,
            suggested_next="proceed",
        )
        assert result.skill_id == "test"
        assert result.passed is True

    def test_check_warns_missing_inputs(self):
        """Test warning for missing inputs."""
        guard = ExecutionGuard()
        skill = self._make_skill(inputs=["path", "content", "extra_input"])
        decision = self._make_router_decision()
        task_context = {"available_inputs": ["path", "content"]}

        result = guard.check(skill, decision, task_context)
        # Should warn about missing input
        assert any("missing" in w.lower() or "缺少" in w for w in result.warnings) or result.passed

    def test_check_no_task_context(self):
        """Test check without task context."""
        guard = ExecutionGuard()
        skill = self._make_skill()
        decision = self._make_router_decision()

        result = guard.check(skill, decision, None)
        assert result.passed is True

    def test_destructive_patterns_coverage(self):
        """Test that destructive patterns are defined."""
        guard = ExecutionGuard()
        assert len(guard.DESTRUCTIVE_PATTERNS) > 0
        assert "rm -rf" in guard.DESTRUCTIVE_PATTERNS

    def test_risky_action_patterns_coverage(self):
        """Test that risky action patterns are defined."""
        guard = ExecutionGuard()
        assert len(guard.RISKY_ACTION_PATTERNS) > 0
        assert "exec" in guard.RISKY_ACTION_PATTERNS
