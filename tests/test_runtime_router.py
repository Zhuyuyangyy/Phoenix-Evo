"""
Phoenix-Evo V0.5 Runtime Skill Router 测试套件
=============================================

覆盖模块：
  1. skill_retriever   — 多路召回 + 多维评分排序
  2. skill_router      — 路由决策引擎（auto/confirm/review/blocked）
  3. execution_guard   — 调用前安全闸门
  4. fallback_manager  — 调用失败回退管理
  5. runtime_reporter  — 运行时记录与效果报告

V0.5 核心验证点：
  - retrieve(task_goal) 返回按综合评分排序的 top-k 候选
  - router.route() 正确路由：auto_use / confirm_use / review_first / blocked
  - execution_guard.check() 对 destructive 操作做 block
  - fallback_manager 失败 2 次自动降级 quarantine
  - runtime_reporter 生成含 step_delta / improvement 的报告
"""

import json
import shutil
from datetime import datetime, timedelta

import pytest

# --------------------------------------------------------------------------
# Fixtures
# --------------------------------------------------------------------------

@pytest.fixture
def v05_root(tmp_path):
    """构建 V0.5 完整目录结构。"""
    root = tmp_path / "phoenix-evo-v05"
    for d in [
        root / "core",
        root / "skills" / "draft",
        root / "skills" / "active",
        root / "skills" / "archived",
        root / "skills" / "quarantine",
        root / "evidence" / "skill_cards",
        root / "evidence" / "replay_reports",
        root / "evidence" / "runtime_logs",
        root / "runtime" / "fallback_logs",
    ]:
        d.mkdir(parents=True, exist_ok=True)

    # skill_index.json：4 个不同状态的技能
    index = {
        "skill_active_good": {
            "skill_id": "skill_active_good",
            "skill_name": "修复WSL中文路径null字节",
            "status": "active",
            "source_trajectory": "traj_001",
            "task_goal": "修复 WSL 中文路径写入 null 字节",
            "tags": ["wsl", "patch", "encoding"],
            "inputs": ["file_path"],
            "quality_score": 0.9,
            "risk_level": "low",
            "confidence": 0.95,
            "usage_count": 5,
            "success_count": 5,
            "success_rate": 1.0,
            "created_at": (datetime.now() - timedelta(days=10)).isoformat(),
            "last_used": (datetime.now() - timedelta(days=2)).isoformat(),
            "promotion_ready": True,
        },
        "skill_active_risky": {
            "skill_id": "skill_active_risky",
            "skill_name": "执行系统命令",
            "status": "active",
            "source_trajectory": "traj_002",
            "task_goal": "在服务器执行 shell 命令",
            "tags": ["shell", "exec", "dangerous"],
            "inputs": ["command"],
            "quality_score": 0.7,
            "risk_level": "high",
            "confidence": 0.8,
            "usage_count": 3,
            "success_count": 2,
            "success_rate": 0.67,
            "created_at": (datetime.now() - timedelta(days=30)).isoformat(),
            "last_used": (datetime.now() - timedelta(days=15)).isoformat(),
            "promotion_ready": False,
        },
        "skill_draft_new": {
            "skill_id": "skill_draft_new",
            "skill_name": "处理 Unicode 编码错误",
            "status": "draft",
            "source_trajectory": "traj_003",
            "task_goal": "修复 Python Unicode 编码错误",
            "tags": ["python", "encoding", "unicode"],
            "inputs": ["text"],
            "quality_score": 0.75,
            "risk_level": "low",
            "confidence": 0.85,
            "usage_count": 0,
            "success_count": 0,
            "success_rate": None,
            "created_at": datetime.now().isoformat(),
            "last_used": None,
            "promotion_ready": False,
        },
        "skill_quarantine_bad": {
            "skill_id": "skill_quarantine_bad",
            "skill_name": "危险权限操作",
            "status": "quarantine",
            "source_trajectory": "traj_004",
            "task_goal": "执行 sudo 权限命令",
            "tags": ["sudo", "privilege"],
            "quality_score": 0.3,
            "risk_level": "critical",
            "confidence": 0.4,
            "usage_count": 1,
            "success_count": 0,
            "success_rate": 0.0,
            "created_at": (datetime.now() - timedelta(days=60)).isoformat(),
            "last_used": None,
            "promotion_ready": False,
        },
    }
    (root / "skills" / "skill_index.json").write_text(
        json.dumps(index, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    # evidence card for skill_active_good
    card = {
        "skill_id": "skill_active_good",
        "skill_name": "修复WSL中文路径null字节",
        "source_trajectory_ids": ["traj_001"],
        "evidence_type": "successful_trajectory",
        "status": "replay_pass",
        "risk_level": "low",
        "quality_score": 0.9,
        "created_at": (datetime.now() - timedelta(days=10)).isoformat(),
        "verified_by": ["skill_verifier", "immune_guard"],
        "replay_report_ids": ["replay_skill_active_good_001"],
        "replay_pass_count": 3,
        "replay_fail_count": 0,
        "promotion_ready": True,
        "task_goal": "修复 WSL 中文路径写入 null 字节",
        "procedure_steps": 3,
        "tags": ["wsl", "patch", "encoding"],
    }
    (root / "evidence" / "skill_cards" / "skill_active_good.card.json").write_text(
        json.dumps(card, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    # replay report for skill_active_good
    report = {
        "report_id": "replay_skill_active_good_001",
        "skill_id": "skill_active_good",
        "replayed_at": (datetime.now() - timedelta(days=1)).isoformat(),
        "total_cases": 5,
        "passed_cases": 5,
        "overall_pass": True,
        "success_delta": 0.3,
        "error_delta": -0.2,
        "risk_delta": -0.05,
        "regression_found": False,
        "step_delta": -1.5,
        "recommendation": "promote",
        "results": [],
    }
    (root / "evidence" / "replay_reports" / "replay_skill_active_good_001.report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    yield root, index
    shutil.rmtree(root, ignore_errors=True)


# ==========================================================================
# Test 1: skill_retriever
# ==========================================================================

class TestSkillRetriever:
    """skill_retriever 模块测试。"""

    def test_retrieve_returns_top_k(self, v05_root):
        """retrieve() 应返回 top-k 个候选。"""
        from core.skill_retriever import SkillRetriever
        root, index = v05_root
        retriever = SkillRetriever(root=root)
        result = retriever.retrieve("修复 WSL 中文路径 null 字节", top_k=3)
        assert len(result.matches) <= 3
        assert result.task_goal == "修复 WSL 中文路径 null 字节"
        assert result.total_candidates == 4
        assert result.retrieval_time_ms >= 0

    def test_quarantine_skills_excluded(self, v05_root):
        """quarantine 状态技能不应被召回。"""
        from core.skill_retriever import SkillRetriever
        root, index = v05_root
        retriever = SkillRetriever(root=root)
        result = retriever.retrieve("修复 WSL 中文路径", top_k=5)
        skill_ids = [m.skill_id for m in result.matches]
        assert "skill_quarantine_bad" not in skill_ids

    def test_active_skill_ranked_highest(self, v05_root):
        """evidence + replay 完整的 active 技能应排名最高。"""
        from core.skill_retriever import SkillRetriever
        root, index = v05_root
        retriever = SkillRetriever(root=root)
        result = retriever.retrieve("WSL 路径 修复", top_k=3)
        if result.matches:
            top = result.matches[0]
            assert top.risk_level in ("low", "medium")

    def test_retrieve_by_keyword_match(self, v05_root):
        """关键词匹配应返回相关技能。"""
        from core.skill_retriever import SkillRetriever
        root, index = v05_root
        retriever = SkillRetriever(root=root)
        result = retriever.retrieve("Python Unicode 编码错误", top_k=5)
        skill_ids = [m.skill_id for m in result.matches]
        assert "skill_draft_new" in skill_ids

    def test_retrieve_empty_task_goal(self, v05_root):
        """空任务描述应返回空结果或不崩溃。"""
        from core.skill_retriever import SkillRetriever
        root, index = v05_root
        retriever = SkillRetriever(root=root)
        result = retriever.retrieve("", top_k=5)
        assert isinstance(result.matches, list)

    def test_evidence_score_read_from_card(self, v05_root):
        """有 skill_card 的技能 evidence_score 应 > 0。"""
        from core.skill_retriever import SkillRetriever
        root, index = v05_root
        retriever = SkillRetriever(root=root)
        result = retriever.retrieve("WSL 修复", top_k=5)
        if "skill_active_good" in {m.skill_id for m in result.matches}:
            match = next(m for m in result.matches if m.skill_id == "skill_active_good")
            assert match.evidence_score > 0

    def test_replay_info_read_from_report(self, v05_root):
        """有 replay_report 的技能 replay_pass_rate 应 > 0。"""
        from core.skill_retriever import SkillRetriever
        root, index = v05_root
        retriever = SkillRetriever(root=root)
        result = retriever.retrieve("WSL 修复", top_k=5)
        match = next((m for m in result.matches if m.skill_id == "skill_active_good"), None)
        if match:
            assert match.replay_pass_rate == 1.0
            assert match.replay_passed is True


# ==========================================================================
# Test 2: skill_router
# ==========================================================================

class TestSkillRouter:
    """skill_router 模块测试。"""

    def _make_retrieval_result(self, matches):
        from core.skill_retriever import SkillRetrievalResult
        return SkillRetrievalResult(
            task_goal="test task", top_k=5,
            total_candidates=len(matches), matches=matches, retrieval_time_ms=1.0,
        )

    def test_auto_use_requires_all_conditions(self, v05_root):
        """evidence>=0.6 + replay>=0.70 + risk low + promotion_ready → auto_use。"""
        from core.skill_retriever import RetrievalMatch
        from core.skill_router import SkillRouter
        root, index = v05_root
        router = SkillRouter(root=root)
        match = RetrievalMatch(
            skill_id="skill_001", skill_name="完美技能", status="active",
            similarity_score=0.9, evidence_score=1.0, replay_pass_rate=1.0,
            replay_passed=True, promotion_ready=True, risk_level="low",
            source_trajectory="traj_001", reason="完美匹配",
        )
        result = router.route(self._make_retrieval_result([match]))
        assert len(result.auto_use) == 1
        assert result.auto_use[0].action == "auto_use"

    def test_confirm_use_for_medium_confidence(self, v05_root):
        """evidence=0.5, replay=0.6, medium risk → confirm_use。"""
        from core.skill_retriever import RetrievalMatch
        from core.skill_router import SkillRouter
        root, index = v05_root
        router = SkillRouter(root=root)
        match = RetrievalMatch(
            skill_id="skill_002", skill_name="中等技能", status="active",
            similarity_score=0.7, evidence_score=0.5, replay_pass_rate=0.6,
            replay_passed=True, promotion_ready=False, risk_level="medium",
            source_trajectory="traj_002", reason="部分匹配",
        )
        result = router.route(self._make_retrieval_result([match]))
        assert len(result.confirm_use) == 1
        assert result.confirm_use[0].action == "confirm_use"

    def test_review_first_for_low_evidence(self, v05_root):
        """evidence=0.3, replay=0.4 → review_first。"""
        from core.skill_retriever import RetrievalMatch
        from core.skill_router import SkillRouter
        root, index = v05_root
        router = SkillRouter(root=root)
        match = RetrievalMatch(
            skill_id="skill_003", skill_name="低证据技能", status="draft",
            similarity_score=0.5, evidence_score=0.3, replay_pass_rate=0.4,
            replay_passed=None, promotion_ready=False, risk_level="low",
            source_trajectory="traj_003", reason="证据不足",
        )
        result = router.route(self._make_retrieval_result([match]))
        assert len(result.review_first) == 1
        assert result.review_first[0].action == "review_first"

    def test_blocked_for_critical_risk(self, v05_root):
        """critical 风险 → blocked。"""
        from core.skill_retriever import RetrievalMatch
        from core.skill_router import SkillRouter
        root, index = v05_root
        router = SkillRouter(root=root)
        match = RetrievalMatch(
            skill_id="skill_004", skill_name="危险技能", status="quarantine",
            similarity_score=0.9, evidence_score=0.2, replay_pass_rate=0.0,
            replay_passed=False, promotion_ready=False, risk_level="critical",
            source_trajectory="traj_004", reason="critical 风险",
        )
        result = router.route(self._make_retrieval_result([match]))
        assert len(result.blocked) == 1
        assert result.blocked[0].action == "blocked"

    def test_high_risk_without_replay_blocked(self, v05_root):
        """高风险且回放未通过 → blocked。"""
        from core.skill_retriever import RetrievalMatch
        from core.skill_router import SkillRouter
        root, index = v05_root
        router = SkillRouter(root=root)
        match = RetrievalMatch(
            skill_id="skill_005", skill_name="高风险技能", status="active",
            similarity_score=0.7, evidence_score=0.5, replay_pass_rate=0.2,
            replay_passed=False, promotion_ready=False, risk_level="high",
            source_trajectory="traj_005", reason="高风险无回放",
        )
        result = router.route(self._make_retrieval_result([match]))
        assert len(result.blocked) == 1

    def test_multiple_skills_routed_correctly(self, v05_root):
        """多个技能应按各自的决策分类。"""
        from core.skill_retriever import RetrievalMatch
        from core.skill_router import SkillRouter
        root, index = v05_root
        router = SkillRouter(root=root)
        matches = [
            RetrievalMatch(skill_id="s1", skill_name="完美", status="active", similarity_score=0.9,
                           evidence_score=0.9, replay_pass_rate=0.9, replay_passed=True,
                           promotion_ready=True, risk_level="low", source_trajectory="t1", reason=""),
            RetrievalMatch(skill_id="s2", skill_name="中等", status="active", similarity_score=0.7,
                           evidence_score=0.5, replay_pass_rate=0.6, replay_passed=True,
                           promotion_ready=False, risk_level="medium", source_trajectory="t2", reason=""),
            RetrievalMatch(skill_id="s3", skill_name="危险", status="quarantine", similarity_score=0.5,
                           evidence_score=0.2, replay_pass_rate=0.0, replay_passed=False,
                           promotion_ready=False, risk_level="critical", source_trajectory="t3", reason=""),
        ]
        result = router.route(self._make_retrieval_result(matches))
        assert len(result.auto_use) == 1
        assert len(result.confirm_use) == 1
        assert len(result.blocked) == 1
        assert result.total_considered == 3

    def test_format_routing_summary(self, v05_root):
        """format_routing_summary() 返回可读摘要。"""
        from core.skill_retriever import RetrievalMatch, SkillRetrievalResult
        from core.skill_router import SkillRouter
        root, index = v05_root
        router = SkillRouter(root=root)
        match = RetrievalMatch(
            skill_id="skill_001", skill_name="测试技能", status="active",
            similarity_score=0.9, evidence_score=0.8, replay_pass_rate=0.9,
            replay_passed=True, promotion_ready=True, risk_level="low",
            source_trajectory="t1", reason="完美匹配",
        )
        retrieval = SkillRetrievalResult(
            task_goal="test task", top_k=5, total_candidates=1,
            matches=[match], retrieval_time_ms=1.0,
        )
        result = router.route(retrieval)
        summary = router.format_routing_summary(result)
        assert "SkillRouter" in summary


# ==========================================================================
# Test 3: execution_guard
# ==========================================================================

class TestExecutionGuard:
    """execution_guard 模块测试。"""

    def test_pass_for_good_skill(self, v05_root):
        """低风险、高置信技能应通过闸门。"""
        from core.execution_guard import ExecutionGuard
        from core.skill_router import RouterDecision
        root, index = v05_root
        guard = ExecutionGuard(root=root)
        skill = {
            "skill_id": "skill_001",
            "skill_name": "测试技能",
            "risk_level": "low",
            "task_goal": "修复 WSL 中文路径 null 字节问题",
            "procedure": ["step1", "step2"],
        }
        decision = RouterDecision(skill_id="skill_001", skill_name="测试", action="auto_use", confidence=0.85)
        result = guard.check(skill, decision)
        assert result.passed is True
        assert result.gate_action in ("pass", "warn")

    def test_block_low_confidence(self, v05_root):
        """置信度 < 20% → block。"""
        from core.execution_guard import ExecutionGuard
        from core.skill_router import RouterDecision
        root, index = v05_root
        guard = ExecutionGuard(root=root)
        skill = {"skill_id": "skill_001", "skill_name": "低置信技能", "risk_level": "low"}
        decision = RouterDecision(skill_id="skill_001", skill_name="低置信", action="auto_use", confidence=0.1)
        result = guard.check(skill, decision)
        assert result.passed is False
        assert result.gate_action == "block"

    def test_block_destructive_operation(self, v05_root):
        """检测到 destructive 操作 → block。"""
        from core.execution_guard import ExecutionGuard
        from core.skill_router import RouterDecision
        root, index = v05_root
        guard = ExecutionGuard(root=root)
        skill = {
            "skill_id": "skill_001", "skill_name": "危险技能",
            "risk_level": "low",
            "procedure": ["确认删除", "执行 rm -rf /backup"],
        }
        decision = RouterDecision(skill_id="skill_001", skill_name="危险", action="auto_use", confidence=0.85)
        result = guard.check(skill, decision)
        assert result.passed is False
        assert result.gate_action == "block"

    def test_warn_on_context_mismatch(self, v05_root):
        """任务与技能上下文完全不匹配 → warn 或 block。"""
        from core.execution_guard import ExecutionGuard
        from core.skill_router import RouterDecision
        root, index = v05_root
        guard = ExecutionGuard(root=root)
        skill = {
            "skill_id": "skill_001", "skill_name": "WSL 路径修复",
            "risk_level": "low", "task_goal": "修复 WSL 中文路径 null 字节", "procedure": ["step1"],
        }
        decision = RouterDecision(skill_id="skill_001", skill_name="WSL", action="auto_use", confidence=0.85)
        task_context = {"task_goal": "修复 Git 提交信息格式", "risk_level": "low"}
        result = guard.check(skill, decision, task_context=task_context)
        assert result.gate_action in ("warn", "block")

    def test_block_double_high_risk(self, v05_root):
        """技能 high + 任务 high → block。"""
        from core.execution_guard import ExecutionGuard
        from core.skill_router import RouterDecision
        root, index = v05_root
        guard = ExecutionGuard(root=root)
        skill = {
            "skill_id": "skill_001",
            "skill_name": "高风险技能",
            "risk_level": "high",
            "task_goal": "执行高风险系统命令",
            "procedure": ["step1"],
        }
        decision = RouterDecision(skill_id="skill_001", skill_name="高风险", action="confirm_use", confidence=0.7)
        task_context = {"task_goal": "执行高风险系统命令", "risk_level": "high"}
        result = guard.check(skill, decision, task_context=task_context)
        assert result.passed is False
        assert result.gate_action == "block"


# ==========================================================================
# Test 4: fallback_manager
# ==========================================================================

class TestFallbackManager:
    """fallback_manager 模块测试。"""

    def test_first_timeout_allows_retry(self, v05_root):
        """首次超时 → retry。"""
        from core.fallback_manager import FallbackManager
        root, index = v05_root
        fm = FallbackManager(root=root)
        action = fm.handle_failure("skill_001", "timeout", "连接超时")
        assert action.retry_allowed is True
        assert action.retry_after_sec == 30
        assert action.action == "retry"

    def test_consecutive_timeout_triggers_degrade(self, v05_root):
        """连续 2 次超时 → 降级 quarantine。"""
        from core.fallback_manager import FallbackManager
        root, index = v05_root
        fm = FallbackManager(root=root)
        fm.handle_failure("skill_001", "timeout", "超时1")
        action = fm.handle_failure("skill_001", "timeout", "超时2")
        assert action.action == "degrade"
        assert action.degraded_to == "quarantine"
        assert action.escalate is True

    def test_high_risk_skill_fails_once_degraded(self, v05_root):
        """高风险技能失败 1 次 → 立即降级。"""
        from core.fallback_manager import FallbackManager
        root, index = v05_root
        fm = FallbackManager(root=root)
        skill_path = root / "skills" / "skill_index.json"
        idx = json.loads(skill_path.read_text(encoding="utf-8"))
        idx["skill_001"] = {"skill_id": "skill_001", "risk_level": "high", "status": "active"}
        skill_path.write_text(json.dumps(idx, ensure_ascii=False))
        action = fm.handle_failure("skill_001", "error", "执行失败")
        assert action.action == "degrade"
        assert action.degraded_to == "quarantine"

    def test_success_updates_stats(self, v05_root):
        """调用成功 → 更新 usage_count + success_count。"""
        from core.fallback_manager import FallbackManager
        root, index = v05_root
        fm = FallbackManager(root=root)
        skill_path = root / "skills" / "skill_index.json"
        idx = json.loads(skill_path.read_text(encoding="utf-8"))
        idx["skill_001"] = {"skill_id": "skill_001", "status": "active", "usage_count": 2, "success_count": 2, "success_rate": 1.0}
        skill_path.write_text(json.dumps(idx, ensure_ascii=False))
        fm.handle_success("skill_001")
        updated = json.loads(skill_path.read_text(encoding="utf-8"))
        assert updated["skill_001"]["usage_count"] == 3
        assert updated["skill_001"]["success_count"] == 3

    def test_context_mismatch_no_retry(self, v05_root):
        """上下文不匹配 → use_manual，不重试。"""
        from core.fallback_manager import FallbackManager
        root, index = v05_root
        fm = FallbackManager(root=root)
        action = fm.handle_failure("skill_001", "context_mismatch", "上下文不匹配")
        assert action.retry_allowed is False
        assert action.action == "use_manual"

    def test_get_fallback_chain(self, v05_root):
        """get_fallback_chain() 返回优先级排序的回退候选。"""
        from core.fallback_manager import FallbackManager
        root, index = v05_root
        fm = FallbackManager(root=root)
        all_skills = [
            {"skill_id": "s1", "status": "active", "evidence_score": 0.9, "usage_count": 3},
            {"skill_id": "s2", "status": "draft", "evidence_score": 0.6, "usage_count": 0},
            {"skill_id": "s3", "status": "archived", "evidence_score": 0.3, "usage_count": 10},
        ]
        chain = fm.get_fallback_chain("s_main", all_skills)
        assert chain[0]["skill_id"] == "s1"
        assert all(s["status"] != "archived" for s in chain)


# ==========================================================================
# Test 5: runtime_reporter
# ==========================================================================

class TestRuntimeReporter:
    """runtime_reporter 模块测试。"""

    def test_create_report_generates_runtime_report(self, v05_root):
        """create_report() 应生成含 step_delta 和 improvement 的报告。"""
        from core.runtime_reporter import RuntimeReporter, SkillInvocation
        from core.skill_retriever import SkillRetrievalResult
        from core.skill_router import RouterDecision, RouterResult
        root, index = v05_root
        reporter = RuntimeReporter(root=root)
        inv = SkillInvocation(
            skill_id="skill_001", skill_name="测试技能", action="auto_use",
            confidence=0.85, guard_passed=True, called=True, success=True, execution_time_ms=150.0,
        )
        SkillRetrievalResult(task_goal="test", top_k=5, total_candidates=5, matches=[], retrieval_time_ms=2.0)
        routing = RouterResult(
            task_goal="test",
            auto_use=[RouterDecision(skill_id="skill_001", skill_name="测试", action="auto_use", confidence=0.85)],
            confirm_use=[], review_first=[], blocked=[], total_considered=5, routing_time_ms=1.0,
        )
        report = reporter.create_report(
            task_goal="test task", task_id="task_001", retrieval_count=5,
            routing_result=routing, invocations=[inv], execution_time_ms=200.0,
            task_success=True, baseline_steps=10, actual_steps=7,
        )
        assert report.task_success is True
        assert report.skill_reused is True
        assert report.step_delta == -3.0
        assert report.improvement_over_baseline == 0.3

    def test_save_and_load_report(self, v05_root):
        """报告应能保存到 evidence/runtime_logs/。"""
        from core.runtime_reporter import RuntimeReporter
        from core.skill_retriever import SkillRetrievalResult
        from core.skill_router import RouterResult
        root, index = v05_root
        reporter = RuntimeReporter(root=root)
        SkillRetrievalResult(task_goal="t", top_k=3, total_candidates=3, matches=[], retrieval_time_ms=1.0)
        routing = RouterResult(task_goal="t", total_considered=3, routing_time_ms=1.0)
        report = reporter.create_report(
            task_goal="test", task_id="task_001", retrieval_count=3,
            routing_result=routing, invocations=[], execution_time_ms=100.0, task_success=True,
        )
        path = reporter.save_report(report)
        assert path.exists()

    def test_batch_summary(self, v05_root):
        """批量汇总应返回关键指标。"""
        from core.runtime_reporter import RuntimeReporter, SkillInvocation
        from core.skill_retriever import SkillRetrievalResult
        from core.skill_router import RouterDecision, RouterResult
        root, index = v05_root
        reporter = RuntimeReporter(root=root)
        for i in range(3):
            SkillRetrievalResult(task_goal=f"t{i}", top_k=3, total_candidates=3, matches=[], retrieval_time_ms=1.0)
            routing = RouterResult(
                task_goal=f"t{i}",
                auto_use=[RouterDecision(skill_id=f"s{i}", skill_name=f"s{i}", action="auto_use", confidence=0.8)],
                total_considered=3, routing_time_ms=1.0,
            )
            inv = SkillInvocation(skill_id=f"s{i}", skill_name=f"s{i}", action="auto_use", confidence=0.8, called=True, success=True)
            reporter.create_report(
                task_goal=f"task {i}", task_id=f"task_{i:03d}",
                retrieval_count=3, routing_result=routing,
                invocations=[inv], execution_time_ms=100.0, task_success=(i % 2 == 0),
            )
        summary = reporter.get_batch_summary(limit=10)
        assert summary["total_runs"] == 3
        assert summary["skill_reuse_rate"] == 1.0

    def test_format_report_markdown(self, v05_root):
        """format_report_markdown() 返回 markdown 文本。"""
        from core.runtime_reporter import RuntimeReporter, SkillInvocation
        from core.skill_retriever import SkillRetrievalResult
        from core.skill_router import RouterResult
        root, index = v05_root
        reporter = RuntimeReporter(root=root)
        SkillRetrievalResult(task_goal="test", top_k=3, total_candidates=3, matches=[], retrieval_time_ms=1.0)
        routing = RouterResult(task_goal="test", total_considered=3, routing_time_ms=1.0)
        inv = SkillInvocation(skill_id="s1", skill_name="技能1", action="auto_use", confidence=0.85, called=True, success=True)
        report = reporter.create_report(
            task_goal="测试任务", task_id="t001",
            retrieval_count=3, routing_result=routing,
            invocations=[inv], execution_time_ms=200.0, task_success=True,
        )
        md = reporter.format_report_markdown(report)
        assert "# Runtime Report" in md


# ==========================================================================
# Test 6: End-to-end workflow
# ==========================================================================

class TestRuntimeE2E:
    """端到端测试：retrieve → route → guard → fallback。"""

    def test_retrieve_route_guard_chain(self, v05_root):
        """完整链路：retrieve → route → guard。"""
        from core.execution_guard import ExecutionGuard
        from core.skill_retriever import SkillRetriever
        from core.skill_router import SkillRouter
        root, index = v05_root
        retriever = SkillRetriever(root=root)
        router = SkillRouter(root=root)
        guard = ExecutionGuard(root=root)

        retrieval = retriever.retrieve("修复 WSL 中文路径 null 字节", top_k=3)
        assert retrieval.total_candidates == 4
        assert len(retrieval.matches) <= 3

        routing = router.route(retrieval)
        assert isinstance(routing.selected_skills, list)

        for decision in routing.auto_use:
            match = next((m for m in retrieval.matches if m.skill_id == decision.skill_id), None)
            if match:
                skill = {
                    "skill_id": match.skill_id, "skill_name": match.skill_name,
                    "risk_level": match.risk_level, "procedure": ["step1"],
                }
                gate_result = guard.check(skill, decision)
                assert gate_result.skill_id == decision.skill_id

    def test_fallback_on_repeated_failure(self, v05_root):
        """连续失败应触发降级。"""
        from core.fallback_manager import FallbackManager
        root, index = v05_root
        fm = FallbackManager(root=root)
        for i in range(3):
            fm.handle_failure("skill_001", "error", f"错误{i+1}")
        stats = fm.get_failure_stats("skill_001")
        assert stats["failures"] >= 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
