"""
Phoenix-Evo V0.4 Evidence & Replay 测试套件
=============================================

覆盖模块：
  1. skill_evidence     — 技能证据卡管理
  2. skill_benchmark   — 评测集管理与 case 匹配
  3. skill_replay      — 回放执行与报告生成
  4. replay_reporter   — 报告格式化与证据汇总
  5. evidence_policy   — 晋级决策规则

V0.4 核心验证点：
  - 每个 skill 有对应 skill_card.json
  - card 绑定 source_trajectory_id
  - 无 evidence 的 skill 不晋升 active
  - replay(skill, cases) 输出带 delta 指标的 ReplayReport
  - EvidencePolicy 正确路由（promote / quarantine / keep_draft）
"""

import json
import shutil
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

import pytest


# ------------------------------------------------------------------ 
# Fixtures
# ------------------------------------------------------------------ 

@pytest.fixture
def v04_root(tmp_path):
    """
    构建 V0.4 完整目录结构（用于 evidence 模块测试）。
    """
    root = tmp_path / "phoenix-evo-v04"
    for d in [
        root / "core",
        root / "skills" / "draft",
        root / "skills" / "active",
        root / "skills" / "archived",
        root / "skills" / "quarantine",
        root / "data" / "trajectories",
        root / "data" / "benchmarks",
        root / "evidence" / "skill_cards",
        root / "evidence" / "replay_reports",
    ]:
        d.mkdir(parents=True, exist_ok=True)

    # 写入 skill_index.json
    index = {
        "skill_test_001": {
            "skill_id": "skill_test_001",
            "skill_name": "修复WSL中文路径文件写入null字节",
            "status": "draft",
            "source_trajectory": "traj_wsl_001",
            "quality_score": 0.85,
            "risk_level": "low",
            "confidence": 0.9,
            "created_at": datetime.now().isoformat(),
            "usage_count": 0,
            "success_count": 0,
            "success_rate": None,
            "last_used": None,
            "warnings": [],
            "activate_level": "manual",
        },
        "skill_test_002": {
            "skill_id": "skill_test_002",
            "skill_name": "危险命令拦截",
            "status": "draft",
            "source_trajectory": "traj_danger_001",
            "quality_score": 0.9,
            "risk_level": "high",
            "confidence": 0.95,
            "created_at": datetime.now().isoformat(),
            "usage_count": 3,
            "success_count": 1,
            "success_rate": 0.33,
            "last_used": (datetime.now() - timedelta(days=35)).isoformat(),
            "warnings": [],
            "activate_level": "manual",
        },
    }
    (root / "skills" / "skill_index.json").write_text(
        json.dumps(index, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    # 写入 2 个 draft 技能文件
    for sid in ["skill_test_001", "skill_test_002"]:
        (root / "skills" / "draft" / f"{sid}.md").write_text(
            f"# {sid}\n\n测试技能内容。\n",
            encoding="utf-8",
        )

    yield root, index

    shutil.rmtree(root, ignore_errors=True)


# ==================================================================
# Test 1: skill_evidence — SkillCard CRUD
# ==================================================================

class TestSkillEvidence:
    """skill_evidence 模块测试。"""

    def test_create_card_from_skill(self, v04_root):
        """从技能字典创建证据卡，绑定 trajectory_id。"""
        from core.skill_evidence import SkillEvidenceManager

        root, index = v04_root
        mgr = SkillEvidenceManager(root=root)

        skill = {
            "skill_id": "skill_test_001",
            "skill_name": "修复WSL中文路径",
            "quality_score": 0.85,
            "risk_level": "low",
            "task_goal": "修复 WSL 中文路径写入 null 字节问题",
            "procedure": ["检测路径", "改用 Python I/O", "验证完整性"],
        }
        card = mgr.create_card(skill, trajectory_id="traj_wsl_001")

        assert card.skill_id == "skill_test_001"
        assert "traj_wsl_001" in card.source_trajectory_ids
        assert card.status == "draft"
        assert card.evidence_type == "successful_trajectory"
        assert card.quality_score == 0.85

        # 文件应存在
        card_path = root / "evidence" / "skill_cards" / "skill_test_001.card.json"
        assert card_path.exists()

    def test_get_card(self, v04_root):
        """读取已存在的证据卡。"""
        from core.skill_evidence import SkillEvidenceManager

        root, index = v04_root
        mgr = SkillEvidenceManager(root=root)

        # 先创建
        skill = {"skill_id": "skill_test_001", "skill_name": "测试", "quality_score": 0.8, "risk_level": "low"}
        mgr.create_card(skill, "traj_001")

        # 再读取
        card = mgr.get_card("skill_test_001")
        assert card is not None
        assert card.skill_id == "skill_test_001"
        assert "traj_001" in card.source_trajectory_ids

    def test_get_card_not_found(self, v04_root):
        """不存在的证据卡返回 None。"""
        from core.skill_evidence import SkillEvidenceManager

        root, index = v04_root
        mgr = SkillEvidenceManager(root=root)
        assert mgr.get_card("nonexistent_skill") is None

    def test_update_card(self, v04_root):
        """更新证据卡字段。"""
        from core.skill_evidence import SkillEvidenceManager

        root, index = v04_root
        mgr = SkillEvidenceManager(root=root)

        skill = {"skill_id": "skill_test_001", "skill_name": "测试", "quality_score": 0.8, "risk_level": "low"}
        mgr.create_card(skill, "traj_001")

        updated = mgr.update_card("skill_test_001", status="replay_pass", replay_pass_count=2)
        assert updated is not None
        assert updated.status == "replay_pass"
        assert updated.replay_pass_count == 2

    def test_list_cards_filter_by_status(self, v04_root):
        """按 status 过滤证据卡列表。"""
        from core.skill_evidence import SkillEvidenceManager

        root, index = v04_root
        mgr = SkillEvidenceManager(root=root)

        # 创建 2 个不同 status 的 card
        for i, (sid, status) in enumerate([("skill_001", "draft"), ("skill_002", "replay_pass")]):
            skill = {"skill_id": sid, "skill_name": f"测试{i}", "quality_score": 0.8, "risk_level": "low"}
            card = mgr.create_card(skill, f"traj_{i:03d}")
            if status != "draft":
                mgr.update_card(sid, status=status)

        all_cards = mgr.list_cards()
        draft_cards = mgr.list_cards(status="draft")
        assert len(all_cards) >= 2
        assert len(draft_cards) >= 1
        assert all(c.status == "draft" for c in draft_cards)

    def test_record_replay_result(self, v04_root):
        """记录回放结果，更新 pass/fail 计数。"""
        from core.skill_evidence import SkillEvidenceManager

        root, index = v04_root
        mgr = SkillEvidenceManager(root=root)

        skill = {"skill_id": "skill_test_001", "skill_name": "测试", "quality_score": 0.8, "risk_level": "low"}
        mgr.create_card(skill, "traj_001")

        # 记录一次 pass
        card = mgr.record_replay_result("skill_test_001", "report_001", passed=True)
        assert card.replay_pass_count == 1
        assert card.replay_fail_count == 0
        assert card.status == "replay_pass"

        # 记录一次 fail
        card = mgr.record_replay_result("skill_test_001", "report_002", passed=False)
        assert card.replay_pass_count == 1
        assert card.replay_fail_count == 1
        assert card.status == "replay_fail"

    def test_set_promotion_ready(self, v04_root):
        """设置技能是否可以晋级。"""
        from core.skill_evidence import SkillEvidenceManager

        root, index = v04_root
        mgr = SkillEvidenceManager(root=root)

        skill = {"skill_id": "skill_test_001", "skill_name": "测试", "quality_score": 0.8, "risk_level": "low"}
        mgr.create_card(skill, "traj_001")

        card = mgr.set_promotion_ready("skill_test_001", ready=True, note="回放全部通过")
        assert card.promotion_ready is True
        assert card.promotion_note == "回放全部通过"
        assert card.status == "replay_pass"

    def test_bind_trajectory_for_merged_skill(self, v04_root):
        """合并技能的额外轨迹绑定。"""
        from core.skill_evidence import SkillEvidenceManager

        root, index = v04_root
        mgr = SkillEvidenceManager(root=root)

        skill = {"skill_id": "skill_test_001", "skill_name": "测试", "quality_score": 0.8, "risk_level": "low"}
        mgr.create_card(skill, "traj_001")

        # 合并另一个轨迹来源
        mgr.bind_trajectory("skill_test_001", "traj_merged_002")
        card = mgr.get_card("skill_test_001")
        assert "traj_merged_002" in card.source_trajectory_ids
        assert card.evidence_type == "merged"

    def test_get_promotion_candidates(self, v04_root):
        """promotion_ready=True 且 status=replay_pass 的技能才能晋级。"""
        from core.skill_evidence import SkillEvidenceManager

        root, index = v04_root
        mgr = SkillEvidenceManager(root=root)

        skill = {"skill_id": "skill_test_001", "skill_name": "测试", "quality_score": 0.8, "risk_level": "low"}
        mgr.create_card(skill, "traj_001")
        mgr.update_card("skill_test_001", status="replay_pass", promotion_ready=True)

        candidates = mgr.get_promotion_candidates()
        assert len(candidates) >= 1
        assert all(c.promotion_ready and c.status == "replay_pass" for c in candidates)


# ==================================================================
# Test 2: skill_benchmark — BenchmarkCase & matching
# ==================================================================

class TestSkillBenchmark:
    """skill_benchmark 模块测试。"""

    def test_default_cases_loaded(self, v04_root):
        """默认 8 个 case 应被加载。"""
        from core.skill_benchmark import SkillBenchmark

        root, index = v04_root
        bm = SkillBenchmark(root=root)
        cases = bm.list_cases()
        assert len(cases) == 8
        assert {c.case_id for c in cases} == {
            f"CASE-{i:03d}" for i in range(1, 9)
        }

    def test_get_case(self, v04_root):
        """通过 case_id 获取单个 case。"""
        from core.skill_benchmark import SkillBenchmark

        root, index = v04_root
        bm = SkillBenchmark(root=root)
        case = bm.get_case("CASE-001")
        assert case is not None
        assert case.task.startswith("修复 WSL")

    def test_search_by_keyword(self, v04_root):
        """关键词搜索返回相关 case。"""
        from core.skill_benchmark import SkillBenchmark

        root, index = v04_root
        bm = SkillBenchmark(root=root)

        results = bm.search_by_keyword("WSL")
        assert len(results) >= 1
        assert any("WSL" in c.task for c in results)

    def test_search_by_risk_tag(self, v04_root):
        """风险标签搜索。"""
        from core.skill_benchmark import SkillBenchmark

        root, index = v04_root
        bm = SkillBenchmark(root=root)

        results = bm.search_by_risk_tag("dangerous_command")
        assert len(results) >= 1
        assert all("dangerous_command" in c.risk_tags for c in results)

    def test_score_skill_against_case_exact_match(self, v04_root):
        """高度匹配的技能应返回 exact_match judgment。"""
        from core.skill_benchmark import SkillBenchmark

        root, index = v04_root
        bm = SkillBenchmark(root=root)

        skill = {
            "skill_id": "skill_wsl_fix",
            "skill_name": "修复WSL中文路径文件写入null字节损坏",
            "task_goal": "修复 WSL 中文路径写入 null 字节问题",
            "inputs": ["路径编码", "WSL"],
            "procedure": ["检测路径", "改用 Python I/O", "验证"],
        }
        case = bm.get_case("CASE-001")
        score = bm.score_skill_against_case(skill, case)

        assert score["judgment"] == "exact_match"
        assert score["overall_score"] >= 0.70

    def test_score_skill_against_case_mismatch(self, v04_root):
        """无关技能应返回 mismatch。"""
        from core.skill_benchmark import SkillBenchmark

        root, index = v04_root
        bm = SkillBenchmark(root=root)

        skill = {
            "skill_id": "skill_git_commit",
            "skill_name": "修复 Git 提交信息格式",
            "task_goal": "规范 git commit message",
            "procedure": ["解析 message", "重写格式"],
        }
        case = bm.get_case("CASE-001")  # WSL case
        score = bm.score_skill_against_case(skill, case)

        assert score["judgment"] in ("partial", "mismatch")
        assert score["overall_score"] < 0.70

    def test_get_all_risk_tags(self, v04_root):
        """返回所有 case 的风险标签集合。"""
        from core.skill_benchmark import SkillBenchmark

        root, index = v04_root
        bm = SkillBenchmark(root=root)
        tags = bm.get_all_risk_tags()
        assert "dangerous_command" in tags
        assert "data_corruption" in tags
        assert "skill_redundancy" in tags


# ==================================================================
# Test 3: skill_replay — ReplayReport & SkillReplay
# ==================================================================

class TestSkillReplay:
    """skill_replay 模块测试。"""

    def test_replay_produces_report(self, v04_root):
        """replay() 应输出包含 delta 指标的 ReplayReport。"""
        from core.skill_replay import SkillReplay

        root, index = v04_root
        replay = SkillReplay(root=root)

        skill = {
            "skill_id": "skill_test_001",
            "skill_name": "修复WSL中文路径",
            "task_goal": "修复 WSL 中文路径写入 null 字节",
            "procedure": ["检测路径", "改用 Python I/O", "验证完整性"],
            "risk_level": "low",
        }
        cases = [
            {
                "case_id": "CASE-001",
                "task": "修复 WSL 中文路径文件写入 null 字节损坏问题",
                "task_keywords": ["WSL", "中文路径", "null字节"],
                "risk_tags": ["data_corruption"],
                "expected_behavior": "使用 Python 脚本写入",
            }
        ]
        report = replay.replay(skill, cases)

        assert report.skill_id == "skill_test_001"
        assert report.total_cases == 1
        assert report.report_id.startswith("replay_skill_test_001")
        assert len(report.results) == 1

    def test_replay_calculates_delta(self, v04_root):
        """回放报告应包含 success_delta、risk_delta 等指标。"""
        from core.skill_replay import SkillReplay

        root, index = v04_root
        replay = SkillReplay(root=root)

        skill = {
            "skill_id": "skill_test_001",
            "skill_name": "危险命令拦截",
            "task_goal": "拦截 rm -rf / 危险命令",
            "procedure": ["检测命令", "拦截"],
            "risk_level": "medium",
        }
        cases = [
            {
                "case_id": "CASE-003",
                "task": "危险命令识别与拦截",
                "task_keywords": ["rm", "-rf", "危险", "拦截"],
                "risk_tags": ["dangerous_command"],
                "expected_behavior": "拦截",
            }
        ]
        report = replay.replay(skill, cases)

        assert report.total_cases == 1
        assert hasattr(report, "success_delta")
        assert hasattr(report, "risk_delta")
        assert hasattr(report, "regression_found")

    def test_replay_saves_report(self, v04_root):
        """save_report() 应将报告写入 evidence/replay_reports/。"""
        from core.skill_replay import SkillReplay

        root, index = v04_root
        replay = SkillReplay(root=root)

        skill = {"skill_id": "skill_test_001", "skill_name": "测试", "procedure": ["step"], "risk_level": "low"}
        cases = [{"case_id": "CASE-001", "task": "测试", "task_keywords": ["WSL"], "risk_tags": [], "expected_behavior": "ok"}]
        report = replay.replay(skill, cases)
        path = replay.save_report(report)

        assert path.exists()
        data = json.loads(path.read_text(encoding="utf-8"))
        assert data["skill_id"] == "skill_test_001"

    def test_replay_loads_report(self, v04_root):
        """load_report() 应能从磁盘加载报告。"""
        from core.skill_replay import SkillReplay

        root, index = v04_root
        replay = SkillReplay(root=root)

        skill = {"skill_id": "skill_test_001", "skill_name": "测试", "procedure": ["step"], "risk_level": "low"}
        cases = [{"case_id": "CASE-001", "task": "测试", "task_keywords": ["WSL"], "risk_tags": [], "expected_behavior": "ok"}]
        report = replay.replay(skill, cases)
        replay.save_report(report)

        loaded = replay.load_report(report.report_id)
        assert loaded is not None
        assert loaded.skill_id == "skill_test_001"
        assert loaded.total_cases == 1

    def test_replay_multiple_cases(self, v04_root):
        """replay() 支持批量多个 cases。"""
        from core.skill_replay import SkillReplay

        root, index = v04_root
        replay = SkillReplay(root=root)

        skill = {
            "skill_id": "skill_multi",
            "skill_name": "WSL修复技能",
            "procedure": ["检测", "改用Python", "验证"],
            "risk_level": "low",
        }
        cases = [
            {"case_id": "CASE-001", "task": "WSL修复", "task_keywords": ["WSL"], "risk_tags": ["data_corruption"], "expected_behavior": "ok"},
            {"case_id": "CASE-002", "task": "patch损坏", "task_keywords": ["patch"], "risk_tags": ["data_corruption"], "expected_behavior": "ok"},
        ]
        report = replay.replay(skill, cases)
        assert report.total_cases == 2
        assert len(report.results) == 2

    def test_replay_regression_detected(self, v04_root):
        """危险 case 但技能无安全措施 → regression。"""
        from core.skill_replay import SkillReplay

        root, index = v04_root
        replay = SkillReplay(root=root)

        # 技能没有任何安全相关关键词
        skill = {
            "skill_id": "skill_no_safety",
            "skill_name": "执行任意命令",
            "procedure": ["直接执行"],
            "risk_level": "high",
        }
        cases = [
            {
                "case_id": "CASE-003",
                "task": "危险命令识别",
                "task_keywords": ["rm", "-rf"],
                "risk_tags": ["dangerous_command"],
                "expected_behavior": "拦截",
            }
        ]
        report = replay.replay(skill, cases)
        assert report.results[0].regression_found is True


# ==================================================================
# Test 4: evidence_policy — EvidencePolicy decision
# ==================================================================

class TestEvidencePolicy:
    """evidence_policy 晋级决策测试。"""

    def test_replay_pass_rate_threshold(self):
        """通过率 < 70% → quarantine。"""
        from core.skill_replay import ReplayReport, ReplayResult
        from core.skill_replay import EvidencePolicy

        policy = EvidencePolicy()
        report = ReplayReport(
            report_id="r1",
            skill_id="skill_001",
            replayed_at=datetime.now().isoformat(),
            total_cases=10,
            passed_cases=5,   # 50% < 70%
            overall_pass=False,
            results=[],
        )
        decision, reason = policy.evaluate("skill_001", report, evidence_complete=True)
        assert decision == "quarantine"

    def test_regression_blocks_promotion(self):
        """有 regression → quarantine。"""
        from core.skill_replay import ReplayReport, ReplayResult
        from core.skill_replay import EvidencePolicy

        policy = EvidencePolicy()
        report = ReplayReport(
            report_id="r1",
            skill_id="skill_001",
            replayed_at=datetime.now().isoformat(),
            total_cases=5,
            passed_cases=4,
            overall_pass=True,
            regression_found=True,
            results=[ReplayResult(case_id="CASE-003", passed=True, regression_found=True)],
        )
        decision, reason = policy.evaluate("skill_001", report, evidence_complete=True)
        assert decision == "quarantine"
        assert "回归" in reason

    def test_risk_increase_blocks_promotion(self):
        """风险上升 > 0.05 → quarantine。"""
        from core.skill_replay import ReplayReport
        from core.skill_replay import EvidencePolicy

        policy = EvidencePolicy()
        report = ReplayReport(
            report_id="r1",
            skill_id="skill_001",
            replayed_at=datetime.now().isoformat(),
            total_cases=5,
            passed_cases=5,
            overall_pass=True,
            regression_found=False,
            risk_delta=0.10,   # 上升超过 0.05
            results=[],
        )
        decision, reason = policy.evaluate("skill_001", report, evidence_complete=True)
        assert decision == "quarantine"

    def test_all_criteria_met_promotes(self):
        """所有条件满足 → promote。"""
        from core.skill_replay import ReplayReport
        from core.skill_replay import EvidencePolicy

        policy = EvidencePolicy()
        report = ReplayReport(
            report_id="r1",
            skill_id="skill_001",
            replayed_at=datetime.now().isoformat(),
            total_cases=5,
            passed_cases=5,    # 100% >= 70%
            overall_pass=True,
            regression_found=False,
            risk_delta=-0.05,  # 风险下降
            results=[],
        )
        decision, reason = policy.evaluate("skill_001", report, evidence_complete=True)
        assert decision == "promote"

    def test_no_replay_cases_keeps_draft(self):
        """回放 case 数 < 1 → keep_draft。"""
        from core.skill_replay import ReplayReport
        from core.skill_replay import EvidencePolicy

        policy = EvidencePolicy()
        report = ReplayReport(
            report_id="r1",
            skill_id="skill_001",
            replayed_at=datetime.now().isoformat(),
            total_cases=0,
            passed_cases=0,
            overall_pass=False,
            results=[],
        )
        decision, reason = policy.evaluate("skill_001", report, evidence_complete=True)
        assert decision == "keep_draft"


# ==================================================================
# Test 5: replay_reporter — Report formatting & evidence summary
# ==================================================================

class TestReplayReporter:
    """replay_reporter 模块测试。"""

    def test_format_report_dict(self, v04_root):
        """format_report() 返回可序列化 dict。"""
        from core.skill_replay import SkillReplay, ReplayReport, ReplayResult
        from core.replay_reporter import ReplayReporter

        root, index = v04_root
        reporter = ReplayReporter(root=root)

        report = ReplayReport(
            report_id="r1",
            skill_id="skill_001",
            replayed_at=datetime.now().isoformat(),
            total_cases=3,
            passed_cases=2,
            overall_pass=True,
            success_delta=0.15,
            error_delta=-0.1,
            risk_delta=-0.05,
            regression_found=False,
            results=[
                ReplayResult(case_id="CASE-001", passed=True, success_delta=0.3, error_delta=-0.2, risk_delta=-0.05),
                ReplayResult(case_id="CASE-002", passed=False, success_delta=-0.1, error_delta=0.05, risk_delta=0.0),
                ReplayResult(case_id="CASE-003", passed=True, success_delta=0.3, error_delta=-0.2, risk_delta=-0.05),
            ],
        )
        formatted = reporter.format_report(report)

        assert formatted["report_id"] == "r1"
        assert formatted["summary"]["pass_rate"] == "67%"
        assert formatted["summary"]["overall_pass"] is True

    def test_format_markdown(self, v04_root):
        """format_markdown() 返回 markdown 文本。"""
        from core.skill_replay import ReplayReport, ReplayResult
        from core.replay_reporter import ReplayReporter

        root, index = v04_root
        reporter = ReplayReporter(root=root)

        report = ReplayReport(
            report_id="r1",
            skill_id="skill_md_test",
            replayed_at=datetime.now().isoformat(),
            total_cases=2,
            passed_cases=2,
            overall_pass=True,
            results=[
                ReplayResult(case_id="CASE-001", passed=True, success_delta=0.3, error_delta=-0.2, risk_delta=-0.05, regression_found=False, reason="ok"),
                ReplayResult(case_id="CASE-002", passed=True, success_delta=0.2, error_delta=-0.1, risk_delta=-0.02, regression_found=False, reason="ok"),
            ],
        )
        md = reporter.format_markdown(report)
        assert "# Replay Report" in md
        assert "CASE-001" in md
        assert "✅" in md

    def test_build_evidence_summary(self, v04_root):
        """build_evidence_summary() 生成带评分的证据摘要。"""
        from core.skill_evidence import SkillEvidenceManager, SkillCard
        from core.skill_replay import ReplayReport, ReplayResult
        from core.replay_reporter import ReplayReporter

        root, index = v04_root
        evidence_mgr = SkillEvidenceManager(root=root)
        reporter = ReplayReporter(root=root)

        # 创建 card
        skill = {"skill_id": "skill_test_001", "skill_name": "WSL修复", "quality_score": 0.8, "risk_level": "low", "procedure": ["检测", "写入"]}
        card = evidence_mgr.create_card(skill, "traj_wsl")
        evidence_mgr.update_card("skill_test_001",
                                verified_by=["skill_verifier", "immune_guard"],
                                replay_pass_count=3,
                                replay_fail_count=0)

        # 回放报告
        report = ReplayReport(
            report_id="r1",
            skill_id="skill_test_001",
            replayed_at=datetime.now().isoformat(),
            total_cases=3,
            passed_cases=3,
            overall_pass=True,
            regression_found=False,
            risk_delta=-0.05,
            results=[],
        )

        summary = reporter.build_evidence_summary(card, report)

        assert summary.skill_id == "skill_test_001"
        assert summary.overall_score >= 50
        assert summary.verdict in ("strong", "moderate", "weak", "insufficient")
        assert isinstance(summary.promotion_recommended, bool)

    def test_evidence_summary_no_replay(self, v04_root):
        """无回放报告时，evidence_summary 的 replay_validity 为 0。"""
        from core.skill_evidence import SkillEvidenceManager
        from core.replay_reporter import ReplayReporter

        root, index = v04_root
        evidence_mgr = SkillEvidenceManager(root=root)
        reporter = ReplayReporter(root=root)

        skill = {"skill_id": "skill_test_001", "skill_name": "测试", "quality_score": 0.8, "risk_level": "low"}
        card = evidence_mgr.create_card(skill, "traj_001")

        summary = reporter.build_evidence_summary(card, replay_report=None)
        assert summary.replay_validity == 0.0
        assert summary.promotion_recommended is False

    def test_batch_summary(self, v04_root):
        """批量回放报告汇总。"""
        from core.skill_replay import ReplayReport, ReplayResult
        from core.replay_reporter import ReplayReporter

        root, index = v04_root
        reporter = ReplayReporter(root=root)

        reports = [
            ReplayReport(report_id="r1", skill_id="skill_001", replayed_at=datetime.now().isoformat(),
                         total_cases=3, passed_cases=3, overall_pass=True, regression_found=False, results=[]),
            ReplayReport(report_id="r2", skill_id="skill_002", replayed_at=datetime.now().isoformat(),
                         total_cases=3, passed_cases=1, overall_pass=False, regression_found=False, results=[]),
        ]
        batch = reporter.batch_summary(reports, skill_cards={})
        assert batch["total_skills"] == 2
        assert batch["total_passed"] == 1
        assert batch["overall_pass_rate"] == "50%"


# ==================================================================
# Run all tests
# ==================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
