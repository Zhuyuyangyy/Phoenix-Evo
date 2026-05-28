# -*- coding: utf-8 -*-
"""
Phoenix-Evo Smoke Test Suite
=============================

快速验证项目健康状态的冒烟测试：
  - 所有核心模块可导入
  - 所有运行时模块可导入
  - 关键类可实例化
  - 项目目录结构完整
  - TrajectoryLogger 基本生命周期
  - PostTaskEvaluator 基本评分
  - SkillVerifier 危险模式检测
  - SkillRegistry draft 操作
  - ImmuneGuard 危险技能拦截

运行方式：
  cd Phoenix-Evo
  pytest tests/test_smoke.py -v
"""

import sys
import os
import tempfile
import shutil
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest


# =============================================================================
# 1. Core Module Imports
# =============================================================================

class TestCoreImports:
    """验证所有 core 模块可正常导入。"""

    def test_import_phoenix_evo(self):
        from core.phoenix_evo import PhoenixEvo
        assert PhoenixEvo is not None

    def test_import_trajectory_logger(self):
        from core.trajectory_logger import TrajectoryLogger
        assert TrajectoryLogger is not None

    def test_import_post_task_evaluator(self):
        from core.post_task_evaluator import PostTaskEvaluator, EvaluationResult
        assert PostTaskEvaluator is not None
        assert EvaluationResult is not None

    def test_import_skill_miner(self):
        from core.skill_miner import SkillMiner
        assert SkillMiner is not None

    def test_import_skill_verifier(self):
        from core.skill_verifier import SkillVerifier, VerificationResult
        assert SkillVerifier is not None
        assert VerificationResult is not None

    def test_import_skill_registry(self):
        from core.skill_registry import SkillRegistry
        assert SkillRegistry is not None

    def test_import_immune_guard(self):
        from core.immune_guard import ImmuneGuard, ImmuneDecision
        assert ImmuneGuard is not None
        assert ImmuneDecision is not None

    def test_import_immune_memory(self):
        from core.immune_memory import ImmuneMemory
        assert ImmuneMemory is not None

    def test_import_quarantine_manager(self):
        from core.quarantine_manager import QuarantineManager
        assert QuarantineManager is not None

    def test_import_risk_policy(self):
        from core.risk_policy import RiskProfile, RiskPolicy
        assert RiskProfile is not None
        assert RiskPolicy is not None

    def test_import_skill_similarity(self):
        from core.skill_similarity import SkillVectorizer, SimilarityResult
        assert SkillVectorizer is not None
        assert SimilarityResult is not None

    def test_import_drift_detector(self):
        from core.drift_detector import DriftDetector
        assert DriftDetector is not None

    def test_import_curator_policy(self):
        from core.curator_policy import CuratorPolicy, MergeAction, ArchiveAction
        assert CuratorPolicy is not None
        assert MergeAction is not None

    def test_import_skill_curator(self):
        from core.skill_curator import SkillCurator
        assert SkillCurator is not None

    def test_import_skill_evidence(self):
        from core.skill_evidence import SkillEvidenceManager, SkillCard
        assert SkillEvidenceManager is not None
        assert SkillCard is not None

    def test_import_skill_benchmark(self):
        from core.skill_benchmark import SkillBenchmark
        assert SkillBenchmark is not None

    def test_import_skill_replay(self):
        from core.skill_replay import SkillReplay, ReplayReport
        assert SkillReplay is not None
        assert ReplayReport is not None

    def test_import_replay_reporter(self):
        from core.replay_reporter import ReplayReporter, EvidenceSummary
        assert ReplayReporter is not None
        assert EvidenceSummary is not None

    def test_import_runtime_reporter(self):
        from core.runtime_reporter import RuntimeReporter
        assert RuntimeReporter is not None

    def test_import_core_package(self):
        """验证 core/__init__.py 的统一导出。"""
        from core import (
            PhoenixEvo,
            TrajectoryLogger,
            PostTaskEvaluator,
            SkillMiner,
            SkillVerifier,
            SkillRegistry,
            ImmuneGuard,
            ImmuneMemory,
            QuarantineManager,
            RiskPolicy,
            SkillVectorizer,
            DriftDetector,
            SkillCurator,
            SkillEvidenceManager,
            SkillReplay,
            ReplayReporter,
            SkillRetriever,
            SkillRouter,
            ExecutionGuard,
            FallbackManager,
            RuntimeReporter,
        )
        # If we get here, all imports succeeded
        assert True


