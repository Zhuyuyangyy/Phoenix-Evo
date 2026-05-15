"""
replay_reporter: 回放报告生成与证据汇总
V0.4 — Phoenix-Evo Evidence & Replay

职责：
  - 将 ReplayReport 格式化为可读报告（dict / markdown）
  - 生成证据摘要（evidence summary）：技能的整体证据健康度评分
  - 生成技能晋级建议
  - 支持批量报告汇总（用于 benchmark 结果展示）
"""

from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Any


# ----------------------------------------------------------------------
# EvidenceSummary — 技能证据健康度报告
# ----------------------------------------------------------------------

@dataclass
class EvidenceSummary:
    """
    技能整体证据健康度评分（0-100 分）。
    
    维度：
      - evidence_completeness：证据链是否完整（有无 card、trajectory_id、来源）
      - replay_validity：回放验证是否通过
      - risk_safety：风险是否安全
      - longevity：技能是否长期稳定
    """
    skill_id: str
    skill_name: str
    evidence_completeness: float   # 0.0 ~ 1.0
    replay_validity: float          # 0.0 ~ 1.0
    risk_safety: float             # 0.0 ~ 1.0
    longevity: float               # 0.0 ~ 1.0
    overall_score: float           # 0.0 ~ 100
    verdict: str                   # "strong" | "moderate" | "weak" | "insufficient"
    verdict_note: str
    promotion_recommended: bool
    concerns: list[str]
    summary_at: str


# ----------------------------------------------------------------------
# ReplayReporter
# ----------------------------------------------------------------------

