"""
SkillMiner: 技能提取器
V0.1 - Phoenix-Evo
"""

from datetime import datetime
from typing import Any

from .post_task_evaluator import EvaluationResult


class SkillMiner:
    def mine(self, trajectory: dict[str, Any], eval_result: EvaluationResult) -> dict:
        skill_name = eval_result.skill_candidate_name or self._default_name(trajectory)
        inputs       = self._extract_inputs(trajectory)
        procedure    = self._extract_procedure(trajectory)
        validation   = self._extract_validation(trajectory)
        failure_cases = self._extract_failure_cases(trajectory)
        skill_md     = self._render(
            name=skill_name,
            task_goal=trajectory["task_goal"],
            task_type=trajectory["task_type"],
            inputs=inputs,
            procedure=procedure,
            validation=validation,
            failure_cases=failure_cases,
            trajectory_id=trajectory["task_id"],
        )
        return {
            "skill_id": f"{skill_name}_{trajectory['task_id']}",
            "skill_name": skill_name,
            "skill_md": skill_md,
            "inputs": inputs,
            "procedure": procedure,
            "validation": validation,
            "failure_cases": failure_cases,
            "source_trajectory": trajectory["task_id"],
            "quality_score": eval_result.quality_score,
            "mined_at": datetime.now().isoformat(),
        }

    def _default_name(self, traj: dict) -> str:
        goal = traj.get("task_goal", "")[:40].replace(" ", "_").replace("/", "_")
        return f"skill_{goal}"

    def _extract_inputs(self, traj: dict) -> list[dict]:
        inputs = []
        seen = set()
        for tc in traj.get("tool_calls", []):
            args = tc.get("args", {})
            for key, val in args.items():
                if key in seen or not val:
                    continue
                seen.add(key)
                inputs.append({"name": key, "example": str(val)[:80],
                               "source": "tool_call_arg", "required": key in ["path", "goal", "task"]})
        goal = traj.get("task_goal", "")
        for kw in ["文件", "项目", "代码", "文档", "模块", "路径"]:
            if kw in goal and kw not in seen:
                inputs.append({"name": kw, "example": "", "source": "task_goal", "required": True})
        return inputs[:8]

    def _extract_procedure(self, traj: dict) -> list[str]:
        steps = []
        for i, action in enumerate(traj.get("actions", [])):
            name = action.get("action", "unknown")
            params = action.get("params", {})
            if params:
                param_str = ", ".join(f"{k}={v}" for k, v in list(params.items())[:2])
                step = f"{i+1}. {name}({param_str})"
            else:
                step = f"{i+1}. {name}"
            steps.append(step)
        return steps

    def _extract_validation(self, traj: dict) -> list[str]:
        validations = []
        for action in traj.get("actions", []):
            name = action.get("action", "").lower()
            if any(k in name for k in ["verify", "check", "assert", "test", "validate", "confirm"]):
                validations.append("验证: " + action.get("action", "") + " -> " + str(action.get("result", "OK"))[:60])
        if not validations:
            validations.append("[WARNING] 无显式验证步骤，建议添加结果检查。")
        return validations

    def _extract_failure_cases(self, traj: dict) -> list[dict]:
        cases = []
        for err in traj.get("errors", []):
            fix = next((f for f in traj.get("fixes", []) if f.get("phase") == err.get("phase")), {})
            cases.append({
                "error": err.get("message", "")[:120],
                "phase": err.get("phase"),
                "fix": fix.get("strategy", "无记录") if fix else "无修复记录",
                "succeeded": fix.get("succeeded", False) if fix else False,
            })
        return cases

    def _render(self, name: str, task_goal: str, task_type: str, inputs: list[dict],
                procedure: list[str], validation: list[str], failure_cases: list[dict],
                trajectory_id: str) -> str:
        ts = datetime.now().isoformat()
        parts = []
        parts.append(f"# Skill: {name}")
        parts.append("")
        parts.append("## Metadata")
        parts.append(f"- **skill_id**: {name}_{trajectory_id}")
        parts.append(f"- **task_type**: {task_type}")
        parts.append(f"- **source_trajectory**: {trajectory_id}")
        parts.append(f"- **mined_at**: {ts}")
        parts.append("- **status**: draft  <- V0.1 禁止自动激活")
        parts.append("")
        parts.append("## When to Use")
        parts.append(f"当任务目标为： **{task_goal}** 时使用本技能。")
        parts.append("")
        parts.append("## Inputs")
        parts.append("| 参数名 | 必填 | 示例 | 来源 |")
        parts.append("| ------ | ---- | ---- | ---- |")
        for inp in inputs:
            req = "[OK]" if inp.get("required") else "[OPT]"
            ex = inp.get("example", "")[:40]
            parts.append(f"| {inp['name']} | {req} | {ex} | {inp.get('source','')} |")
        parts.append("")
        parts.append("## Procedure")
        for step in (procedure or ["[WARNING] 无步骤记录"]):
            parts.append(step)  # steps already have numbers like "1. xxx"
        parts.append("")
        parts.append("## Validation")
        for v in (validation or ["[WARNING] 无验证步骤"]):
            parts.append(f"- {v}")
        parts.append("")
        parts.append("## Failure Cases")
        parts.append("| 错误阶段 | 错误信息 | 修复策略 | 修复成功 |")
        parts.append("| -------- | -------- | -------- | -------- |")
        for fc in (failure_cases or [{"error": "无", "phase": "-", "fix": "无", "succeeded": True}]):
            ok = "[OK]" if fc.get("succeeded") else "[FAIL]"
            em = fc.get("error", "无")[:50]
            fx = fc.get("fix", "无")[:40]
            ph = fc.get("phase", "-")
            parts.append(f"| {ph} | {em} | {fx} | {ok} |")
        parts.append("")
        parts.append("## Safety Note")
        parts.append("**V0.1 约束**: 本技能来自单一轨迹，未经过多场景验证。")
        parts.append("激活前请确认: (1) 有至少2次成功轨迹支撑 (2) 不涉及高风险操作。")
        parts.append("")
        parts.append("---")
        parts.append(f"*Generated by Phoenix-Evo V0.1 | source: {trajectory_id}*")
        return "\n".join(parts)