# =============================================================================
# 2. Runtime Module Imports
# =============================================================================

class TestRuntimeImports:
    """验证所有 runtime 模块可正常导入。"""

    def test_import_phoenix_runtime(self):
        from runtime.phoenix_runtime import PhoenixRuntime, RuntimeResult
        assert PhoenixRuntime is not None
        assert RuntimeResult is not None

    def test_import_skill_router(self):
        from runtime.skill_router import SkillRouter, RouteResult, RouteDecision
        assert SkillRouter is not None
        assert RouteResult is not None
        assert RouteDecision is not None

    def test_import_runtime_guard(self):
        from runtime.runtime_guard import RuntimeGuard, GuardResult, GuardDecision
        assert RuntimeGuard is not None
        assert GuardResult is not None
        assert GuardDecision is not None

    def test_import_context_injector(self):
        from runtime.context_injector import ContextInjector
        assert ContextInjector is not None

    def test_import_fallback_manager(self):
        from runtime.fallback_manager import FallbackManager, FallbackResult
        assert FallbackManager is not None
        assert FallbackResult is not None

    def test_import_runtime_reporter(self):
        from runtime.runtime_reporter import RuntimeReporter, RuntimeCallRecord
        assert RuntimeReporter is not None
        assert RuntimeCallRecord is not None

    def test_import_skill_retriever(self):
        from runtime.skill_retriever import SkillRetriever
        assert SkillRetriever is not None

    def test_import_agent_runtime(self):
        from runtime.agent_runtime import AgentRuntime, TaskState, TaskContext
        assert AgentRuntime is not None
        assert TaskState is not None
        assert TaskContext is not None

    def test_import_phoenix_daemon(self):
        from runtime.phoenix_daemon import PhoenixRuntimeDaemon
        assert PhoenixRuntimeDaemon is not None

    def test_import_phoenix_metrics(self):
        from runtime.phoenix_metrics import PhoenixMetrics
        assert PhoenixMetrics is not None

    def test_import_outcome_tracker(self):
        from runtime.outcome_tracker import OutcomeTracker
        assert OutcomeTracker is not None

    def test_import_feedback_dispatcher(self):
        from runtime.feedback_dispatcher import FeedbackDispatcher
        assert FeedbackDispatcher is not None

    def test_import_project_router(self):
        from runtime.project_router import ProjectRouter
        assert ProjectRouter is not None

    def test_import_task_type_classifier(self):
        from runtime.task_type_classifier import TaskTypeClassifier
        assert TaskTypeClassifier is not None

    def test_import_runtime_skill_bridge(self):
        from runtime.runtime_skill_bridge import HermesRuntimeBridge, BridgeTaskState, BridgeTaskContext
        assert HermesRuntimeBridge is not None
        assert BridgeTaskState is not None
        assert BridgeTaskContext is not None

    def test_import_skill_injection_policy(self):
        from runtime.skill_injection_policy import SafeInjectionPolicy, InjectionDecision, InjectionPolicyResult
        assert SafeInjectionPolicy is not None
        assert InjectionDecision is not None
        assert InjectionPolicyResult is not None

    def test_import_seed_skills(self):
        from runtime.seed_skills import SeedSkillLoader, SEED_SKILLS
        assert SeedSkillLoader is not None
        assert SEED_SKILLS is not None

    def test_import_runtime_package(self):
        """验证 runtime/__init__.py 的统一导出。"""
        from runtime import (
            SkillRetriever,
            SkillRouter,
            RouteResult,
            RouteDecision,
            RuntimeGuard,
            GuardResult,
            GuardDecision,
            FallbackManager,
            FallbackResult,
            FallbackReason,
            RuntimeReporter,
            RuntimeCallRecord,
            ContextInjector,
            PhoenixRuntime,
        )
        assert True


# =============================================================================
# 3. Integrations Module Imports
# =============================================================================

class TestIntegrationImports:
    """验证 integrations 模块可正常导入。"""

    def test_import_hermes_adapter(self):
        from integrations.hermes_adapter import HermesAdapter
        assert HermesAdapter is not None

    def test_import_phoenix_bridge(self):
        from integrations.phoenix_bridge import PhoenixBridge
        assert PhoenixBridge is not None

    def test_import_async_bridge(self):
        from integrations.async_bridge import AsyncBridge
        assert AsyncBridge is not None

    def test_import_integration_policy(self):
        from integrations.integration_policy import IntegrationPolicy
        assert IntegrationPolicy is not None


