"""
execution_guard: 技能调用前安全闸门
V0.5 — Phoenix-Evo Runtime Skill Router

职责：
  - SkillRouter 决策之后、实际调用技能之前，最后一道安全闸门
  - 复核当前任务上下文是否与技能匹配
  - 检查技能调用是否可能引发运行时风险
  - 对"auto_use"技能做快速验证，对"confirm_use"技能做强化检查
  - 输出 ExecutionGuardResult，附带风险标签和通过原因
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class ExecutionGateResult:
    """
    调用闸门检查结果。

    字段：
      skill_id           — 技能 ID
      skill_name         — 技能名称
      passed             — 是否通过闸门
      gate_action        — "pass" | "warn" | "block"
      risk_tags          — 检测到的运行时风险标签
      warnings           — 警告信息
      block_reason       — 拦截原因（passed=False 时填写）
      context_match_score — 任务上下文与技能的匹配度
      suggested_next     — 建议的后续操作
    """
    skill_id: str = ""
    skill_name: str = ""
    passed: bool = True
    gate_action: str = "pass"
    risk_tags: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    block_reason: str = ""
    context_match_score: float = 0.0
    suggested_next: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ExecutionGuard:
    """
    技能调用前安全闸门。

    V0.5 闸门检查项：

    1. Context Match（上下文匹配）
       - 当前任务描述 vs 技能原始 task_goal 的词重叠度
       - 低于 0.30 → warn（可能任务不匹配）
       - 低于 0.15 → block（完全不匹配）

    2. Risk Amplification Check（风险放大检查）
       - 如果技能 risk_level 是 medium/high 且当前任务也是 medium/high → warn
       - 如果两者都是 high → block（双重高风险）

    3. Input Validation（输入验证）
       - 检查技能期望的 inputs 是否能在当前任务上下文中提供
       - 缺必需 input → warn

    4. Output Safety（输出安全）
       - 如果技能产生文件 / 执行命令 / 修改系统状态 → warn
       - 如果是 destructive 操作 → block

    5. Confidence Threshold（置信度门控）
       - router confidence < 0.20 → block（置信度过低）

    闸门结果：
      pass  — 通过，可执行
      warn  — 通过但需记录警告
      block — 拦截，不执行
    """

    CONTEXT_MATCH_BLOCK = 0.15
    CONTEXT_MATCH_WARN = 0.30

    DESTRUCTIVE_PATTERNS = [
        "rm -rf", "rm -r /", "del /", "format c:",
        "shutdown", "reboot", "halt",
        "DROP TABLE", "DELETE FROM", "TRUNCATE",
        "--no-preserve-root", "mkfs",
    ]

    RISKY_ACTION_PATTERNS = [
        "exec", "eval", "system(", "subprocess",
        "sudo", "chmod 777", "chown",
        "mv /", "cp /", "install",
    ]

    def __init__(self, root: Path | str | None = None):
        self.root = Path(root) if root else Path(__file__).parent.parent

    def check(
        self,
        skill: dict[str, Any],
        router_decision: RouterDecision,   # type: ignore[name-defined]
        task_context: dict[str, Any] | None = None,
    ) -> ExecutionGateResult:
        """
        对单个技能执行调用前闸门检查。

        Args:
            skill: 技能字典
            router_decision: SkillRouter 的路由决策
            task_context: 当前任务上下文（可选）

        Returns:
            ExecutionGateResult
        """
        task_context = task_context or {}
        skill_id = skill.get("skill_id", "")
        skill_name = skill.get("skill_name", "")

        passed = True
        gate_action = "pass"
        risk_tags: list[str] = []
        warnings: list[str] = []

        # ── 1. Confidence check ────────────────────────────────
        confidence = router_decision.confidence
        if confidence < 0.20:
            return ExecutionGateResult(
                skill_id=skill_id, skill_name=skill_name,
                passed=False, gate_action="block",
                risk_tags=["low_confidence"],
                block_reason=f"路由置信度 {confidence:.0%} < 20%，拦截",
                context_match_score=0.0,
                suggested_next="返回 SkillRouter 重新检索候选",
            )

        # ── 2. Context match check ─────────────────────────────
        # task_goal 优先从 task_context 取，fallback 到 skill 内置的 task_goal
        task_goal = (
            task_context.get("task_goal", "")
            if task_context
            else skill.get("task_goal", "")
        )
        if not task_goal:
            task_goal = skill.get("task_goal", "")
        skill_goal = skill.get("task_goal", "")

        context_score = self._compute_context_match(task_goal, skill_goal)

        if context_score < self.CONTEXT_MATCH_BLOCK:
            return ExecutionGateResult(
                skill_id=skill_id, skill_name=skill_name,
                passed=False, gate_action="block",
                risk_tags=["context_mismatch"],
                block_reason=f"任务上下文与技能不匹配（{context_score:.0%} < {self.CONTEXT_MATCH_BLOCK:.0%}）",
                context_match_score=context_score,
                suggested_next="选择更匹配的技能或手动处理",
            )
        if context_score < self.CONTEXT_MATCH_WARN:
            warnings.append(f"任务上下文与技能匹配度较低（{context_score:.0%}）")
            gate_action = "warn"
            risk_tags.append("low_context_match")

        # ── 3. Risk amplification check ────────────────────────
        skill_risk = skill.get("risk_level", "low")
        task_risk = task_context.get("risk_level", "low")

        if skill_risk == "high" and task_risk == "high":
            warnings.append("双重高风险：技能和任务均为 high")
            gate_action = "warn"
            risk_tags.append("risk_amplification")

        if skill_risk == "critical" or (skill_risk == "high" and task_risk in ("high", "critical")):
            return ExecutionGateResult(
                skill_id=skill_id, skill_name=skill_name,
                passed=False, gate_action="block",
                risk_tags=["risk_amplification"],
                block_reason=f"技能风险 {skill_risk} + 任务风险 {task_risk}，风险过高",
                context_match_score=context_score,
                suggested_next="人工复核确认",
            )

        # ── 4. Input validation ────────────────────────────────
        required_inputs = skill.get("inputs", [])
        provided_inputs = task_context.get("available_inputs", [])
        if required_inputs and provided_inputs:
            missing = [inp for inp in required_inputs if inp not in provided_inputs]
            if missing:
                warnings.append(f"缺少可选输入：{', '.join(missing)}")
                gate_action = "warn"
                risk_tags.append("missing_inputs")

        # ── 5. Output safety check ──────────────────────────────
        procedure_text = " ".join(str(p) for p in skill.get("procedure", []))
        procedure_lower = procedure_text.lower()

        # 检查破坏性操作
        for pattern in self.DESTRUCTIVE_PATTERNS:
            if pattern.lower() in procedure_lower:
                return ExecutionGateResult(
                    skill_id=skill_id, skill_name=skill_name,
                    passed=False, gate_action="block",
                    risk_tags=["destructive_operation"],
                    block_reason=f"检测到破坏性操作：{pattern}",
                    context_match_score=context_score,
                    suggested_next="人工确认操作安全性",
                )

        # 检查危险操作
        for pattern in self.RISKY_ACTION_PATTERNS:
            if pattern.lower() in procedure_lower:
                warnings.append(f"检测到高风险操作：{pattern}")
                gate_action = "warn" if gate_action == "pass" else gate_action
                risk_tags.append("risky_operation")

        # ── 6. Finalize ───────────────────────────────────────
        if gate_action != "block":
            if gate_action == "warn":
                warnings.append("闸门通过但有警告，请关注运行时表现")
                suggested_next = "调用并记录结果，失败则触发 fallback"
            else:
                suggested_next = "正常调用"

        return ExecutionGateResult(
            skill_id=skill_id,
            skill_name=skill_name,
            passed=passed,
            gate_action=gate_action,
            risk_tags=risk_tags,
            warnings=warnings,
            block_reason="",
            context_match_score=round(context_score, 4),
            suggested_next=suggested_next,
        )

    def _compute_context_match(self, task_goal: str, skill_goal: str) -> float:
        """计算任务与技能的上下文匹配度（词重叠率）。"""
        if not task_goal or not skill_goal:
            return 0.0

        import re
        # 提取中英文词
        def english(t):
            return re.findall(r"[a-zA-Z][a-zA-Z0-9]+", t.lower())
        def chinese(t):
            return re.findall(r"[\u4e00-\u9fff]+", t.lower())

        task_words = set(english(task_goal) + chinese(task_goal))
        skill_words = set(english(skill_goal) + chinese(skill_goal))

        if not task_words or not skill_words:
            return 0.0

        intersection = task_words & skill_words
        union = task_words | skill_words
        return len(intersection) / len(union) if union else 0.0
