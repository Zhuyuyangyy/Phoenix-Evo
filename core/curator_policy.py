"""
curator_policy: Curator 决策策略模块
V0.3 — Phoenix-Evo Curator

职责：
  - 定义 Curator 对各类情况的处理策略（merge / keep / downgrade / archive / quarantine）
  - 将 drift_detector 的报告、skill_similarity 的分组转化为可执行操作
  - 支持人工复核边界情况（review 列表）
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# ----------------------------------------------------------------------
# Decision types
# ----------------------------------------------------------------------

class CuratorAction:
    """Curator 可执行的操作基类。"""


class MergeAction(CuratorAction):
    """合并多个相似技能为一个。"""
    def __init__(self, skill_ids: list[str], surviving_id: str):
        self.skill_ids = skill_ids   # 待合并的所有 skill_id（含 surviving）
        self.surviving_id = surviving_id  # 保留的 skill_id

    def __repr__(self):
        return f"MergeAction({self.skill_ids} -> {self.surviving_id})"


class KeepAction(CuratorAction):
    """保留技能，不做操作。"""
    def __init__(self, skill_id: str, reason: str = ""):
        self.skill_id = skill_id
        self.reason = reason

    def __repr__(self):
        return f"KeepAction({self.skill_id}): {self.reason}"


class DowngradeAction(CuratorAction):
    """将 active 技能降级为 draft（需要人工复核后才能重新激活）。"""
    def __init__(self, skill_id: str, reason: str = ""):
        self.skill_id = skill_id
        self.reason = reason

    def __repr__(self):
        return f"DowngradeAction({self.skill_id}): {self.reason}"


class ArchiveAction(CuratorAction):
    """归档技能（移到 archived 目录，保留记录）。"""
    def __init__(self, skill_id: str, reason: str = ""):
        self.skill_id = skill_id
        self.reason = reason

    def __repr__(self):
        return f"ArchiveAction({self.skill_id}): {self.reason}"


class QuarantineAction(CuratorAction):
    """将技能移入隔离区（需人工复核）。"""
    def __init__(self, skill_id: str, reason: str = ""):
        self.skill_id = skill_id
        self.reason = reason

    def __repr__(self):
        return f"QuarantineAction({self.skill_id}): {self.reason}"


class ReviewAction(CuratorAction):
    """需要人工复核（边界情况，Curator 无法自动决策）。"""
    def __init__(self, skill_id: str, reason: str = ""):
        self.skill_id = skill_id
        self.reason = reason

    def __repr__(self):
        return f"ReviewAction({self.skill_id}): {self.reason}"


# ----------------------------------------------------------------------
# Curator decision record
# ----------------------------------------------------------------------

@dataclass
class CuratorDecision:
    """Curator 一次扫描做出的所有决策。"""
    actions: list[CuratorAction] = field(default_factory=list)
    merge_groups: list[MergeAction] = field(default_factory=list)
    review_skills: list[ReviewAction] = field(default_factory=list)   # 需人工复核
    archived_skills: list[str] = field(default_factory=list)           # 已归档
    quarantined_skills: list[str] = field(default_factory=list)        # 已隔离
    downgraded_skills: list[str] = field(default_factory=list)        # 已降级
    kept_skills: list[str] = field(default_factory=list)              # 已保留
    skipped_skills: list[str] = field(default_factory=list)            # 跳过（无变化）
    scanned_count: int = 0
    curator_note: str = ""

    @property
    def total_actions(self) -> int:
        return len(self.actions)


# ----------------------------------------------------------------------
# Policy engine
# ----------------------------------------------------------------------

class CuratorPolicy:
    """
    Curator 决策策略引擎。

    输入：
      - skill_similarity 的分组结果
      - drift_detector 的健康报告
      - 当前 skill_index

    输出：
      - CuratorDecision（含待执行操作列表）

    策略规则：
      1. 相似分组（score >= 0.60）→ 合并建议（自动执行）
         但若存在 risk_level != "none" 的技能，→ review
      2. drift 严重程度 critical → archive
      3. drift 严重程度 drift → quarantine
      4. drift 严重程度 warning → downgrade
      5. 无风险的 stable 技能 → keep
      6. 长期 stale 且 usage_count = 0 → archive（无复核）
    """

    # 相似度阈值
    MERGE_THRESHOLD = 0.60
    REVIEW_THRESHOLD = 0.40

    def __init__(self, skill_index: dict[str, Any]):
        self.index = skill_index

    # ------------------------------------------------------------------
    # Main policy method
    # ------------------------------------------------------------------

    def decide(
        self,
        similarity_results: list,      # list[SimilarityResult] from skill_similarity
        drift_reports: list,           # list[SkillHealthReport] from drift_detector
        similarity_groups: list[list[str]] | None = None,
    ) -> CuratorDecision:
        """
        综合相似度和漂移报告，做出 Curator 决策。

        Args:
            similarity_results: skill_similarity.compute_pairwise() 的结果
            drift_reports: drift_detector.analyze_all() 的结果
            similarity_groups: 可选，skill_similarity.get_groups() 的结果。
                               如果为 None，用相似度结果动态构建。

        Returns:
            CuratorDecision
        """
        decision = CuratorDecision()
        drift_map = {r.skill_id: r for r in drift_reports}
        all_skill_ids = set(self.index.keys())
        decision.scanned_count = len(all_skill_ids)

        # 1. 处理相似分组
        if similarity_groups is None:
            similarity_groups = self._build_groups(similarity_results)

        for group in similarity_groups:
            if len(group) < 2:
                continue
            [drift_map.get(sid) for sid in group if sid in drift_map]
            # 检查组内是否有风险技能
            risky = any(
                e.get("risk_level") not in ("none", "low")
                for sid in group
                if (e := self.index.get(sid))
            )
            if risky:
                # 有风险技能 → 全部 review，不合并
                for sid in group:
                    decision.review_skills.append(ReviewAction(
                        skill_id=sid,
                        reason=f"相似组内存在风险技能，需人工确认（组: {group}）",
                    ))
            else:
                # 找最优技能作为 surviving
                surviving = self._select_surviving(group)
                to_merge = [sid for sid in group if sid != surviving]
                if to_merge:
                    decision.merge_groups.append(MergeAction(
                        skill_ids=group,
                        surviving_id=surviving,
                    ))
                    for sid in to_merge:
                        decision.archived_skills.append(sid)

        # 2. 处理漂移报告
        already_handled = set()
        for mg in decision.merge_groups:
            already_handled.update(mg.skill_ids)

        for report in drift_reports:
            sid = report.skill_id
            if sid in already_handled:
                continue

            sev = report.overall_severity
            entry = self.index.get(sid, {})
            status = entry.get("status", "draft")

            if sev == "critical":
                decision.archived_skills.append(sid)
                decision.actions.append(ArchiveAction(skill_id=sid, reason=f"critical drift: {report.recommendations}"))
            elif sev == "drift":
                decision.quarantined_skills.append(sid)
                decision.actions.append(QuarantineAction(skill_id=sid, reason=f"drift detected: {report.recommendations}"))
            elif sev == "warning":
                if status == "active":
                    decision.downgraded_skills.append(sid)
                    decision.actions.append(DowngradeAction(skill_id=sid, reason=f"warning drift: {report.recommendations}"))
                else:
                    decision.review_skills.append(ReviewAction(skill_id=sid, reason=f"warning drift: {report.recommendations}"))
            else:  # stable
                decision.kept_skills.append(sid)
                decision.actions.append(KeepAction(skill_id=sid, reason="stable"))

        # 3. 处理完全未出现在 drift_reports 中的技能（stable 但从未被 drift_detector 分析）
        #    drift_detector 只分析 active/draft，所以 archived/rejected 不在此范围
        handled_ids = (
            set(decision.archived_skills)
            | set(decision.quarantined_skills)
            | set(decision.downgraded_skills)
            | set(decision.kept_skills)
            | {a.skill_id for a in decision.review_skills}
        )
        for sid in all_skill_ids:
            if sid in handled_ids:
                continue
            entry = self.index.get(sid, {})
            status = entry.get("status", "")
            if status in ("active", "draft"):
                decision.kept_skills.append(sid)
                decision.actions.append(KeepAction(skill_id=sid, reason="无漂移记录"))

        decision.curator_note = self._build_note(decision)
        return decision

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _build_groups(self, similarity_results: list) -> list[list[str]]:
        """从相似度结果构建连通分量分组。"""
        threshold = self.MERGE_THRESHOLD
        adj: dict[str, set[str]] = {}
        for r in similarity_results:
            if r.score >= threshold:
                adj.setdefault(r.skill_a, set()).add(r.skill_b)
                adj.setdefault(r.skill_b, set()).add(r.skill_a)
        # 确保所有技能节点都在 adj 中（即使无连接也加进去）
        for r in similarity_results:
            if r.skill_a not in adj:
                adj.setdefault(r.skill_a, set())
            if r.skill_b not in adj:
                adj.setdefault(r.skill_b, set())

        visited: set[str] = set()
        groups: list[list[str]] = []

        def dfs(node: str, group: list[str]) -> None:
            visited.add(node)
            group.append(node)
            for nei in adj.get(node, []):
                if nei not in visited:
                    dfs(nei, group)

        for sid in adj:
            if sid not in visited:
                group: list[str] = []
                dfs(sid, group)
                groups.append(group)

        return groups

    def _select_surviving(self, group: list[str]) -> str:
        """
        从相似技能组中选择最优保留技能。
        优先级：usage_count 高 > success_rate 高 > 最近创建 > 第一个
        """
        candidates = []
        for sid in group:
            entry = self.index.get(sid, {})
            usage = entry.get("usage_count", 0)
            sr = entry.get("success_rate") or 0.0
            created = entry.get("created_at", "0")
            candidates.append((sid, usage, sr, created))
        # 按 usage_count 降序，再按 success_rate 降序，再按创建时间降序
        candidates.sort(key=lambda x: (x[1], x[2], x[3]), reverse=True)
        return candidates[0][0] if candidates else group[0]

    def _build_note(self, decision: CuratorDecision) -> str:
        """生成 Curator 扫描摘要。"""
        parts = []
        if decision.merge_groups:
            parts.append(f"发现 {len(decision.merge_groups)} 组相似技能待合并")
        if decision.quarantined_skills:
            parts.append(f"建议隔离 {len(decision.quarantined_skills)} 个漂移技能")
        if decision.downgraded_skills:
            parts.append(f"建议降级 {len(decision.downgraded_skills)} 个 warning 技能")
        if decision.archived_skills:
            parts.append(f"建议归档 {len(decision.archived_skills)} 个失效技能")
        if decision.review_skills:
            parts.append(f"需人工复核 {len(decision.review_skills)} 个边界技能")
        if decision.kept_skills:
            parts.append(f"保留 {len(decision.kept_skills)} 个稳定技能")
        return "; ".join(parts) if parts else "技能库状态健康，无须干预"