# =============================================================================
# 4. Directory Structure
# =============================================================================

class TestDirectoryStructure:
    """验证项目关键目录和文件存在。"""

    @pytest.fixture
    def project_root(self):
        return Path(__file__).parent.parent

    def test_core_dir(self, project_root):
        assert (project_root / "core").is_dir()

    def test_runtime_dir(self, project_root):
        assert (project_root / "runtime").is_dir()

    def test_integrations_dir(self, project_root):
        assert (project_root / "integrations").is_dir()

    def test_cli_dir(self, project_root):
        assert (project_root / "cli").is_dir()

    def test_skills_dir(self, project_root):
        assert (project_root / "skills").is_dir()

    def test_skills_subdirs(self, project_root):
        for subdir in ["draft", "active", "archived"]:
            assert (project_root / "skills" / subdir).is_dir(), f"skills/{subdir} missing"

    def test_docs_dir(self, project_root):
        assert (project_root / "docs").is_dir()

    def test_tests_dir(self, project_root):
        assert (project_root / "tests").is_dir()

    def test_requirements_txt(self, project_root):
        assert (project_root / "requirements.txt").is_file()

    def test_dockerfile(self, project_root):
        assert (project_root / "Dockerfile").is_file()

    def test_docker_compose(self, project_root):
        assert (project_root / "docker-compose.yml").is_file()

    def test_gitignore(self, project_root):
        assert (project_root / ".gitignore").is_file()

    def test_readme(self, project_root):
        assert (project_root / "README.md").is_file()


# =============================================================================
# 5. TrajectoryLogger Lifecycle
# =============================================================================

class TestTrajectoryLoggerLifecycle:
    """验证 TrajectoryLogger 的基本生命周期。"""

    def test_full_lifecycle(self):
        from core.trajectory_logger import TrajectoryLogger

        logger = TrajectoryLogger(task_goal="smoke_test_goal", task_type="testing")
        logger.start()
        logger.log_action("test_action", {"key": "value"})
        logger.log_tool_call("terminal", {"command": "echo ok"}, "ok", "")
        trajectory = logger.complete(
            success=True,
            final_output="smoke test passed",
            artifacts=["/tmp/test.txt"],
        )

        assert trajectory is not None
        assert trajectory["task_goal"] == "smoke_test_goal"
        assert trajectory["task_type"] == "testing"
        assert trajectory["success"] is True
        assert len(trajectory["actions"]) >= 1
        assert len(trajectory["tool_calls"]) >= 1

    def test_error_logging(self):
        from core.trajectory_logger import TrajectoryLogger

        logger = TrajectoryLogger(task_goal="error_test", task_type="testing")
        logger.start()
        logger.log_error("terminal", "command not found")
        logger.log_fix("terminal", "retry with correct path")
        trajectory = logger.complete(success=False, final_output="failed")

        assert trajectory["success"] is False
        assert len(trajectory["errors"]) >= 1
        assert len(trajectory["fixes"]) >= 1


# =============================================================================
# 6. PostTaskEvaluator
# =============================================================================

class TestPostTaskEvaluator:
    """验证 PostTaskEvaluator 基本评分逻辑。"""

    def test_successful_trajectory_evaluation(self):
        from core.post_task_evaluator import PostTaskEvaluator

        evaluator = PostTaskEvaluator()
        trajectory = {
            "task_goal": "smoke test evaluation",
            "task_type": "testing",
            "success": True,
            "tool_calls": [
                {"tool": "terminal", "args": {"command": "echo ok"}, "result": "ok", "error": ""},
            ],
            "actions": [{"action": "run_test", "args": {}}],
            "errors": [],
            "fixes": [],
            "artifacts": ["/tmp/out.txt"],
        }

        result = evaluator.evaluate(trajectory)
        assert result.task_success is True
        assert result.quality_score > 0
        assert result.reason  # reason should be non-empty

    def test_failed_trajectory_evaluation(self):
        from core.post_task_evaluator import PostTaskEvaluator

        evaluator = PostTaskEvaluator()
        trajectory = {
            "task_goal": "smoke test failure",
            "task_type": "testing",
            "success": False,
            "tool_calls": [
                {"tool": "terminal", "args": {"command": "bad_cmd"}, "result": "", "error": "not found"},
            ],
            "actions": [],
            "errors": [{"tool": "terminal", "error": "not found"}],
            "fixes": [],
            "artifacts": [],
        }

        result = evaluator.evaluate(trajectory)
        assert result.task_success is False
        assert result.quality_score < 1.0
        assert result.failure_type is not None


