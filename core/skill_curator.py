"""
skill_curator: Phoenix-Evo Curator 主流程
V0.3 — Phoenix-Evo

职责：
  - 定期扫描技能库（draft / active）
  - 执行重复检测、漂移检测、治理决策
  - 执行 curator_policy 产生的操作（merge / archive / downgrade / quarantine）
  - 维护 Curator 运行日志（skills/.curator_log.json）
  - V0.3 不自动激活技能（draft -> active 需人工复核）

与 PhoenixEvo 主循环的关系：
  - PhoenixEvo.trigger_evolution() 在技能生成后调用 Curator.scan()
  - Curator.scan() 是独立扫描，不依赖 PhoenixEvo 的任务流

V0.3 Curator 四模块协作：
  1. skill_similarity  → 找出重复/相似技能
  2. drift_detector    → 识别技能漂移和健康问题
  3. curator_policy    → 综合两者输出决策
  4. skill_curator    → 执行决策，更新技能库
"""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Any

from .skill_registry import SkillRegistry
from .skill_similarity import SkillVectorizer, SimilarityResult
from .drift_detector import DriftDetector, SkillHealthReport
from .curator_policy import (
    CuratorPolicy,
    CuratorDecision,
    CuratorAction,
    MergeAction,
    KeepAction,
    DowngradeAction,
    ArchiveAction,
    QuarantineAction,
    ReviewAction,
)
from .quarantine_manager import QuarantineManager


# ----------------------------------------------------------------------
# Curator log
# ----------------------------------------------------------------------

@dataclass
class CuratorRunLog:
    """Curator 单次运行的记录。"""
    run_id: str
    scanned_count: int
    merge_groups: int
    archived_count: int
    quarantined_count: int
    downgraded_count: int
    review_count: int
    kept_count: int
    skipped_count: int
    actions_summary: str
    run_at: str
    errors: list[str] = field(default_factory=list)


