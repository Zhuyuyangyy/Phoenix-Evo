"""
ContextInjector: 把 SkillCard 转换为 Hermes 可读的上下文字符串
V0.6 - Phoenix-Evo Runtime Skill Router

注入格式：
  ## Relevant Skill: {skill_name}
  **When to use**: xxx
  **Steps**:
    1. xxx
  **Constraints**: xxx
  **Evidence score**: 0.82 | **Replay pass**: 0.85 | **Success rate**: 0.88
  **Risk level**: medium
  **Risk notes**: xxx
  *Skill ID: xxx | Route score: 0.732*

只注入必要信息，不塞整个 SkillCard。
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from runtime.skill_router import RouteResult


class ContextInjector:
    """
    把 RouteResult（已通过 RuntimeGuard）转换为 Hermes LLM 上下文字符串。
    输出格式与 Hermes /skills 格式对齐。
    """

    def inject(
        self,
        skill: "RouteResult" = None,
        task_description: str = "",
        route_result: "RouteResult" = None,
    ) -> str:
        """
        主注入方法。

        参数:
            skill: RouteResult 对象（PhoenixRuntime 传入时的参数名）
            task_description: 当前任务描述（未使用，保留接口兼容）
            route_result: RouteResult 对象（别名）

        返回:
            Hermes LLM 可读的上下文字符串
        """
        rr = skill if skill is not None else route_result
        if rr is None:
            return ""

        entry = getattr(rr, "_index_entry", {})
        card  = getattr(rr, "_skill_card", {})

        return self._build_context(rr=rr, entry=entry, card=card)

    def inject_batch(self, route_results: list["RouteResult"]) -> str:
        """批量注入多个 skill（用于多候选建议场景）"""
        lines = ["[Relevant Skills]", ""]
        for i, rr in enumerate(route_results, 1):
            lines.append(f"--- Skill {i} ---")
            lines.append(self.inject(skill=rr))
            lines.append("")
        return chr(10).join(lines)

    @staticmethod
    def _build_context(
        rr: "RouteResult",
        entry: dict,
        card: dict,
    ) -> str:
        # ---- When to Use ----
        when_to_use = card.get("when to use", "")
        if not when_to_use:
            when_to_use = card.get("when_to_use", "")

        # ---- Procedure ----
        procedure = card.get("procedure", "")
        if procedure:
            steps = []
            for line in procedure.splitlines():
                line = line.strip()
                if line and (line[0].isdigit() or line.startswith("- ")):
                    steps.append(line)
            procedure_text = chr(10).join(f"  {s}" for s in steps) if steps else procedure
        else:
            procedure_text = "(no steps)"

        # ---- Constraints ----
        validation = card.get("validation", "")
        constraints = ""
        if validation:
            constraints = validation.splitlines()[0].strip() if chr(10) in validation else validation
        if not constraints:
            constraints = "(no special constraints)"

        # ---- Risk notes ----
        safety = card.get("safety note", "")
        risk_notes = safety if safety else "(no risk notes)"

        # ---- Evidence & Replay ----
        ev = getattr(rr, "evidence_score", None)
        rr_rate = getattr(rr, "replay_pass_rate", None)
        rs = getattr(rr, "runtime_success_rate", None)

        evidence_str = f"{ev:.2f}" if ev else "N/A"
        replay_str   = f"{rr_rate:.2f}" if rr_rate else "N/A"
        f"{rs:.2f}" if rs else "N/A"

        # ---- Usage stats ----
        usage_count   = entry.get("usage_count", 0)
        success_count = entry.get("success_count", 0)
        success_rate  = entry.get("success_rate")
        if success_rate is not None:
            success_str = f"{float(success_rate):.2f}"
        else:
            success_str = f"{success_count}/{usage_count}" if usage_count else "0/0"

        # ---- Risk level ----
        risk_level = entry.get("risk_level", "unknown")

        # ---- Route score ----
        route_score = getattr(rr, "route_score", None)
        score_str = f"{route_score:.3f}" if route_score else "N/A"

        # ---- Build output ----
        lines = [
            f"## Relevant Skill: {rr.skill_name}",
            "",
            f"**When to use**: {when_to_use}",
            "",
            "**Steps**:",
            procedure_text,
            "",
            f"**Constraints**: {constraints}",
            "",
            f"**Evidence score**: {evidence_str} | **Replay pass**: {replay_str} | **Success rate**: {success_str}",
            f"**Risk level**: {risk_level}",
            "",
            f"**Risk notes**: {risk_notes}",
            "",
            f"*Skill ID: {rr.skill_id} | Route score: {score_str}*",
        ]
        return chr(10).join(lines)


def attach_skill_data_to_route(route_result, index_entry, skill_card):
    """
    将 index_entry 和 skill_card 临时附加到 RouteResult 上，
    供 ContextInjector.inject() 使用。
    """
    route_result._index_entry = index_entry
    route_result._skill_card  = skill_card
    return route_result