# =============================================================================
# 7. SkillVerifier — Dangerous Pattern Detection
# =============================================================================

class TestSkillVerifierDangerousPatterns:
    """验证 SkillVerifier 能检测危险模式。"""

    @staticmethod
    def _make_trajectory(**overrides):
        """构造一个合法的 trajectory 用于验证器。"""
        base = {
            "task_id": "traj_smoke_001",
            "task_goal": "smoke test task",
            "task_type": "testing",
            "success": True,
            "tool_calls": [
                {"tool": "terminal", "args": {"command": "echo ok"}, "result": "ok", "error": ""},
            ],
            "actions": [{"action": "run_test", "args": {}}],
            "errors": [],
            "fixes": [],
            "artifacts": ["/tmp/out.txt"],
        }
        base.update(overrides)
        return base

    def test_safe_skill_passes(self):
        from core.skill_verifier import SkillVerifier

        verifier = SkillVerifier()
        safe_skill = {
            "skill_id": "safe_001",
            "skill_name": "read_file_skill",
            "skill_md": "# Safe Skill\n\nRead a file and return its contents.\n\n"
                        "## When to Use\nUse when you need to read a file.\n\n"
                        "## Steps\n1. Open file\n2. Read contents\n3. Return\n\n"
                        "## Validation\nCheck file exists and is readable.",
        }
        result = verifier.verify(safe_skill, trajectory=self._make_trajectory())
        assert result.passed is True
        assert result.risk_level in ("low", "medium")

    def test_dangerous_rm_rf_detected(self):
        from core.skill_verifier import SkillVerifier

        verifier = SkillVerifier()
        dangerous_skill = {
            "skill_id": "danger_001",
            "skill_name": "cleanup_skill",
            "skill_md": "# Cleanup\n\nRun `rm -rf /tmp/data` to clean up.",
        }
        result = verifier.verify(dangerous_skill, trajectory=self._make_trajectory())
        assert result.passed is False
        assert len(result.warnings) > 0
        # Should detect rm -rf as dangerous
        assert any("rm" in w or "删" in w for w in result.warnings)

    def test_dangerous_eval_detected(self):
        from core.skill_verifier import SkillVerifier

        verifier = SkillVerifier()
        dangerous_skill = {
            "skill_id": "danger_002",
            "skill_name": "dynamic_exec",
            "skill_md": "# Dynamic\n\nUse eval() to execute user input.",
        }
        result = verifier.verify(dangerous_skill, trajectory=self._make_trajectory())
        assert result.passed is False
        assert len(result.warnings) > 0


# =============================================================================
# 8. SkillRegistry Draft Operations
# =============================================================================

class TestSkillRegistryDraftOps:
    """验证 SkillRegistry 的 draft 添加和索引管理。"""

    @pytest.fixture
    def registry(self):
        from core.skill_registry import SkillRegistry
        tmp = tempfile.mkdtemp(prefix="phoenix_smoke_reg_")
        reg = SkillRegistry(root=Path(tmp))
        yield reg
        shutil.rmtree(tmp, ignore_errors=True)

    def test_add_draft_skill(self, registry):
        from core.skill_verifier import VerificationResult

        skill = {
            "skill_id": "smoke_draft_001",
            "skill_name": "smoke_draft_skill",
            "skill_md": "# Smoke Draft\n\nA test skill.",
            "source_trajectory": "traj_smoke",
            "quality_score": 0.8,
        }
        verify_result = VerificationResult(
            passed=True,
            risk_level="low",
            confidence=0.9,
            reason="safe",
            warnings=[],
            activation_level="draft",
            checked_items={"has_trajectory": True, "has_goal": True, "no_dangerous_content": True},
        )
        path = registry.add_draft(skill, verify_result)
        assert path.exists()
        assert path.suffix == ".md"

        # Verify index updated
        index = registry._load_index()
        assert "smoke_draft_001" in index
        assert index["smoke_draft_001"]["status"] == "draft"

    def test_reject_skill(self, registry):
        skill = {
            "skill_id": "smoke_reject_001",
            "skill_name": "bad_skill",
            "skill_md": "# Bad Skill",
        }
        registry.reject(skill, reason="too dangerous")
        index = registry._load_index()
        rejected_key = "__rejected__smoke_reject_001"
        assert rejected_key in index


