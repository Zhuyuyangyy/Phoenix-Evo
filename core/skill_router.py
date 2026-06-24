"""
skill_router: 技能路由决策引擎
V0.5 — Phoenix-Evo Runtime Skill Router

职责：
  - 接收 SkillRetrievalResult，决定如何处理每个候选技能
  - 结合风险等级、evidence 分数、replay 结果、当前任务类型做最终决策
  - 路由结果：
      auto_use     — 最高置信，可自动调用
      confirm_use  — 中等置信，需人工确认
      review_first — 低置信，进入人工复核
      blocked      — 高风险 / 已降级，禁止调用
  - 为每个候选计算最终置信分数
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

# ----------------------------------------------------------------------
# RouterDecision
# ----------------------------------------------------------------------

@dataclass
class RouterDecision:
    """
    单个技能的路由决策。

    字段：
      skill_id        — 技能 ID
      skill_name      — 技能名称
      action          — 路由动作
      confidence      — 置信度 0.0 ~ 1.0
      reason          — 决策理由
      conditions      — 满足的晋升条件列表
      concerns        — 未满足的条件 / 风险点
      suggested_review_level — 建议复核级别
    """
    skill_id: str = ""
    skill_name: str = ""
    action: str = "blocked"
    confidence: float = 0.0
    reason: str = ""
    conditions: list[str] = field(default_factory=list)
    concerns: list[str] = field(default_factory=list)
    suggested_review_level: str = "none"  # "none" | "light" | "full"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class RouterResult:
    """
    完整路由结果。

    字段：
      task_goal        — 原始任务
      selected_skills  — 选中的技能（auto_use + confirm_use）
      auto_use         — 可自动调用的技能（最高置信）
      confirm_use      — 需确认的技能
      review_first     — 需人工复核的技能
      blocked          — 被拦截的技能
      total_considered — 考虑的总候选数
      routing_time_ms  — 路由耗时
    """
    task_goal: str
    selected_skills: list[RouterDecision] = field(default_factory=list)
    auto_use: list[RouterDecision] = field(default_factory=list)
    confirm_use: list[RouterDecision] = field(default_factory=list)
    review_first: list[RouterDecision] = field(default_factory=list)
    blocked: list[RouterDecision] = field(default_factory=list)
    total_considered: int = 0
    routing_time_ms: float = 0.0


# ----------------------------------------------------------------------
# SkillRouter
# ----------------------------------------------------------------------

class SkillRouter:
    """
    技能路由决策引擎。

    V0.5 决策矩阵：

    维度：
      - evidence_score   (0.0~1.0): 证据链完整度
      - replay_pass_rate (0.0~1.0): 回放通过率
      - risk_level       (none/low/medium/high/critical)
      - promotion_ready  (bool): 是否已通过 evidence gate

    决策规则：
      auto_use（自动调用）：
        evidence >= 0.6
        AND replay_pass_rate >= 0.70
        AND risk_level in (none, low)
        AND promotion_ready == True

      confirm_use（需确认）：
        evidence >= 0.4
        AND replay_pass_rate >= 0.50
        AND risk_level in (none, low, medium)
        AND NOT blocked by other rules

      review_first（人工复核）：
        evidence >= 0.2
        OR replay_pass_rate >= 0.30
        OR (promotion_ready == True AND evidence >= 0.5)

      blocked（拦截）：
        risk_level == critical
        OR (replay_pass_rate < 0.30 AND evidence < 0.4)
        OR risk_level == high AND replay_passed == False
        OR skill in (archived, quarantine)

    置信度计算：
      base = evidence_score × 0.40 + replay_pass_rate × 0.40 + safety × 0.20
      safety = 1.0 if risk in (none, low) else 0.5 if risk == medium else 0.0
    """

    # Thresholds
    AUTO_USE_EVIDENCE_THRESHOLD = 0.60
    AUTO_USE_REPLAY_THRESHOLD = 0.70
    CONFIRM_EVIDENCE_THRESHOLD = 0.40
    CONFIRM_REPLAY_THRESHOLD = 0.50
    REVIEW_EVIDENCE_THRESHOLD = 0.20
    REVIEW_REPLAY_THRESHOLD = 0.30

    # Risk levels
    SAFE_RISK_LEVELS = {"none", "low"}
    MEDIUM_RISK_LEVELS = {"none", "low", "medium"}
    BLOCKED_RISK_LEVELS = {"critical"}

    def __init__(self, root: Path | str | None = None):
        self.root = Path(root) if root else Path(__file__).parent.parent

    def route(
        self,
        retrieval_result: SkillRetrievalResult,   # type: ignore[name-defined]
        task_risk: str = "low",
    ) -> RouterResult:
        """
        对检索结果做路由决策。

        Args:
            retrieval_result: SkillRetriever 返回的检索结果
            task_risk: 当前任务的风险等级（影响部分决策）

        Returns:
            RouterResult
        """
        import time
        t0 = time.monotonic()

        auto_use: list[RouterDecision] = []
        confirm_use: list[RouterDecision] = []
        review_first: list[RouterDecision] = []
        blocked: list[RouterDecision] = []

        for match in retrieval_result.matches:
            decision = self._decide_single(match, task_risk)

            if decision.action == "auto_use":
                auto_use.append(decision)
            elif decision.action == "confirm_use":
                confirm_use.append(decision)
            elif decision.action == "review_first":
                review_first.append(decision)
            else:
                blocked.append(decision)

        elapsed_ms = (time.monotonic() - t0) * 1000
        selected = auto_use + confirm_use

        return RouterResult(
            task_goal=retrieval_result.task_goal,
            selected_skills=selected,
            auto_use=auto_use,
            confirm_use=confirm_use,
            review_first=review_first,
            blocked=blocked,
            total_considered=len(retrieval_result.matches),
            routing_time_ms=round(elapsed_ms, 2),
        )

    def _decide_single(
        self,
        match: RetrievalMatch,   # type: ignore[name-defined]
        task_risk: str,
    ) -> RouterDecision:
        """
        对单个候选技能做决策。
        """
        skill_id = match.skill_id
        skill_name = match.skill_name
        evidence = match.evidence_score
        replay_rate = match.replay_pass_rate
        replay_passed = match.replay_passed
        risk = match.risk_level
        promotion_ready = match.promotion_ready

        conditions: list[str] = []
        concerns: list[str] = []

        # 计算综合置信度
        safety = 1.0 if risk in self.SAFE_RISK_LEVELS else 0.5 if risk == "medium" else 0.0
        confidence = round(
            evidence * 0.40
            + replay_rate * 0.40
            + safety * 0.20,
            4,
        )

        # ── BLOCKED ──
        if risk == "critical":
            decision = "blocked"
            concerns.append("风险等级 critical")
            reason = "风险等级为 critical，直接拦截"
            return RouterDecision(
                skill_id=skill_id, skill_name=skill_name, action=decision,
                confidence=0.0, reason=reason, conditions=conditions,
                concerns=concerns, suggested_review_level="full",
            )

        if replay_passed is False and replay_rate < 0.30 and evidence < 0.4:
            decision = "blocked"
            concerns.append("回放未通过且证据不足")
            reason = "回放失败且证据链不完整，风险过高，拦截"
            return RouterDecision(
                skill_id=skill_id, skill_name=skill_name, action=decision,
                confidence=confidence, reason=reason, conditions=conditions,
                concerns=concerns, suggested_review_level="full",
            )

        if risk == "high" and replay_passed is False:
            decision = "blocked"
            concerns.append("高风险且回放未通过")
            reason = "高风险技能且回放验证未通过，拦截"
            return RouterDecision(
                skill_id=skill_id, skill_name=skill_name, action=decision,
                confidence=confidence, reason=reason, conditions=conditions,
                concerns=concerns, suggested_review_level="full",
            )

        # ── AUTO USE ──
        auto_conditions = [
            evidence >= self.AUTO_USE_EVIDENCE_THRESHOLD,
            replay_rate >= self.AUTO_USE_REPLAY_THRESHOLD,
            risk in self.SAFE_RISK_LEVELS,
            promotion_ready,
        ]

        if all(auto_conditions):
            conditions.extend([
                f"evidence {evidence:.0%} >= {self.AUTO_USE_EVIDENCE_THRESHOLD:.0%}",
                f"replay_pass_rate {replay_rate:.0%} >= {self.AUTO_USE_REPLAY_THRESHOLD:.0%}",
                f"risk_level {risk} in safe list",
                "promotion_ready == True",
            ])
            return RouterDecision(
                skill_id=skill_id, skill_name=skill_name, action="auto_use",
                confidence=confidence,
                reason="所有自动调用条件满足，可自动调用",
                conditions=conditions, concerns=[],
                suggested_review_level="none",
            )

        # ── CONFIRM USE ──
        confirm_conditions = [
            evidence >= self.CONFIRM_EVIDENCE_THRESHOLD,
            replay_rate >= self.CONFIRM_REPLAY_THRESHOLD,
            risk in self.MEDIUM_RISK_LEVELS,
        ]

        if all(confirm_conditions):
            conditions.extend([
                f"evidence {evidence:.0%} >= {self.CONFIRM_EVIDENCE_THRESHOLD:.0%}",
                f"replay_pass_rate {replay_rate:.0%} >= {self.CONFIRM_REPLAY_THRESHOLD:.0%}",
                f"risk_level {risk} in medium-safe list",
            ])
            return RouterDecision(
                skill_id=skill_id, skill_name=skill_name, action="confirm_use",
                confidence=confidence,
                reason="满足人工确认条件，请确认后调用",
                conditions=conditions, concerns=[],
                suggested_review_level="light",
            )

        # ── REVIEW FIRST ──
        review_conditions = [
            evidence >= self.REVIEW_EVIDENCE_THRESHOLD,
            replay_rate >= self.REVIEW_REPLAY_THRESHOLD,
        ]

        if any(review_conditions):
            if evidence >= 0.5 and promotion_ready:
                conditions.append("promotion_ready 且 evidence >= 50%")
                reason = "有晋级资格但未完全满足自动条件，建议人工复核"
            else:
                conditions.append(f"evidence {evidence:.0%} >= {self.REVIEW_EVIDENCE_THRESHOLD:.0%} OR replay >= {self.REVIEW_REPLAY_THRESHOLD:.0%}")
                reason = "满足部分条件，建议人工复核后决定是否调用"
            concerns.append("未满足自动或确认条件，需人工介入")
            return RouterDecision(
                skill_id=skill_id, skill_name=skill_name, action="review_first",
                confidence=confidence,
                reason=reason, conditions=conditions, concerns=concerns,
                suggested_review_level="full",
            )

        # ── DEFAULT: blocked（不满足最低条件）──
        concerns.append("未满足最低调用条件")
        return RouterDecision(
            skill_id=skill_id, skill_name=skill_name, action="blocked",
            confidence=0.0,
            reason="证据和回放均未达到最低阈值，拦截",
            conditions=conditions, concerns=concerns,
            suggested_review_level="full",
        )

    def format_routing_summary(self, result: RouterResult) -> str:
        """生成路由结果摘要文本。"""
        lines = [
            f"[SkillRouter] 任务: {result.task_goal}",
            f"考虑候选: {result.total_considered} 个",
            f"路由耗时: {result.routing_time_ms:.1f}ms",
            "",
        ]
        if result.auto_use:
            lines.append(f"✅ 自动调用 ({len(result.auto_use)}):")
            for s in result.auto_use:
                lines.append(f"   [{s.skill_id}] {s.skill_name} (置信 {s.confidence:.0%})")
        if result.confirm_use:
            lines.append(f"⚠️  需确认 ({len(result.confirm_use)}):")
            for s in result.confirm_use:
                lines.append(f"   [{s.skill_id}] {s.skill_name} (置信 {s.confidence:.0%})")
        if result.review_first:
            lines.append(f"🔍 人工复核 ({len(result.review_first)}):")
            for s in result.review_first:
                lines.append(f"   [{s.skill_id}] {s.skill_name} (置信 {s.confidence:.0%})")
        if result.blocked:
            lines.append(f"🚫 拦截 ({len(result.blocked)}):")
            for s in result.blocked:
                lines.append(f"   [{s.skill_id}] {s.skill_name} — {s.reason}")
        return "\n".join(lines)
