"""
runtime_reporter: 运行时调用记录与效果报告
V0.5 — Phoenix-Evo Runtime Skill Router

职责：
  - 记录每次技能调用的完整上下文和结果
  - 生成 RuntimeReport，包含调用是否成功、用了哪些技能、步数变化等
  - 更新 PhoenixEvo 的轨迹日志（形成下一轮进化数据）
  - 汇总批量调用的统计：复用率、成功率、平均步数变化
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

# ----------------------------------------------------------------------
# RuntimeReport — 单次运行时报告
# ----------------------------------------------------------------------

@dataclass
class SkillInvocation:
    """单次技能调用记录。"""
    skill_id: str = ""
    skill_name: str = ""
    action: str = ""                # router decision action
    confidence: float = 0.0
    guard_passed: bool = False
    guard_warnings: list[str] = field(default_factory=list)
    called: bool = False             # 是否实际调用
    success: bool = False            # 调用是否成功
    execution_time_ms: float = 0.0
    fallback_triggered: bool = False
    fallback_action: str = ""
    error: str = ""


@dataclass
class RuntimeReport:
    """
    单次任务执行的运行时报告。

    字段：
      task_goal            — 任务描述
      task_id              — 任务 ID
      skills_retrieved     — 召回的技能数
      skills_considered    — 路由决策的技能数
      auto_use_count       — 自动调用数
      confirm_use_count    — 需确认数
      review_first_count   — 人工复核数
      blocked_count        — 拦截数
      invocations          — 实际调用列表
      total_execution_ms   — 总执行耗时
      task_success         — 任务是否成功
      skill_reused         — 是否复用了已有技能（vs 新生成）
      reused_skill_ids     — 被复用的技能 ID 列表
      step_delta           — 步数变化（复用技能 vs 从头开始）
      generated_new_skill  — 是否生成了新技能
      improvement_over_baseline — 相比无技能基线的改进幅度
      started_at           — 开始时间
      completed_at         — 完成时间
    """
    task_goal: str = ""
    task_id: str = ""
    skills_retrieved: int = 0
    skills_considered: int = 0
    auto_use_count: int = 0
    confirm_use_count: int = 0
    review_first_count: int = 0
    blocked_count: int = 0
    invocations: list[SkillInvocation] = field(default_factory=list)
    total_execution_ms: float = 0.0
    task_success: bool = False
    skill_reused: bool = False
    reused_skill_ids: list[str] = field(default_factory=list)
    step_delta: float = 0.0
    generated_new_skill: bool = False
    improvement_over_baseline: float = 0.0
    started_at: str = ""
    completed_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["invocations"] = [asdict(i) for i in self.invocations]
        return d

    @property
    def reused_count(self) -> int:
        return len(self.reused_skill_ids)


# ----------------------------------------------------------------------
# RuntimeReporter
# ----------------------------------------------------------------------

class RuntimeReporter:
    """
    运行时调用记录与效果报告生成器。

    职责：
      - 记录每次技能调用的完整上下文和结果
      - 将 RuntimeReport 写入 evidence/runtime_logs/
      - 生成汇总统计：复用率、成功率、平均步数变化
      - 将关键数据反馈给 PhoenixEvo 轨迹日志（形成下一轮进化数据）
    """

    def __init__(self, root: Path | str | None = None):
        self.root = Path(root) if root else Path(__file__).parent.parent
        self.logs_dir = self.root / "evidence" / "runtime_logs"
        self.logs_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Report generation
    # ------------------------------------------------------------------

    def create_report(
        self,
        task_goal: str,
        task_id: str,
        retrieval_count: int,
        routing_result: RouterResult,   # type: ignore[name-defined]
        invocations: list[SkillInvocation],
        execution_time_ms: float,
        task_success: bool,
        generated_new_skill: bool = False,
        baseline_steps: int | None = None,
        actual_steps: int | None = None,
    ) -> RuntimeReport:
        """
        从运行时数据生成 RuntimeReport。

        Args:
            task_goal: 任务描述
            task_id: 任务 ID
            retrieval_count: 召回的候选数
            routing_result: SkillRouter 的路由结果
            invocations: 实际调用记录列表
            execution_time_ms: 总执行耗时
            task_success: 任务是否成功
            generated_new_skill: 是否从本次任务生成了新技能
            baseline_steps: 基线步数（无技能复用）
            actual_steps: 实际步数

        Returns:
            RuntimeReport
        """
        auto_use = len(routing_result.auto_use)
        confirm_use = len(routing_result.confirm_use)
        review_first = len(routing_result.review_first)
        blocked = len(routing_result.blocked)

        reused_ids = [i.skill_id for i in invocations if i.called and i.success]
        skill_reused = len(reused_ids) > 0

        # 步数变化
        step_delta = 0.0
        improvement = 0.0
        if baseline_steps is not None and actual_steps is not None:
            step_delta = actual_steps - baseline_steps
            if baseline_steps > 0:
                improvement = (baseline_steps - actual_steps) / baseline_steps
                improvement = round(improvement, 4)

        report = RuntimeReport(
            task_goal=task_goal,
            task_id=task_id,
            skills_retrieved=retrieval_count,
            skills_considered=routing_result.total_considered,
            auto_use_count=auto_use,
            confirm_use_count=confirm_use,
            review_first_count=review_first,
            blocked_count=blocked,
            invocations=invocations,
            total_execution_ms=round(execution_time_ms, 2),
            task_success=task_success,
            skill_reused=skill_reused,
            reused_skill_ids=reused_ids,
            step_delta=round(step_delta, 4),
            generated_new_skill=generated_new_skill,
            improvement_over_baseline=round(improvement, 4),
            started_at=datetime.now().isoformat(),
            completed_at=datetime.now().isoformat(),
        )

        self.save_report(report)
        return report

    def save_report(self, report: RuntimeReport) -> Path:
        """保存报告到 evidence/runtime_logs/。"""
        path = self.logs_dir / f"runtime_{report.task_id}.report.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(report.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return path

    # ------------------------------------------------------------------
    # Batch statistics
    # ------------------------------------------------------------------

    def get_batch_summary(self, limit: int = 50) -> dict[str, Any]:
        """
        汇总最近 N 次运行时报告，返回关键指标。

        Returns:
            {
                "total_runs": int,
                "skill_reuse_rate": float,
                "task_success_rate": float,
                "avg_step_delta": float,
                "auto_use_rate": float,
                "block_rate": float,
                "avg_improvement": float,
                "top_reused_skills": list[dict],
            }
        """
        reports = self._load_recent_reports(limit)
        if not reports:
            return self._empty_summary()

        total = len(reports)
        reused = sum(1 for r in reports if r.get("skill_reused"))
        success = sum(1 for r in reports if r.get("task_success"))
        step_deltas = [r.get("step_delta", 0.0) for r in reports]
        improvements = [r.get("improvement_over_baseline", 0.0) for r in reports if r.get("improvement_over_baseline") is not None]

        auto_use = sum(1 for r in reports if r.get("auto_use_count", 0) > 0)
        blocked = sum(1 for r in reports if r.get("blocked_count", 0) > 0)

        # Top reused skills
        skill_counts: dict[str, int] = {}
        for r in reports:
            for sid in r.get("reused_skill_ids", []):
                skill_counts[sid] = skill_counts.get(sid, 0) + 1
        top_skills = sorted(skill_counts.items(), key=lambda x: -x[1])[:5]
        top_reused = [{"skill_id": sid, "reuse_count": c} for sid, c in top_skills]

        return {
            "total_runs": total,
            "skill_reuse_rate": round(reused / total, 4),
            "task_success_rate": round(success / total, 4),
            "avg_step_delta": round(sum(step_deltas) / len(step_deltas), 2) if step_deltas else 0.0,
            "auto_use_rate": round(auto_use / total, 4),
            "block_rate": round(blocked / total, 4),
            "avg_improvement": round(sum(improvements) / len(improvements), 4) if improvements else 0.0,
            "top_reused_skills": top_reused,
        }

    def _load_recent_reports(self, limit: int) -> list[dict]:
        reports: list[dict] = []
        if not self.logs_dir.exists():
            return reports

        for p in sorted(self.logs_dir.glob("runtime_*.report.json"), reverse=True)[:limit]:
            try:
                reports.append(json.loads(p.read_text(encoding="utf-8")))
            except (OSError, json.JSONDecodeError):
                continue
        return reports

    def _empty_summary(self) -> dict[str, Any]:
        return {
            "total_runs": 0,
            "skill_reuse_rate": 0.0,
            "task_success_rate": 0.0,
            "avg_step_delta": 0.0,
            "auto_use_rate": 0.0,
            "block_rate": 0.0,
            "avg_improvement": 0.0,
            "top_reused_skills": [],
        }

    # ------------------------------------------------------------------
    # Format
    # ------------------------------------------------------------------

    def format_report_markdown(self, report: RuntimeReport) -> str:
        """将 RuntimeReport 格式化为 Markdown。"""
        reuse_icon = "✅" if report.skill_reused else "❌"
        improvement = f"{report.improvement_over_baseline:+.0%}" if report.improvement_over_baseline else "N/A"

        lines = [
            f"# Runtime Report: {report.task_id}",
            "",
            f"**Task:** {report.task_goal}",
            f"**Success:** {'✅' if report.task_success else '❌'}",
            f"**Skill Reused:** {reuse_icon} {report.reused_count} skills",
            f"**Total Time:** {report.total_execution_ms:.0f}ms",
            "",
            "## Routing Summary",
            "",
            f"- Retrieved: {report.skills_retrieved}",
            f"- Considered: {report.skills_considered}",
            f"- Auto Use: {report.auto_use_count}",
            f"- Confirm Use: {report.confirm_use_count}",
            f"- Review First: {report.review_first_count}",
            f"- Blocked: {report.blocked_count}",
            "",
        ]

        if report.invocations:
            lines.append("## Invocations")
            lines.append("")
            for inv in report.invocations:
                icon = "✅" if inv.success else "❌"
                fb = f" → fallback: {inv.fallback_action}" if inv.fallback_triggered else ""
                lines.append(
                    f"- {icon} **{inv.skill_id}** ({inv.action}, conf={inv.confidence:.0%})"
                    f"{fb} — {inv.execution_time_ms:.0f}ms"
                )
            lines.append("")

        if report.step_delta != 0.0:
            lines.append(f"**Step Delta:** {report.step_delta:+.0f} steps (vs baseline)")
            lines.append(f"**Improvement:** {improvement}")
            lines.append("")

        lines.append(f"*Runtime report generated at {report.completed_at}*")
        return "\n".join(lines)