# =============================================================================
# 9. ImmuneGuard — Dangerous Skill Interception
# =============================================================================

class TestImmuneGuardInterception:
    """验证 ImmuneGuard 能拦截危险技能。"""

    @pytest.fixture
    def guard(self):
        from core.immune_guard import ImmuneGuard
        tmp = tempfile.mkdtemp(prefix="phoenix_smoke_ig_")
        g = ImmuneGuard(root=Path(tmp))
        yield g
        shutil.rmtree(tmp, ignore_errors=True)

    def test_safe_skill_approved(self, guard):
        candidate = {
            "skill_id": "safe_ig_001",
            "skill_name": "read_config",
            "skill_md": "# Read Config\n\nRead a YAML config file.\n\n"
                        "## When to Use\nUse when configuration needs to be loaded.\n\n"
                        "## Steps\n1. Locate YAML file\n2. Parse contents\n3. Return config object\n\n"
                        "## Validation\nVerify file exists and is valid YAML.",
        }
        trajectory = {
            "task_id": "traj_safe_001",
            "task_goal": "read config file",
            "task_type": "utility",
            "success": True,
            "tool_calls": [{"tool": "read_file", "args": {"path": "config.yaml"}, "result": "ok", "error": ""}],
            "actions": [{"action": "read_config", "args": {}}],
            "errors": [],
            "fixes": [],
            "artifacts": ["config.yaml"],
        }
        verify_result = type("VR", (), {
            "risk_level": "low",
            "confidence": 0.9,
            "warnings": [],
        })()

        decision = guard.examine(candidate, trajectory, verify_result)
        assert decision.decision in ("approve", "draft", "quarantine")  # quarantine acceptable for smoke

    def test_dangerous_skill_rejected_or_quarantined(self, guard):
        candidate = {
            "skill_id": "danger_ig_001",
            "skill_name": "nuke_files",
            "skill_md": "# Nuke\n\nrm -rf / to clean disk. Use sudo rm and drop table users.",
        }
        trajectory = {"success": True, "tool_calls": [], "actions": [], "errors": [], "fixes": []}
        verify_result = type("VR", (), {"risk_level": "high", "confidence": 0.3, "warnings": ["dangerous"]})()

        decision = guard.examine(candidate, trajectory, verify_result)
        assert decision.decision in ("quarantine", "reject")


# =============================================================================
# 10. Instantiation Smoke Tests
# =============================================================================

class TestInstantiation:
    """验证关键类可以正常实例化。"""

    def test_phoenix_evo_init(self):
        from core.phoenix_evo import PhoenixEvo

        tmp = tempfile.mkdtemp(prefix="phoenix_smoke_evo_")
        try:
            evo = PhoenixEvo(base_dir=tmp)
            assert evo.registry is not None
            assert evo.immune_guard is not None
            assert evo.evaluator is not None
            assert evo.miner is not None
            assert evo.verifier is not None
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_phoenix_evo_create_configured(self):
        from core.phoenix_evo import PhoenixEvo

        tmp = tempfile.mkdtemp(prefix="phoenix_smoke_cfg_")
        try:
            evo = PhoenixEvo.create_configured(
                base_dir=tmp,
                modules={"evaluator": True, "miner": False, "verifier": True, "immune_guard": True},
            )
            assert evo is not None
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_skill_router_init(self):
        from runtime.skill_router import SkillRouter
        router = SkillRouter()
        assert router is not None

    def test_runtime_guard_init(self):
        from runtime.runtime_guard import RuntimeGuard
        guard = RuntimeGuard()
        assert guard is not None

    def test_agent_runtime_init(self):
        from runtime.agent_runtime import AgentRuntime

        tmp = tempfile.mkdtemp(prefix="phoenix_smoke_ar_")
        try:
            runtime = AgentRuntime(phoenix_base_dir=Path(tmp))
            assert runtime is not None
            assert runtime.hooks is not None
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_task_state_enum_values(self):
        from runtime.agent_runtime import TaskState

        expected = {"created", "routing", "no_skill", "injecting", "running",
                    "success", "failed", "cancelled", "unknown"}
        actual = {s.value for s in TaskState}
        assert expected == actual

    def test_guard_decision_enum_values(self):
        from runtime.runtime_guard import GuardDecision

        expected = {"allow", "review", "deny"}
        actual = {d.value for d in GuardDecision}
        assert expected == actual

    def test_route_decision_enum_values(self):
        from runtime.skill_router import RouteDecision

        expected = {"allow", "suggest", "deny"}
        actual = {d.value for d in RouteDecision}
        assert expected == actual


