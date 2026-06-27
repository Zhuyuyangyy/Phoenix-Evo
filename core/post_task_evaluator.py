"""
PostTaskEvaluator: 任务后自评器
V0.1 — Phoenix-Evo

职责：读取 trajectory JSON，输出可解释的自评报告。
      包含质量评分、复用潜力评估、失败归因。
      纯本地 LLM-free 规则引擎，评分可解释。
"""

from dataclasses import dataclass
from typing import Any


@dataclass
class EvaluationResult:
    task_success: bool
    quality_score: float          # 0.0–1.0，可解释
    reuse_potential: float       # 0.0–1.0
    should_extract_skill: bool
    reason: str                  # 评分理由，必须可解释
    failure_type: str | None     # 失败归因类型
    root_cause: str | None       # 根本原因描述
    improvement_suggestion: str   # 改进建议
    skill_candidate_name: str | None  # 如果 should_extract_skill=True，输出候选技能名


# ── 失败类型枚举 ──────────────────────────────────────────────

class FailureType:
    NONE               = "none"
    PLANNING           = "planning_failure"       # 任务拆解错误
    TOOL_CALL          = "tool_call_failure"     # 工具调用失败
    CONTEXT_INCOMPLETE = "context_incomplete"     # 上下文不足
    EXECUTION          = "execution_failure"     # 代码/命令写错
    VERIFICATION       = "verification_failure"  # 未检查结果
    MEMORY             = "memory_failure"        # 忘记历史规则
    SAFETY             = "safety_failure"        # 越权/误操作
    UNKNOWN            = "unknown_failure"


# ── 评分维度和权重 ────────────────────────────────────────────

WEIGHTS = {
    "success":          0.30,
    "no_error":         0.20,
    "no_fix":           0.15,   # 无需修复说明执行干净
    "verification":     0.15,   # 有结果验证动作
    "tool_efficiency":  0.10,  # 工具调用次数合理
    "no_repeat":        0.10,   # 无重复 action
}


