"""
Tests for FallbackManager module.
"""


from core.fallback_manager import FallbackAction, FallbackManager


class TestFallbackManager:
    """Test suite for FallbackManager."""

    def test_init_creates_manager(self, tmp_path):
        """Test that FallbackManager initializes correctly."""
        manager = FallbackManager(root=tmp_path)
        assert manager.root == tmp_path
        assert manager.fallback_dir.exists()

    def test_handle_failure_timeout(self, tmp_path):
        """Test handling timeout failure."""
        manager = FallbackManager(root=tmp_path)
        action = manager.handle_failure("skill_001", "timeout", "connection timed out")

        assert action.action == "retry"
        assert action.retry_allowed is True
        assert action.retry_after_sec == 30

    def test_handle_failure_error(self, tmp_path):
        """Test handling error failure."""
        manager = FallbackManager(root=tmp_path)
        action = manager.handle_failure("skill_001", "error", "execution error")

        assert action.action == "retry"
        assert action.retry_allowed is True

    def test_handle_failure_user_rejected(self, tmp_path):
        """Test handling user rejection."""
        manager = FallbackManager(root=tmp_path)
        action = manager.handle_failure("skill_001", "user_rejected", "user said no")

        assert action.action == "use_older"
        assert action.retry_allowed is False

    def test_handle_failure_context_mismatch(self, tmp_path):
        """Test handling context mismatch."""
        manager = FallbackManager(root=tmp_path)
        action = manager.handle_failure("skill_001", "context_mismatch", "wrong context")

        assert action.action == "use_manual"
        assert action.retry_allowed is False

    def test_handle_failure_consecutive_timeout_degrades(self, tmp_path):
        """Test that consecutive timeouts lead to degradation."""
        manager = FallbackManager(root=tmp_path)

        # First timeout - retry
        action1 = manager.handle_failure("skill_001", "timeout", "timeout 1")
        assert action1.action == "retry"

        # Second timeout - degrade
        action2 = manager.handle_failure("skill_001", "timeout", "timeout 2")
        assert action2.action == "degrade"
        assert action2.degraded_to == "quarantine"

    def test_handle_failure_total_failures_degrades(self, tmp_path):
        """Test that total failures lead to degradation."""
        manager = FallbackManager(root=tmp_path)

        # Different failure types
        manager.handle_failure("skill_001", "timeout", "timeout")
        manager.handle_failure("skill_001", "error", "error")
        action = manager.handle_failure("skill_001", "user_rejected", "rejected")

        assert action.action == "degrade"
        assert action.degraded_to == "quarantine"

    def test_handle_failure_high_risk_immediate_degrade(self, tmp_path):
        """Test that high-risk skill fails immediately degrade."""
        manager = FallbackManager(root=tmp_path)

        # Create a skill index with high risk
        index_path = tmp_path / "skills" / "skill_index.json"
        index_path.parent.mkdir(parents=True)
        import json
        index_path.write_text(json.dumps({
            "skill_001": {"risk_level": "high", "status": "active"}
        }))

        action = manager.handle_failure("skill_001", "error", "error", index_path)
        assert action.action == "degrade"
        assert action.degraded_to == "quarantine"

    def test_handle_success(self, tmp_path):
        """Test handling success."""
        manager = FallbackManager(root=tmp_path)

        # Create a skill index
        index_path = tmp_path / "skills" / "skill_index.json"
        index_path.parent.mkdir(parents=True)
        import json
        index_path.write_text(json.dumps({
            "skill_001": {
                "usage_count": 5,
                "success_count": 3,
                "success_rate": 0.6,
            }
        }))

        manager.handle_success("skill_001", index_path)

        # Verify the index was updated
        data = json.loads(index_path.read_text())
        assert data["skill_001"]["usage_count"] == 6
        assert data["skill_001"]["success_count"] == 4

    def test_get_fallback_chain(self, tmp_path):
        """Test getting fallback chain."""
        manager = FallbackManager(root=tmp_path)

        all_skills = [
            {"skill_id": "skill_001", "status": "active", "evidence_score": 0.8, "usage_count": 10},
            {"skill_id": "skill_002", "status": "active", "evidence_score": 0.7, "usage_count": 5},
            {"skill_id": "skill_003", "status": "draft", "evidence_score": 0.6, "usage_count": 3},
            {"skill_id": "skill_004", "status": "archived", "evidence_score": 0.9, "usage_count": 20},
        ]

        chain = manager.get_fallback_chain("skill_001", all_skills)
        assert len(chain) <= 3
        # Should not include the primary skill or archived
        assert all(s["skill_id"] != "skill_001" for s in chain)
        assert all(s["status"] != "archived" for s in chain)

    def test_get_fallback_chain_sorted(self, tmp_path):
        """Test that fallback chain is sorted by priority."""
        manager = FallbackManager(root=tmp_path)

        all_skills = [
            {"skill_id": "skill_002", "status": "draft", "evidence_score": 0.5, "usage_count": 1},
            {"skill_id": "skill_003", "status": "active", "evidence_score": 0.9, "usage_count": 20},
        ]

        chain = manager.get_fallback_chain("skill_001", all_skills)
        if len(chain) >= 2:
            # Active should come before draft
            assert chain[0]["status"] == "active"

    def test_record_failure_creates_log(self, tmp_path):
        """Test that failure recording creates log file."""
        manager = FallbackManager(root=tmp_path)
        manager._record_failure("skill_001", "timeout", "test timeout")

        log_path = manager.fallback_dir / "skill_001.jsonl"
        assert log_path.exists()

    def test_count_consecutive_failures(self, tmp_path):
        """Test consecutive failure counting."""
        manager = FallbackManager(root=tmp_path)

        history = [
            {"type": "timeout", "result": "fail"},
            {"type": "timeout", "result": "fail"},
            {"type": "success", "result": "success"},
        ]
        count = manager._count_consecutive_failures(history, "timeout")
        assert count == 0  # Reset by success

    def test_count_consecutive_failures_no_reset(self, tmp_path):
        """Test consecutive failure counting without reset."""
        manager = FallbackManager(root=tmp_path)

        history = [
            {"type": "timeout", "result": "fail"},
            {"type": "timeout", "result": "fail"},
        ]
        count = manager._count_consecutive_failures(history, "timeout")
        assert count == 2

    def test_get_failure_stats(self, tmp_path):
        """Test getting failure statistics."""
        manager = FallbackManager(root=tmp_path)
        manager.failure_history["skill_001"] = [
            {"type": "timeout", "result": "fail", "at": "2024-01-01"},
            {"type": "success", "result": "success", "at": "2024-01-02"},
        ]

        stats = manager.get_failure_stats("skill_001")
        assert stats["total_invocations"] == 2
        assert stats["successes"] == 1
        assert stats["failures"] == 1

    def test_get_failure_stats_empty(self, tmp_path):
        """Test getting failure statistics for unknown skill."""
        manager = FallbackManager(root=tmp_path)
        stats = manager.get_failure_stats("unknown_skill")
        assert stats["total_invocations"] == 0

    def test_fallback_action_fields(self):
        """Test that FallbackAction has all required fields."""
        action = FallbackAction(
            action="retry",
            reason="timeout",
            skill_id="test",
            degraded_to="",
            escalate=False,
            retry_allowed=True,
            retry_after_sec=30,
        )
        assert action.action == "retry"
        assert action.retry_allowed is True