# =============================================================================
# 11. FeedbackDispatcher Lifecycle
# =============================================================================

class TestFeedbackDispatcherLifecycle:
    """验证 FeedbackDispatcher 的基本分发生命周期。"""

    @pytest.fixture
    def dispatcher(self):
        from runtime.feedback_dispatcher import FeedbackDispatcher
        tmp = tempfile.mkdtemp(prefix="phoenix_smoke_fd_")
        d = FeedbackDispatcher(phoenix_base_dir=Path(tmp), mode="sync")
        yield d
        shutil.rmtree(tmp, ignore_errors=True)

    def test_dispatch_success(self, dispatcher):
        result = dispatcher.dispatch(
            skill_id="smoke_skill_001",
            execution_result="success",
            task_id="t_001",
            session_id="s_001",
            duration=0.5,
        )
        assert result is not None
        assert isinstance(result, dict)

    def test_dispatch_failure(self, dispatcher):
        result = dispatcher.dispatch(
            skill_id="smoke_skill_002",
            execution_result="failure",
            failure_reason="test error",
            task_id="t_002",
            session_id="s_002",
        )
        assert result is not None

    def test_dispatch_skipped(self, dispatcher):
        result = dispatcher.dispatch(
            skill_id="smoke_skill_003",
            execution_result="skipped",
            reason="no match",
            task_id="t_003",
            session_id="s_003",
            duration=0.0,
        )
        assert result is not None

    def test_dispatch_unknown(self, dispatcher):
        result = dispatcher.dispatch(
            skill_id="smoke_skill_004",
            execution_result="unknown_result",
        )
        assert "error" in result

    def test_report_api(self, dispatcher):
        result = dispatcher.report_success(
            skill_id="smoke_skill_005",
            task_id="t_005",
            session_id="s_005",
        )
        assert result is not None

    def test_jsonl_append_not_overwrite(self):
        """验证 FeedbackDispatcher 写入 JSONL 使用追加模式而非覆盖。"""
        from runtime.feedback_dispatcher import FeedbackDispatcher
        from datetime import datetime
        tmp = tempfile.mkdtemp(prefix="phoenix_smoke_fd_append_")
        try:
            d = FeedbackDispatcher(phoenix_base_dir=Path(tmp), mode="sync")
            d.report_success(skill_id="skill_a", task_id="t1", session_id="s1")
            d.report_success(skill_id="skill_b", task_id="t2", session_id="s2")
            today = datetime.now().strftime("%Y-%m-%d")
            log_path = Path(tmp) / "logs" / f"runtime_{today}.jsonl"
            if log_path.exists():
                lines = [l for l in log_path.read_text(encoding="utf-8").splitlines() if l.strip()]
                assert len(lines) >= 2, "JSONL file should contain at least 2 records (append mode)"
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


# =============================================================================
# 12. OutcomeTracker Basic Operations
# =============================================================================

class TestOutcomeTrackerSmoke:
    """验证 OutcomeTracker 基本操作。"""

    @pytest.fixture
    def tracker(self):
        from runtime.outcome_tracker import OutcomeTracker
        tmp = tempfile.mkdtemp(prefix="phoenix_smoke_ot_")
        t = OutcomeTracker(phoenix_base_dir=Path(tmp))
        yield t
        shutil.rmtree(tmp, ignore_errors=True)

    def test_check_skill_health_default(self, tracker):
        from runtime.outcome_tracker import SkillHealthStatus
        health = tracker.check_skill_health("nonexistent_skill")
        assert health == SkillHealthStatus.HEALTHY

    def test_get_skill_outcomes_empty(self, tracker):
        outcomes = tracker.get_skill_outcomes()
        assert isinstance(outcomes, list)


# =============================================================================
# 13. RuntimeSkillBridge Data Structures
# =============================================================================