class CuratorLogger:
    """
    维护 skills/.curator_log.json，运行历史用于追溯和回滚参考。
    """

    def __init__(self, root: Path | None = None):
        self.root = Path(root) if root else Path(__file__).parent.parent
        self.log_path = self.root / "skills" / ".curator_log.json"

    def append(self, log: CuratorRunLog) -> None:
        """追加单次运行记录。"""
        logs = self._load()
        logs.append(asdict(log))
        # 只保留最近 50 条
        if len(logs) > 50:
            logs = logs[-50:]
        self._save(logs)

    def get_recent(self, n: int = 5) -> list[CuratorRunLog]:
        """获取最近 N 次运行记录。"""
        raw = self._load()
        return [CuratorRunLog(**r) for r in raw[-n:]]

    def _load(self) -> list[dict]:
        if not self.log_path.exists():
            return []
        try:
            return json.loads(self.log_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, IOError):
            return []

    def _save(self, logs: list[dict]) -> None:
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self.log_path.write_text(
            json.dumps(logs, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )


# ----------------------------------------------------------------------
# Curator main class
# ----------------------------------------------------------------------

class SkillCurator:
    """
    Phoenix-Evo V0.3 Curator：技能生态治理系统。

    用法:
        curator = SkillCurator(root="/path/to/Phoenix-Evo")
        report = curator.scan()         # 执行完整扫描
        report = curator.scan_only()   # 仅分析，不执行操作
        curator.execute(decision)       # 执行决策（可单独调用）
    """

    def __init__(self, root: Path | str | None = None):
        self.root = Path(root) if root else Path(__file__).parent.parent
        self.registry = SkillRegistry(root=self.root)
        self.quarantine_mgr = QuarantineManager(root=self.root)
        self.curator_logger = CuratorLogger(root=self.root)

    # ------------------------------------------------------------------
    # Public API: full scan + execute
    # ------------------------------------------------------------------

    def scan(self) -> CuratorScanReport:
        """
        执行完整 Curator 扫描：分析 → 决策 → 执行。
        返回扫描报告。
        """
        return self._scan(execute=True)

    def scan_only(self) -> CuratorScanReport:
        """
        仅分析扫描（不执行任何操作），返回决策报告供人工参考。
        """
        return self._scan(execute=False)

    # ------------------------------------------------------------------
    # Core scan logic
    # ------------------------------------------------------------------

    def _scan(self, execute: bool) -> CuratorScanReport:
        errors: list[str] = []

        # 1. 加载技能索引
        index = self.registry.get_index()

        # 2. 提取 active + draft 技能条目
        active_draft = [
            entry for entry in index.values()
            if entry.get("status") in ("active", "draft")
        ]

        # 3. 相似度分析
        similarity_results: list[SimilarityResult] = []
        similarity_groups: list[list[str]] = []
        try:
            if len(active_draft) >= 2:
                vectorizer = SkillVectorizer(active_draft, root=self.root)
                similarity_results = vectorizer.compute_pairwise()
                similarity_groups = vectorizer.get_groups()
        except Exception as e:
            errors.append(f"相似度分析异常: {e}")

        # 4. 漂移检测
        drift_reports: list[SkillHealthReport] = []
        try:
            detector = DriftDetector(index)
            drift_reports = detector.analyze_all()
        except Exception as e:
            errors.append(f"漂移检测异常: {e}")

        # 5. 策略决策
        decision = CuratorDecision()
        try:
            policy = CuratorPolicy(index)
            decision = policy.decide(similarity_results, drift_reports, similarity_groups)
        except Exception as e:
            errors.append(f"策略决策异常: {e}")

        # 6. 执行决策（仅 scan() 时执行）
        if execute:
            try:
                self._execute_decision(decision, index)
            except Exception as e:
                errors.append(f"执行决策异常: {e}")

        # 7. 记录运行日志
        log = CuratorRunLog(
            run_id=f"curator_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            scanned_count=decision.scanned_count,
            merge_groups=len(decision.merge_groups),
            archived_count=len(set(decision.archived_skills)),
            quarantined_count=len(set(decision.quarantined_skills)),
            downgraded_count=len(set(decision.downgraded_skills)),
            review_count=len(decision.review_skills),
            kept_count=len(set(decision.kept_skills)),
            skipped_count=len(set(decision.skipped_skills)),
            actions_summary=decision.curator_note,
            run_at=datetime.now().isoformat(),
            errors=errors,
        )
        if execute:
            self.curator_logger.append(log)

        return CuratorScanReport(
            scanned_count=decision.scanned_count,
            decision=decision,
            similarity_results=similarity_results,
            drift_reports=drift_reports,
            similarity_groups=similarity_groups,
            errors=errors,
            curator_log=log,
        )

    # ------------------------------------------------------------------
    # Execute decisions
    # ------------------------------------------------------------------

    def _execute_decision(self, decision: CuratorDecision, index: dict[str, Any]) -> None:
        """
        执行 CuratorPolicy 产生的所有操作。
        操作顺序：merge → archive → quarantine → downgrade → keep
        """

        # 1. 执行合并（merge：保留最优，archive 其余）
        for merge_action in decision.merge_groups:
            surviving = merge_action.surviving_id
            for sid in merge_action.skill_ids:
                if sid == surviving:
                    continue
                # 更新索引状态为 merged，引用 surviving
                if sid in index:
                    index[sid]["status"] = "merged"
                    index[sid]["merged_into"] = surviving
                    index[sid]["merged_at"] = datetime.now().isoformat()
                # 移动文件到 archived
                self.registry.archive(sid, reason=f"merged into {surviving}")

        # 2. 执行归档（archive）
        for sid in set(decision.archived_skills):
            # 排除已经在 merge 中处理过的
            merged_ids = {
                ms for ma in decision.merge_groups for ms in ma.skill_ids if ms != ma.surviving_id
            }
            if sid in merged_ids:
                continue
            self.registry.archive(sid, reason="curator: archive by policy")

        # 3. 执行隔离（quarantine）
        for sid in set(decision.quarantined_skills):
            entry = index.get(sid, {})
            risk_profile = {
                "risk_level": entry.get("risk_level", "none"),
                "drift_type": "detected_by_curator",
            }
            # 找对应文件路径
            status = entry.get("status", "draft")
            skill_path = self._skill_path(sid, status)
            self.quarantine_mgr.quarantine_skill(
                skill_md_path=skill_path,
                reason="curator: drift detected",
                quarantine_rules=["curator_drift"],
                risk_profile=risk_profile,
            )
            # 更新 registry 索引
            if sid in index:
                index[sid]["status"] = "quarantined"

        # 4. 执行降级（downgrade：active → draft）
        for sid in set(decision.downgraded_skills):
            self._downgrade_skill(sid)

        # 5. 执行保留（keep：只更新 last_reviewed 字段）
        for sid in set(decision.kept_skills):
            if sid in index:
                index[sid]["last_reviewed"] = datetime.now().isoformat()

        # 6. review_skills 不做自动操作，只记录
        for review in decision.review_skills:
            if review.skill_id in index:
                index[review.skill_id]["curator_review_note"] = review.reason
                index[review.skill_id]["needs_human_review"] = True

        # 统一保存索引
        self.registry._save_index(index)

    def _downgrade_skill(self, skill_id: str) -> None:
        """将 active 技能降级为 draft。"""
        index = self.registry.get_index()
        if skill_id not in index:
            return
        entry = index[skill_id]
        if entry.get("status") != "active":
            return
        # 移动文件
        active_path = self.root / "skills" / "active" / f"{skill_id}.md"
        draft_path = self.root / "skills" / "draft" / f"{skill_id}.md"
        if active_path.exists():
            shutil.move(str(active_path), str(draft_path))
        entry["status"] = "draft"
        entry["downgraded_at"] = datetime.now().isoformat()
        entry["downgraded_by"] = "curator"
        self.registry._save_index(index)

    def _skill_path(self, skill_id: str, status: str) -> Path:
        """根据技能状态返回文件路径。"""
        base = self.root / "skills"
        if status == "active":
            return base / "active" / f"{skill_id}.md"
        elif status == "draft":
            return base / "draft" / f"{skill_id}.md"
        elif status == "archived":
            return base / "archived" / f"{skill_id}.md"
        elif status == "quarantined":
            return base / "quarantine" / f"{skill_id}.md"
        return base / "draft" / f"{skill_id}.md"

    # ------------------------------------------------------------------
    # Review queue (for human-in-the-loop)
    # ------------------------------------------------------------------

    def get_review_queue(self) -> list[dict[str, Any]]:
        """
        返回当前所有待人工复核的技能（来自 quarantine 和 curator review）。
        用于 PhoenixEvo UI 或人工审查流程。
        """
        index = self.registry.get_index()
        queue: list[dict[str, Any]] = []

        # Curator review 列表
        for sid, entry in index.items():
            if entry.get("needs_human_review"):
                queue.append({**entry, "review_type": "curator_review"})

        # Quarantine 待复核列表
        for entry in self.quarantine_mgr.get_pending_review():
            queue.append({**asdict(entry), "review_type": "quarantine_review"})

        return queue


# ----------------------------------------------------------------------
# Scan report
# ----------------------------------------------------------------------

@dataclass
class CuratorScanReport:
    """
    Curator.scan() 返回的完整报告。
    """
    scanned_count: int
    decision: CuratorDecision
    similarity_results: list[SimilarityResult]
    drift_reports: list[SkillHealthReport]
    similarity_groups: list[list[str]]
    errors: list[str]
    curator_log: CuratorRunLog

    @property
    def total_issues(self) -> int:
        return (
            len(self.decision.merge_groups)
            + len(self.decision.quarantined_skills)
            + len(self.decision.downgraded_skills)
            + len(self.decision.review_skills)
        )

    @property
    def needs_attention(self) -> bool:
        """是否有需要人工处理的问题。"""
        return bool(
            self.decision.review_skills
            or self.decision.quarantined_skills
            or self.decision.merge_groups
        )

    def __len__(self) -> int:
        """支持 len() 操作，使 auto_curate 等场景可安全调用。"""
        return self.scanned_count

    def __bool__(self) -> bool:
        """支持 bool() 操作。"""
        return self.needs_attention