class ReplayReporter:
    """
    将回放报告转化为可读格式，生成证据汇总。

    核心方法：
      - format_report(replay_report) → 可读 dict
      - format_markdown(replay_report) → markdown 文本
      - build_evidence_summary(skill_card, replay_report) → EvidenceSummary
      - batch_summary(replay_reports) → 批量汇总
    """

    def __init__(self, root: Path | str | None = None):
        self.root = Path(root) if root else Path(__file__).parent.parent

    # ------------------------------------------------------------------
    # Format replay report
    # ------------------------------------------------------------------

    def format_report(self, report: "ReplayReport") -> dict[str, Any]:
        """
        将 ReplayReport 转为可读 dict（用于 API 返回或 JSON 序列化）。
        """
        return {
            "report_id": report.report_id,
            "skill_id": report.skill_id,
            "replayed_at": report.replayed_at,
            "summary": {
                "total_cases": report.total_cases,
                "passed_cases": report.passed_cases,
                "pass_rate": f"{report.pass_rate:.0%}",
                "overall_pass": report.overall_pass,
                "success_delta": f"{report.success_delta:+.2f}",
                "error_delta": f"{report.error_delta:+.2f}",
                "risk_delta": f"{report.risk_delta:+.2f}",
                "step_delta": f"{report.step_delta:+.2f}",
                "regression_found": report.regression_found,
                "recommendation": report.recommendation,
            },
            "results": [
                {
                    "case_id": r.case_id,
                    "passed": r.passed,
                    "success_delta": f"{r.success_delta:+.2f}",
                    "error_delta": f"{r.error_delta:+.2f}",
                    "risk_delta": f"{r.risk_delta:+.2f}",
                    "regression": r.regression_found,
                    "reason": r.reason,
                }
                for r in report.results
            ],
        }

    def format_markdown(self, report: "ReplayReport") -> str:
        """
        将 ReplayReport 转为 Markdown 文本（用于文档或报告输出）。
        """
        lines = [
            f"# Replay Report: {report.skill_id}",
            "",
            f"**Report ID:** `{report.report_id}`",
            f"**Replayed At:** {report.replayed_at}",
            f"**Skill ID:** `{report.skill_id}`",
            "",
            "## Summary",
            "",
            f"- **Total Cases:** {report.total_cases}",
            f"- **Passed Cases:** {report.passed_cases}",
            f"- **Pass Rate:** {report.pass_rate:.0%}",
            f"- **Overall Pass:** {'✅ Yes' if report.overall_pass else '❌ No'}",
            f"- **Success Delta:** {report.success_delta:+.2f}",
            f"- **Error Delta:** {report.error_delta:+.2f}",
            f"- **Risk Delta:** {report.risk_delta:+.2f}",
            f"- **Step Delta:** {report.step_delta:+.2f}",
            f"- **Regression Found:** {'⚠️ Yes' if report.regression_found else '✅ No'}",
            f"- **Recommendation:** `{report.recommendation}`",
            "",
            "## Case Results",
            "",
            "| Case | Passed | Success Δ | Error Δ | Risk Δ | Regression | Reason |",
            "|------|--------|-----------|---------|--------|-----------|--------|",
        ]
        for r in report.results:
            reg_icon = "⚠️ Yes" if r.regression_found else "No"
            pass_icon = "✅" if r.passed else "❌"
            lines.append(
                f"| {r.case_id} | {pass_icon} | {r.success_delta:+.2f} | "
                f"{r.error_delta:+.2f} | {r.risk_delta:+.2f} | {reg_icon} | "
                f"{r.reason[:60]} |"
            )
        lines.append("")
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Evidence summary
    # ------------------------------------------------------------------

    def build_evidence_summary(
        self,
        skill_card: "SkillCard",
        replay_report: "ReplayReport | None" = None,
    ) -> EvidenceSummary:
        """
        根据技能证据卡和回放报告，生成整体证据健康度评分。

        Args:
            skill_card: SkillCard 实例
            replay_report: 可选，ReplayReport 实例

        Returns:
            EvidenceSummary
        """
        skill_id = skill_card.skill_id
        skill_name = skill_card.skill_name

        # 1. Evidence Completeness（0.0 ~ 1.0）
        ec_score = 0.0
        ec_reasons: list[str] = []
        if skill_card.source_trajectory_ids:
            ec_score += 0.4
            ec_reasons.append("有来源轨迹")
        if skill_card.task_goal:
            ec_score += 0.2
            ec_reasons.append("有原始任务目标")
        if skill_card.verified_by:
            ec_score += 0.2
            ec_reasons.append(f"通过 {len(skill_card.verified_by)} 个验证器")
        if skill_card.procedure_steps >= 3:
            ec_score += 0.2
            ec_reasons.append(f"步骤数 {skill_card.procedure_steps} >= 3")
        evidence_completeness = min(ec_score, 1.0)

        # 2. Replay Validity（0.0 ~ 1.0）
        rv_score = 0.0
        rv_reasons: list[str] = []
        if replay_report is None:
            rv_score = 0.0
            rv_reasons.append("未进行回放验证")
        else:
            rv_score = replay_report.pass_rate
            rv_reasons.append(f"回放通过率 {replay_report.pass_rate:.0%}")
            if replay_report.regression_found:
                rv_score *= 0.3
                rv_reasons.append("⚠️ 发现回归，降权")
        replay_validity = min(rv_score, 1.0)

        # 3. Risk Safety（0.0 ~ 1.0）
        risk_order = {"none": 1.0, "low": 0.8, "medium": 0.5, "high": 0.2, "critical": 0.0}
        risk_safety = risk_order.get(skill_card.risk_level, 0.5)
        if replay_report and replay_report.risk_delta > 0:
            risk_safety *= (1.0 - replay_report.risk_delta)
        risk_safety = max(risk_safety, 0.0)

        # 4. Longevity（0.0 ~ 1.0）
        total_replay = skill_card.replay_pass_count + skill_card.replay_fail_count
        if total_replay == 0:
            longevity = 0.3  # 未回放过，打折
        else:
            longevity = skill_card.replay_pass_count / total_replay
        longevity = min(longevity, 1.0)

        # 综合评分（加权平均）
        overall = (
            evidence_completeness * 0.25
            + replay_validity * 0.40
            + risk_safety * 0.20
            + longevity * 0.15
        )
        overall_score = round(overall * 100, 1)

        # Verdict
        if overall_score >= 75:
            verdict = "strong"
            verdict_note = "证据链完整，回放通过率高，风险安全，适合晋级"
            promotion_recommended = True
        elif overall_score >= 50:
            verdict = "moderate"
            verdict_note = "证据基本完整，回放效果一般，建议补充更多验证"
            promotion_recommended = False
        elif overall_score >= 25:
            verdict = "weak"
            verdict_note = "证据不完整或回放效果差，建议隔离待人工复核"
            promotion_recommended = False
        else:
            verdict = "insufficient"
            verdict_note = "证据严重不足，建议拒绝或归档"
            promotion_recommended = False

        concerns = []
        if evidence_completeness < 0.6:
            concerns.append("证据链不完整")
        if replay_validity < 0.5:
            concerns.append("回放验证效果不佳")
        if risk_safety < 0.5:
            concerns.append("风险评分不安全")
        if longevity < 0.3:
            concerns.append("长期稳定性未知")

        return EvidenceSummary(
            skill_id=skill_id,
            skill_name=skill_name,
            evidence_completeness=round(evidence_completeness, 4),
            replay_validity=round(replay_validity, 4),
            risk_safety=round(risk_safety, 4),
            longevity=round(longevity, 4),
            overall_score=overall_score,
            verdict=verdict,
            verdict_note=verdict_note,
            promotion_recommended=promotion_recommended,
            concerns=concerns,
            summary_at=datetime.now().isoformat(),
        )

    def format_summary_markdown(self, summary: EvidenceSummary) -> str:
        """将 EvidenceSummary 格式化为 Markdown。"""
        verdict_icon = {"strong": "🟢", "moderate": "🟡", "weak": "🟠", "insufficient": "🔴"}
        icon = verdict_icon.get(summary.verdict, "⚪")
        promo = "✅ 推荐晋级" if summary.promotion_recommended else "❌ 暂不晋级"

        lines = [
            f"# Evidence Summary: {summary.skill_id}",
            "",
            f"**Skill Name:** {summary.skill_name}",
            f"**Overall Score:** {summary.overall_score}/100 {icon} **{summary.verdict}**",
            f"**Promotion:** {promo}",
            "",
            "## Score Breakdown",
            "",
            f"- **Evidence Completeness:** {summary.evidence_completeness:.0%}",
            f"  - 证据链是否完整（来源轨迹、任务目标、验证器、步骤数）",
            f"- **Replay Validity:** {summary.replay_validity:.0%}",
            f"  - 回放验证通过率",
            f"- **Risk Safety:** {summary.risk_safety:.0%}",
            f"  - 风险等级与回放风险变化",
            f"- **Longevity:** {summary.longevity:.0%}",
            f"  - 长期回放成功率",
            "",
            f"**Verdict:** {summary.verdict_note}",
            "",
        ]
        if summary.concerns:
            lines.append("**Concerns:**")
            for c in summary.concerns:
                lines.append(f"  - ⚠️ {c}")
            lines.append("")
        lines.append(f"*Generated at: {summary.summary_at}*")
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Batch summary
    # ------------------------------------------------------------------

    def batch_summary(
        self,
        reports: list["ReplayReport"],
        skill_cards: dict[str, "SkillCard"],
    ) -> dict[str, Any]:
        """
        批量回放报告汇总（用于展示多个技能的回放结果）。
        """
        if not reports:
            return {
                "total_skills": 0,
                "total_passed": 0,
                "overall_pass_rate": 0.0,
                "average_success_delta": 0.0,
                "average_risk_delta": 0.0,
                "regression_count": 0,
                "recommendations": {},
            }

        total_passed = sum(1 for r in reports if r.overall_pass)
        total_regression = sum(1 for r in reports if r.regression_found)

        rec_counts: dict[str, int] = {}
        for r in reports:
            rec_counts[r.recommendation] = rec_counts.get(r.recommendation, 0) + 1

        return {
            "total_skills": len(reports),
            "total_passed": total_passed,
            "overall_pass_rate": f"{total_passed / len(reports):.0%}",
            "average_success_delta": f"{sum(r.success_delta for r in reports) / len(reports):+.2f}",
            "average_error_delta": f"{sum(r.error_delta for r in reports) / len(reports):+.2f}",
            "average_risk_delta": f"{sum(r.risk_delta for r in reports) / len(reports):+.2f}",
            "regression_count": total_regression,
            "recommendations": rec_counts,
        }