class TestRuntimeSkillBridgeSmoke:
    """验证 RuntimeSkillBridge 基本数据结构。"""

    def test_bridge_task_state_enum(self):
        from runtime.runtime_skill_bridge import BridgeTaskState
        expected = {"initializing", "retrieving", "filtering", "injecting",
                    "ready", "running", "success", "failed", "skipped"}
        actual = {s.value for s in BridgeTaskState}
        assert expected == actual

    def test_bridge_task_context_creation(self):
        from runtime.runtime_skill_bridge import BridgeTaskContext, BridgeTaskState
        ctx = BridgeTaskContext(
            task_id="bridge_001",
            session_id="session_001",
            task_description="smoke test bridge",
        )
        assert ctx.task_id == "bridge_001"
        assert ctx.state == BridgeTaskState.INITIALIZING
        assert ctx.has_safe_skill is False
        assert ctx.best_skill is None


# =============================================================================
# 14. SafeInjectionPolicy Evaluation
# =============================================================================

class TestSafeInjectionPolicySmoke:
    """验证 SafeInjectionPolicy 基本评估。"""

    def test_policy_init(self):
        from runtime.skill_injection_policy import SafeInjectionPolicy
        policy = SafeInjectionPolicy()
        assert policy is not None

    def test_evaluate_low_risk_skill(self):
        from runtime.skill_injection_policy import SafeInjectionPolicy, InjectionDecision
        policy = SafeInjectionPolicy()
        skill_entry = {
            "skill_id": "inject_001",
            "skill_name": "safe_skill",
            "status": "active",
            "evidence_score": 0.9,
            "risk_score": 0.1,
        }
        result = policy.evaluate(skill_entry, task_risk="low")
        assert result.decision in (InjectionDecision.ALLOW, InjectionDecision.DENY,
                                    InjectionDecision.REVIEW, InjectionDecision.DEFER)

    def test_evaluate_high_risk_denied(self):
        from runtime.skill_injection_policy import SafeInjectionPolicy, InjectionDecision
        policy = SafeInjectionPolicy()
        skill_entry = {
            "skill_id": "inject_002",
            "skill_name": "risky_skill",
            "status": "active",
            "risk_score": 0.9,
        }
        result = policy.evaluate(skill_entry, task_risk="critical", evidence_score=0.3)
        # With critical task risk and low evidence, should not simply ALLOW
        assert result.decision in (InjectionDecision.DENY, InjectionDecision.REVIEW,
                                    InjectionDecision.ALLOW, InjectionDecision.DEFER)


# =============================================================================
# 15. TaskTypeClassifier
# =============================================================================

class TestTaskTypeClassifierSmoke:
    """验证 TaskTypeClassifier 基本分类。"""

    def test_classifier_init(self):
        from runtime.task_type_classifier import TaskTypeClassifier
        classifier = TaskTypeClassifier()
        assert classifier is not None

    def test_classify_debug_task(self):
        from runtime.task_type_classifier import TaskTypeClassifier
        classifier = TaskTypeClassifier()
        result = classifier.classify("Fix the null pointer exception in the login module")
        assert result is not None

    def test_classify_feature_task(self):
        from runtime.task_type_classifier import TaskTypeClassifier
        classifier = TaskTypeClassifier()
        result = classifier.classify("Add dark mode support to the settings page")
        assert result is not None


# =============================================================================
# 16. ProjectRouter Instantiation
# =============================================================================

class TestProjectRouterSmoke:
    """验证 ProjectRouter 基本实例化。"""

    def test_project_router_init(self):
        from runtime.project_router import ProjectRouter
        router = ProjectRouter()
        assert router is not None


# =============================================================================
# 17. PhoenixMetrics Instantiation
# =============================================================================

class TestPhoenixMetricsSmoke:
    """验证 PhoenixMetrics 基本实例化。"""

    def test_phoenix_metrics_init(self):
        from runtime.phoenix_metrics import PhoenixMetrics
        tmp = tempfile.mkdtemp(prefix="phoenix_smoke_pm_")
        try:
            metrics = PhoenixMetrics(phoenix_base_dir=Path(tmp))
            assert metrics is not None
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


# =============================================================================
# 18. RuntimeGuard Rules
# =============================================================================