class PostTaskEvaluator:
    """
    纯规则自评器，无需 LLM 调用。

    使用方式：
        result = PostTaskEvaluator.evaluate(trajectory_dict)
        print(result.should_extract_skill)  # True/False
        print(result.reason)               # 可解释理由
    """

    def __init__(self):
        self._weights = WEIGHTS

    # ── 主入口 ────────────────────────────────────────────────

    @staticmethod
    def evaluate(trajectory: dict[str, Any]) -> EvaluationResult:
        """
        输入 trajectory dict，输出 EvaluationResult。
        """
        evaluator = PostTaskEvaluator()
        return evaluator._evaluate(trajectory)

    # ── 内部评分逻辑 ─────────────────────────────────────────

    def _evaluate(self, traj: dict[str, Any]) -> EvaluationResult:
        scores = self._score_dimensions(traj)
        quality = self._weighted_sum(scores)
        reuse   = self._calc_reuse_potential(traj, quality)
        failure_type, root_cause = self._classify_failure(traj)

        should_extract, skill_name, reason = self._decide_extraction(
            traj, quality, reuse, failure_type
        )
        suggestion = self._gen_improvement(traj, failure_type, root_cause)

        return EvaluationResult(
            task_success=traj.get("success", False),
            quality_score=round(quality, 3),
            reuse_potential=round(reuse, 3),
            should_extract_skill=should_extract,
            reason=reason,
            failure_type=failure_type,
            root_cause=root_cause,
            improvement_suggestion=suggestion,
            skill_candidate_name=skill_name,
        )

    def _score_dimensions(self, traj: dict) -> dict[str, float]:
        s = {}

        # 1. success
        s["success"] = 1.0 if traj.get("success") else 0.0

        # 2. no_error
        errors = traj.get("errors", [])
        s["no_error"] = 0.0 if errors else 1.0

        # 3. no_fix（无需修复说明执行干净）
        fixes = traj.get("fixes", [])
        s["no_fix"] = 1.0 if not fixes else max(0.0, 1.0 - len(fixes) * 0.3)

        # 4. verification（有结果验证动作）
        has_verification = self._has_verification(traj)
        s["verification"] = 1.0 if has_verification else 0.5

        # 5. tool_efficiency（工具调用次数合理，<20为佳）
        tool_calls = traj.get("tool_calls", [])
        n_tools = len(tool_calls)
        if n_tools <= 5:
            s["tool_efficiency"] = 1.0
        elif n_tools <= 15:
            s["tool_efficiency"] = 0.8
        elif n_tools <= 25:
            s["tool_efficiency"] = 0.5
        else:
            s["tool_efficiency"] = 0.2

        # 6. no_repeat（无重复 action）
        actions = traj.get("actions", [])
        action_names = [a.get("action", "") for a in actions]
        repeats = len(action_names) - len(set(action_names))
        s["no_repeat"] = max(0.0, 1.0 - repeats * 0.25)

        return s

    def _has_verification(self, traj: dict) -> bool:
        """判断轨迹中是否有结果验证动作。"""
        for a in traj.get("actions", []):
            name = a.get("action", "").lower()
            if any(k in name for k in ["verify", "check", "assert", "test", "validate", "confirm"]):
                return True
        # tool_calls 中有测试类工具也算
        for tc in traj.get("tool_calls", []):
            t = tc.get("tool", "").lower()
            if any(k in t for k in ["test", "assert", "verify", "lint", "type_check"]):
                return True
        return False

    def _weighted_sum(self, scores: dict[str, float]) -> float:
        total = 0.0
        for key, weight in self._weights.items():
            total += scores.get(key, 0.0) * weight
        return min(1.0, max(0.0, total))

    def _calc_reuse_potential(self, traj: dict, quality: float) -> float:
        """
        复用潜力：任务成功 + 轨迹完整 + 有 artifacts + 无错误
        """
        score = quality * 0.4
        if traj.get("artifacts"):
            score += 0.2
        if len(traj.get("actions", [])) >= 3:
            score += 0.2
        if not traj.get("errors"):
            score += 0.2
        return min(1.0, max(0.0, score))

    def _classify_failure(self, traj: dict) -> tuple[str, str]:
        """对错误进行归因分类。"""
        if not traj.get("errors"):
            return FailureType.NONE, None

        errors = traj["errors"]
        first  = errors[0]
        phase  = first.get("phase", "")
        msg    = first.get("message", "")

        # 按关键词简单归因
        if "not found" in msg.lower() or "enoent" in msg.lower():
            return FailureType.CONTEXT_INCOMPLETE, f"访问了不存在的路径或资源：{msg[:80]}"
        if "permission" in msg.lower() or "denied" in msg.lower():
            return FailureType.SAFETY, f"权限不足：{msg[:80]}"
        if "timeout" in msg.lower() or "timed out" in msg.lower():
            return FailureType.TOOL_CALL, f"工具调用超时：{msg[:80]}"
        if any(k in phase.lower() for k in ["plan", "parse", "intent"]):
            return FailureType.PLANNING, f"规划阶段失败：{msg[:80]}"
        if any(k in phase.lower() for k in ["exec", "run", "code", "write"]):
            return FailureType.EXECUTION, f"执行阶段失败：{msg[:80]}"
        if any(k in msg.lower() for k in ["no such", "attribute", "undefined", "not defined"]):
            return FailureType.EXECUTION, f"代码执行错误：{msg[:80]}"

        return FailureType.UNKNOWN, f"未知原因失败：{msg[:80]}"

    def _decide_extraction(
        self,
        traj: dict,
        quality: float,
        reuse: float,
        failure_type: str,
    ) -> tuple[bool, str | None, str]:
        """
        判断是否应提取技能。
        V0.1 规则：
          - 质量 > 0.7 且 复用潜力 > 0.6 → 应该提取
          - 质量 > 0.7 但 有错误修复 → 应该提取（从修复中学习）
          - 质量 <= 0.5 → 不提取
          - 涉及安全失败 → 不提取
        """
        skill_name = None

        if failure_type in (FailureType.SAFETY, FailureType.PLANNING):
            return False, None, f"失败类型为 {failure_type}，不沉淀为技能以避免错误扩散。"

        if quality > 0.7 or (quality > 0.5 and traj.get("fixes")):
            skill_name = self._infer_skill_name(traj)
            reason = (
                f"质量分={quality:.2f}，复用潜力={reuse:.2f}。"
                f"{'从修复轨迹中提取经验。' if traj.get('fixes') else '高质量完整轨迹，值得沉淀。'}"
            )
            return True, skill_name, reason

        if reuse > 0.5 and quality > 0.5:
            skill_name = self._infer_skill_name(traj)
            return True, skill_name, f"复用潜力较高({reuse:.2f})，可形成候选技能。"

        return False, None, f"质量分={quality:.2f}，未达到提取阈值(>0.7)。"

    def _infer_skill_name(self, traj: dict) -> str:
        """从轨迹中推断技能名称。"""
        goal = traj.get("task_goal", "")
        task_type = traj.get("task_type", "")

        # 从 goal 中提取关键词
        goal_clean = goal.replace("请", "").replace("帮我", "").replace("生成", "")
        words = goal_clean[:40].strip()

        type_map = {
            "coding":       "code",
            "writing":      "write",
            "research":     "research",
            "planning":     "plan",
            "debugging":    "debug",
            "general":      "task",
        }
        prefix = type_map.get(task_type, "task")
        return f"{prefix}_{words.replace(' ', '_')[:30]}"

    def _gen_improvement(
        self,
        traj: dict,
        failure_type: str,
        root_cause: str | None,
    ) -> str:
        """生成改进建议。"""
        suggestions = []

        if traj.get("errors") and not traj.get("fixes"):
            suggestions.append("发生错误但未修复，建议任务循环中增加 fix 记录和重试机制。")

        if not self._has_verification(traj):
            suggestions.append("缺少结果验证步骤，建议在执行后增加 check/verify 动作。")

        n_tools = len(traj.get("tool_calls", []))
        if n_tools > 20:
            suggestions.append(f"工具调用次数偏多({n_tools})，建议优化任务拆解，减少绕路。")

        if traj.get("fixes") and not all(f.get("succeeded") for f in traj.get("fixes", [])):
            suggestions.append("存在未成功的修复尝试，建议分析 fix 失败原因并更新策略。")

        if failure_type == FailureType.CONTEXT_INCOMPLETE:
            suggestions.append("上下文不足，建议先读取相关文件确认状态再执行。")

        if failure_type == FailureType.EXECUTION:
            suggestions.append("执行失败，建议在写代码/命令后加入 dry-run 或语法检查。")

        if not suggestions:
            suggestions.append("任务执行良好，可考虑将成功流程固化为技能。")

        return " | ".join(suggestions)
