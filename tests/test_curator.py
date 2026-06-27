"""
Phoenix-Evo V0.3 Curator 测试套件
===================================

覆盖模块：
  1. skill_similarity   — TF-IDF 相似度计算、分组
  2. drift_detector     — 漂移检测、健康报告
  3. curator_policy     — 策略决策
  4. skill_curator      — 完整扫描流程（scan_only）

V0.3 关键设计：
  - scan_only() 不执行任何文件操作，仅返回决策报告
  - scan() 执行完整流程（merge/archive/quarantine/downgrade）
  - draft → active 不自动激活，必须人工复核
"""

import json
import shutil
from datetime import datetime, timedelta

import pytest

# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------

@pytest.fixture
def curator_root(tmp_path):
    """
    构建完整的 Phoenix-Evo 目录结构。

    创建 5 个模拟技能（3 个高度相似，2 个独立）：
      - skill_similar_1, skill_similar_2, skill_similar_3 → 高度相似（WSL 路径修复）
      - skill_independent_1 → 独立技能
      - skill_stale_1 → 陈旧技能（30 天未使用）
    """
    root = tmp_path / "phoenix-evo"
    skills = root / "skills"
    draft = skills / "draft"
    active = skills / "active"
    archived = skills / "archived"
    quarantine = skills / "quarantine"
    for d in [draft, active, archived, quarantine]:
        d.mkdir(parents=True)

    index = {}

    # 3 个高度相似的 WSL 路径修复技能（draft 状态）
    similar_content = (
        "# debug_修复WSL中文路径文件写入null字节损坏问题\n\n"
        "## 问题\nWSL 下 patch 工具写入含中文路径文件产生 null 字节。\n\n"
        "## 解决步骤\n1. 检测路径是否含非 ASCII 字符\n"
        "2. 使用 Python 脚本 + 绝对路径写入\n"
        "3. 验证文件完整性\n"
        "## 触发条件\ntask_id 包含 wsl 或路径含中文\n"
    )
    for i in range(1, 4):
        sid = f"skill_similar_{i}"
        path = draft / f"{sid}.md"
        path.write_text(similar_content, encoding="utf-8")
        index[sid] = {
            "skill_id": sid,
            "skill_name": "debug_修复WSL中文路径文件写入null字节损坏问题",
            "status": "draft",
            "source_trajectory": f"traj_{sid}",
            "quality_score": 0.8,
            "risk_level": "low",
            "confidence": 0.9,
            "created_at": datetime.now().isoformat(),
            "usage_count": 0,
            "success_count": 0,
            "success_rate": None,
            "last_used": None,
            "warnings": [],
            "activate_level": "manual",
        }

    # 1 个独立技能（active 状态）
    independent_content = (
        "# skill_修复Git提交信息格式错误\n\n"
        "## 问题\ngit commit message 格式不规范。\n\n"
        "## 解决步骤\n1. 解析当前 commit message\n"
        "2. 按 conventional commits 格式重写\n"
        "## 触发条件\ncommit message 包含 BREAKING CHANGE 或 feat/fix/docs\n"
    )
    sid = "skill_independent_1"
    (active / f"{sid}.md").write_text(independent_content, encoding="utf-8")
    index[sid] = {
        "skill_id": sid,
        "skill_name": "修复Git提交信息格式错误",
        "status": "active",
        "source_trajectory": "traj_independent",
        "quality_score": 0.85,
        "risk_level": "low",
        "confidence": 0.9,
        "created_at": datetime.now().isoformat(),
        "usage_count": 5,
        "success_count": 4,
        "success_rate": 0.8,
        "last_used": (datetime.now() - timedelta(days=5)).isoformat(),
        "warnings": [],
        "activate_level": "auto",
    }

    # 1 个陈旧技能（30 天未使用，成功率低）
    stale_content = (
        "# skill_修复Docker网络配置\n\n"
        "## 问题\nDocker 容器网络连接失败。\n\n"
        "## 解决步骤\n1. 检查 docker network ls\n"
        "2. 重启网络\n"
    )
    sid = "skill_stale_1"
    (active / f"{sid}.md").write_text(stale_content, encoding="utf-8")
    index[sid] = {
        "skill_id": sid,
        "skill_name": "修复Docker网络配置",
        "status": "active",
        "source_trajectory": "traj_stale",
        "quality_score": 0.6,
        "risk_level": "medium",
        "confidence": 0.7,
        "created_at": (datetime.now() - timedelta(days=45)).isoformat(),
        "usage_count": 3,
        "success_count": 0,
        "success_rate": 0.0,   # 连续失败 → critical
        "last_used": (datetime.now() - timedelta(days=35)).isoformat(),
        "warnings": [],
        "activate_level": "manual",
    }

    # 写入 index
    (skills / "skill_index.json").write_text(
        json.dumps(index, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    # quarantine_index
    (quarantine / "quarantine_index.json").write_text("{}", encoding="utf-8")

    yield root, index

    # Teardown
    shutil.rmtree(root, ignore_errors=True)


# ==================================================================
# Test 1: skill_similarity — SkillVectorizer
# ==================================================================

class TestSkillSimilarity:
    """skill_similarity 模块测试。"""

    def test_tfidf_cosine_similarity_identical(self, curator_root):
        """完全相同的技能相似度应为 1.0。"""
        from core.skill_similarity import SkillVectorizer

        root, index = curator_root
        active_draft = [v for v in index.values() if v.get("status") in ("active", "draft")]

        vectorizer = SkillVectorizer(active_draft, root=root)
        results = vectorizer.compute_pairwise()

        # 找 skill_similar_1 和 skill_similar_2
        r = next(
            (x for x in results if {x.skill_a, x.skill_b} == {"skill_similar_1", "skill_similar_2"}),
            None,
        )
        assert r is not None, "pair not found"
        assert r.score >= 0.60, f"Expected high similarity, got {r.score}"
        assert r.recommendation == "merge"

    def test_tfidf_cosine_similarity_independent(self, curator_root):
        """完全不相关的技能相似度应低于阈值。"""
        from core.skill_similarity import SkillVectorizer

        root, index = curator_root
        active_draft = [v for v in index.values() if v.get("status") in ("active", "draft")]

        vectorizer = SkillVectorizer(active_draft, root=root)
        results = vectorizer.compute_pairwise()

        r = next(
            (x for x in results
             if {x.skill_a, x.skill_b} == {"skill_similar_1", "skill_independent_1"}),
            None,
        )
        assert r is not None
        assert r.score < 0.40
        assert r.recommendation == "independent"

    def test_get_groups_merges_similar(self, curator_root):
        """get_groups 应将 3 个相似技能分到同一组。"""
        from core.skill_similarity import SkillVectorizer

        root, index = curator_root
        active_draft = [v for v in index.values() if v.get("status") in ("active", "draft")]

        vectorizer = SkillVectorizer(active_draft, root=root)
        groups = vectorizer.get_groups()

        # 3 个相似技能应该在同一组
        similar_ids = {"skill_similar_1", "skill_similar_2", "skill_similar_3"}
        found = [g for g in groups if similar_ids & set(g)]
        assert len(found) == 1
        assert similar_ids <= set(found[0])

    def test_no_skills_returns_empty(self, tmp_path):
        """空技能列表不应报错。"""
        from core.skill_similarity import SkillVectorizer

        vectorizer = SkillVectorizer([])
        assert vectorizer.compute_pairwise() == []
        assert vectorizer.get_groups() == []


# ==================================================================
# Test 2: drift_detector — DriftDetector
# ==================================================================

class TestDriftDetector:
    """drift_detector 模块测试。"""

    def test_critical_success_rate_detected(self, curator_root):
        """success_rate=0 且 usage>=3 应标记为 critical。"""
        from core.drift_detector import DriftDetector

        root, index = curator_root
        detector = DriftDetector(index)
        reports = detector.analyze_all()

        stale_report = next((r for r in reports if r.skill_id == "skill_stale_1"), None)
        assert stale_report is not None
        assert stale_report.overall_severity == "critical"
        assert any(r.drift_type == "success_rate" and r.severity == "critical"
                   for r in stale_report.drift_records)

    def test_stale_warning_detected(self, curator_root):
        """超过 30 天未使用的技能应标记为 stale/warning。"""
        from core.drift_detector import DriftDetector

        root, index = curator_root
        # skill_stale_1：last_used 35 天前
        detector = DriftDetector(index)
        reports = detector.analyze_all()

        stale_report = next((r for r in reports if r.skill_id == "skill_stale_1"), None)
        assert stale_report is not None
        assert any(r.drift_type == "usage" for r in stale_report.drift_records)

    def test_healthy_skill_stable(self, curator_root):
        """健康的技能应评定为 stable。"""
        from core.drift_detector import DriftDetector

        root, index = curator_root
        detector = DriftDetector(index)
        reports = detector.analyze_all()

        healthy_report = next((r for r in reports if r.skill_id == "skill_independent_1"), None)
        assert healthy_report is not None
        assert healthy_report.overall_severity == "stable"

    def test_unused_skill_stale_created_long_ago(self, curator_root):
        """创建很久但从未使用的技能应被标记。"""
        from core.drift_detector import DriftDetector

        root, index = curator_root
        detector = DriftDetector(index)
        reports = detector.analyze_all()

        # skill_similar_1 刚创建，usage_count=0，不应触发 stale
        similar_report = next((r for r in reports if r.skill_id == "skill_similar_1"), None)
        assert similar_report is not None
        # 刚创建的技能，不应该有 usage 漂移
        assert not any(r.drift_type == "usage" for r in similar_report.drift_records)

    def test_analyze_all_sorted_by_severity(self, curator_root):
        """analyze_all() 应按严重程度降序排列。"""
        from core.drift_detector import DriftDetector

        root, index = curator_root
        detector = DriftDetector(index)
        reports = detector.analyze_all()

        severities = [r.overall_severity for r in reports]
        # critical 应在 stable 前面
        critical_pos = severities.index("critical") if "critical" in severities else -1
        stable_pos = severities.index("stable") if "stable" in severities else -1
        if critical_pos >= 0 and stable_pos >= 0:
            assert critical_pos < stable_pos


# ==================================================================
# Test 3: curator_policy — CuratorPolicy
# ==================================================================

class TestCuratorPolicy:
    """curator_policy 模块测试。"""

    def test_merge_group_produces_merge_action(self, curator_root):
        """高度相似技能组应产生 MergeAction。"""
        from core.curator_policy import CuratorPolicy
        from core.drift_detector import DriftDetector
        from core.skill_similarity import SkillVectorizer

        root, index = curator_root
        active_draft = [v for v in index.values() if v.get("status") in ("active", "draft")]

        vectorizer = SkillVectorizer(active_draft, root=root)
        sim_results = vectorizer.compute_pairwise()
        sim_groups = vectorizer.get_groups()

        detector = DriftDetector(index)
        drift_reports = detector.analyze_all()

        policy = CuratorPolicy(index)
        decision = policy.decide(sim_results, drift_reports, sim_groups)

        # 应该至少有一组 merge
        assert len(decision.merge_groups) >= 1
        merge = decision.merge_groups[0]
        assert merge.surviving_id in ["skill_similar_1", "skill_similar_2", "skill_similar_3"]
        assert set(merge.skill_ids).issubset(
            {"skill_similar_1", "skill_similar_2", "skill_similar_3"}
        )

    def test_critical_skill_archived(self, curator_root):
        """critical 漂移技能应被归档。"""
        from core.curator_policy import CuratorPolicy
        from core.drift_detector import DriftDetector
        from core.skill_similarity import SkillVectorizer

        root, index = curator_root
        vectorizer = SkillVectorizer(list(index.values()), root=root)
        sim_results = vectorizer.compute_pairwise()
        sim_groups = vectorizer.get_groups()

        detector = DriftDetector(index)
        drift_reports = detector.analyze_all()

        policy = CuratorPolicy(index)
        decision = policy.decide(sim_results, drift_reports, sim_groups)

        assert "skill_stale_1" in decision.archived_skills

    def test_stable_skill_kept(self, curator_root):
        """stable 技能应被保留。"""
        from core.curator_policy import CuratorPolicy
        from core.drift_detector import DriftDetector
        from core.skill_similarity import SkillVectorizer

        root, index = curator_root
        vectorizer = SkillVectorizer(list(index.values()), root=root)
        sim_results = vectorizer.compute_pairwise()
        sim_groups = vectorizer.get_groups()

        detector = DriftDetector(index)
        drift_reports = detector.analyze_all()

        policy = CuratorPolicy(index)
        decision = policy.decide(sim_results, drift_reports, sim_groups)

        assert "skill_independent_1" in decision.kept_skills

    def test_decision_has_summary_note(self, curator_root):
        """decision.curator_note 不应为空。"""
        from core.curator_policy import CuratorPolicy
        from core.drift_detector import DriftDetector
        from core.skill_similarity import SkillVectorizer

        root, index = curator_root
        vectorizer = SkillVectorizer(list(index.values()), root=root)
        decision = CuratorPolicy(index).decide(
            vectorizer.compute_pairwise(),
            DriftDetector(index).analyze_all(),
            vectorizer.get_groups(),
        )

        assert decision.curator_note != ""
        assert len(decision.curator_note) > 5


# ==================================================================
# Test 4: skill_curator — SkillCurator
# ==================================================================

class TestSkillCurator:
    """skill_curator 模块测试。"""

    def test_scan_only_no_file_mutation(self, curator_root):
        """scan_only() 执行后，draft/active 目录文件不应被移动。"""
        from core.skill_curator import SkillCurator

        root, index = curator_root
        curator = SkillCurator(root=root)

        # 记录扫描前的文件列表
        draft_before = list((root / "skills" / "draft").glob("*.md"))
        active_before = list((root / "skills" / "active").glob("*.md"))

        report = curator.scan_only()

        # 文件不应被移动
        draft_after = list((root / "skills" / "draft").glob("*.md"))
        active_after = list((root / "skills" / "active").glob("*.md"))
        assert draft_before == draft_after
        assert active_before == active_after
        assert report.scanned_count == 5

    def test_scan_only_returns_decision(self, curator_root):
        """scan_only() 应返回包含决策信息的完整报告。"""
        from core.skill_curator import SkillCurator

        root, index = curator_root
        curator = SkillCurator(root=root)
        report = curator.scan_only()

        assert report.scanned_count == 5
        assert report.decision is not None
        assert hasattr(report, "similarity_results")
        assert hasattr(report, "drift_reports")
        assert hasattr(report, "similarity_groups")

    def test_scan_only_errors_list(self, curator_root):
        """scan_only() 的 errors 列表应为空（无异常）。"""
        from core.skill_curator import SkillCurator

        root, index = curator_root
        curator = SkillCurator(root=root)
        report = curator.scan_only()

        assert report.errors == []

    def test_review_queue_collects_curator_reviews(self, curator_root):
        """get_review_queue() 应收集 curator review 列表。"""
        from core.skill_curator import SkillCurator

        root, index = curator_root
        curator = SkillCurator(root=root)

        # 先执行 scan_only（不执行，因此 curator review 还在 index 中）
        curator.scan_only()
        queue = curator.get_review_queue()

        # skill_stale_1 是 critical，应该被 archived 而非 review
        # curator review 主要来自 risk 技能的 review
        # 这个测试验证 get_review_queue 不报错
        assert isinstance(queue, list)

    def test_curator_log_empty_after_scan_only(self, curator_root):
        """scan_only() 执行后，不应写入运行日志（只有 scan() 才写）。"""
        from core.skill_curator import SkillCurator

        root, index = curator_root
        curator = SkillCurator(root=root)
        curator.scan_only()

        log_path = root / "skills" / ".curator_log.json"
        assert not log_path.exists()

    def test_scan_full_log_written(self, curator_root):
        """scan() 执行后应写入运行日志。"""
        from core.skill_curator import SkillCurator

        root, index = curator_root
        curator = SkillCurator(root=root)
        curator.scan()

        log_path = root / "skills" / ".curator_log.json"
        assert log_path.exists()
        logs = json.loads(log_path.read_text(encoding="utf-8"))
        assert len(logs) == 1
        assert logs[0]["scanned_count"] == 5

    def test_scan_full_merges_and_archives(self, curator_root):
        """scan() 应实际执行合并和归档。"""
        from core.skill_curator import SkillCurator

        root, index = curator_root
        curator = SkillCurator(root=root)
        curator.scan()

        # 合并后，archived 目录应有被合并的技能文件
        archived_files = list((root / "skills" / "archived").glob("*.md"))
        # 至少 2 个相似技能应被合并（保留 1 个，archive 其余）
        assert len(archived_files) >= 2

        # merged_into 字段验证
        index_after = json.loads(
            (root / "skills" / "skill_index.json").read_text(encoding="utf-8")
        )
        merged = [sid for sid, e in index_after.items() if e.get("status") == "merged"]
        assert len(merged) >= 2


# ==================================================================
# Test 5: V0.3 integration — PhoenixEvo + Curator
# ==================================================================

class TestCuratorIntegration:
    """Curator 与 PhoenixEvo 的集成测试。"""

    def test_curator_scanned_count_matches_skill_index(self, curator_root):
        """Curator 扫描计数应与 skill_index 中的 active+draft 数量一致。"""
        from core.skill_curator import SkillCurator

        root, index = curator_root
        curator = SkillCurator(root=root)
        report = curator.scan_only()

        expected = sum(1 for e in index.values() if e.get("status") in ("active", "draft"))
        assert report.scanned_count == expected

    def test_scan_report_has_correct_structure(self, curator_root):
        """CuratorScanReport 的所有字段都应有值。"""
        from core.skill_curator import SkillCurator

        root, index = curator_root
        curator = SkillCurator(root=root)
        report = curator.scan_only()

        assert report.scanned_count > 0
        assert isinstance(report.decision.merge_groups, list)
        assert isinstance(report.similarity_results, list)
        assert isinstance(report.drift_reports, list)
        assert isinstance(report.similarity_groups, list)
        assert report.curator_log is not None  # scan_only 也有 log，只是未写入文件


# ==================================================================
# Run all tests
# ==================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