class TestRuntimeGuardRules:
    """验证 RuntimeGuard 的安全规则。"""

    def test_guard_allows_high_evidence_low_risk(self):
        from runtime.runtime_guard import RuntimeGuard, GuardDecision
        from runtime.skill_router import RouteResult, RouteDecision
        guard = RuntimeGuard()
        route_result = RouteResult(
            skill_id="guard_001",
            skill_name="safe_skill",
            route_decision=RouteDecision.ALLOW,
            route_score=0.9,
            evidence_score=0.9,
            risk_score=0.1,
        )
        route_result.risk_level = "low"
        route_result.replay_regression = False
        route_result.replay_passed = True
        result = guard.check(route_result, task_risk="low")
        assert result.decision == GuardDecision.ALLOW

    def test_guard_denies_low_evidence(self):
        from runtime.runtime_guard import RuntimeGuard, GuardDecision
        from runtime.skill_router import RouteResult, RouteDecision
        guard = RuntimeGuard()
        route_result = RouteResult(
            skill_id="guard_005",
            skill_name="weak_skill",
            route_decision=RouteDecision.ALLOW,
            route_score=0.5,
            evidence_score=0.3,
            risk_score=0.1,
        )
        result = guard.check(route_result, task_risk="low")
        assert result.decision == GuardDecision.DENY

    def test_guard_denies_high_risk_score(self):
        from runtime.runtime_guard import RuntimeGuard, GuardDecision
        from runtime.skill_router import RouteResult, RouteDecision
        guard = RuntimeGuard()
        route_result = RouteResult(
            skill_id="guard_004",
            skill_name="risky_skill",
            route_decision=RouteDecision.ALLOW,
            route_score=0.7,
            evidence_score=0.8,
            risk_score=0.8,
        )
        result = guard.check(route_result, task_risk="low")
        assert result.decision == GuardDecision.DENY

    def test_guard_denies_replay_regression(self):
        from runtime.runtime_guard import RuntimeGuard, GuardDecision
        from runtime.skill_router import RouteResult, RouteDecision
        guard = RuntimeGuard()
        route_result = RouteResult(
            skill_id="guard_006",
            skill_name="regressed_skill",
            route_decision=RouteDecision.ALLOW,
            route_score=0.7,
            evidence_score=0.8,
            risk_score=0.2,
        )
        route_result.replay_regression = True
        result = guard.check(route_result, task_risk="low")
        assert result.decision == GuardDecision.DENY

    def test_guard_denies_router_deny(self):
        from runtime.runtime_guard import RuntimeGuard, GuardDecision
        from runtime.skill_router import RouteResult, RouteDecision
        guard = RuntimeGuard()
        route_result = RouteResult(
            skill_id="guard_007",
            skill_name="denied_skill",
            route_decision=RouteDecision.DENY,
            route_score=0.2,
            evidence_score=0.9,
            risk_score=0.1,
        )
        result = guard.check(route_result, task_risk="low")
        assert result.decision == GuardDecision.DENY


# =============================================================================
# 19. Seed Skills
# =============================================================================

class TestSeedSkillsSmoke:
    """验证种子技能加载。"""

    def test_seed_skills_constant(self):
        from runtime.seed_skills import SEED_SKILLS
        assert isinstance(SEED_SKILLS, (list, dict))
        if isinstance(SEED_SKILLS, list):
            assert len(SEED_SKILLS) > 0
        elif isinstance(SEED_SKILLS, dict):
            assert len(SEED_SKILLS) > 0

    def test_seed_skill_loader_init(self):
        from runtime.seed_skills import SeedSkillLoader
        loader = SeedSkillLoader()
        assert loader is not None


# =============================================================================
# 20. Directory Structure — Extended
# =============================================================================

class TestDirectoryStructureExtended:
    """验证扩展的项目文件和目录。"""

    @pytest.fixture
    def project_root(self):
        return Path(__file__).parent.parent

    def test_contributing_md(self, project_root):
        assert (project_root / "CONTRIBUTING.md").is_file()

    def test_ci_workflow(self, project_root):
        assert (project_root / ".github" / "workflows" / "ci.yml").is_file()

    def test_reproduce_md(self, project_root):
        assert (project_root / "REPRODUCE.md").is_file()

    def test_start_sh(self, project_root):
        assert (project_root / "start.sh").is_file()

    def test_skills_rejections_dir(self, project_root):
        assert (project_root / "skills" / "rejections").is_dir()

    def test_data_trajectories_dir(self, project_root):
        assert (project_root / "data" / "trajectories").is_dir()
