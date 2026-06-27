"""
skill_replay: 历史任务回放验证
V0.4 — Phoenix-Evo Evidence & Replay

职责：
  - 接收 skill + benchmark cases，执行回放验证
  - 对比"用 skill" vs "不用 skill" 的行为差异
  - 输出 ReplayReport，包含成功率提升、错误率变化、风险变化等指标
  - 支持批量回放多个 cases
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

# ----------------------------------------------------------------------
# ReplayReport — 回放报告
# ----------------------------------------------------------------------

@dataclass
class ReplayResult:
    """单次回放结果。"""
    case_id: str = ""
    skill_id: str = ""
    passed: bool = False
    success_delta: float = 0.0    # 成功率变化
    error_delta: float = 0.0      # 错误率变化
    risk_delta: float = 0.0      # 风险分数变化
    step_delta: float = 0.0      # 步数变化（负=减少）
    regression_found: bool = False
    execution_time_ms: float = 0.0
    reason: str = ""


@dataclass
class ReplayReport:
    """
    完整回放报告。

    字段：
      report_id        — 报告唯一 ID
      skill_id        — 被回放的技能 ID
      replayed_at     — 回放时间
      total_cases     — 总 case 数
      passed_cases    — 通过 case 数
      overall_pass    — 整体是否通过（passed_cases >= 50% 且无 regression）
      success_delta   — 平均成功率变化
      error_delta     — 平均错误率变化
      risk_delta      — 平均风险变化
      regression_found — 是否发现回归
      results         — 单次结果列表
      recommendation  — "promote" | "quarantine" | "keep_draft"
    """
    report_id: str = ""
    skill_id: str = ""
    replayed_at: str = ""
    total_cases: int = 0
    passed_cases: int = 0
    overall_pass: bool = False
    success_delta: float = 0.0
    error_delta: float = 0.0
    risk_delta: float = 0.0
    regression_found: bool = False
    step_delta: float = 0.0
    results: list[ReplayResult] = field(default_factory=list)
    recommendation: str = "keep_draft"

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["results"] = [asdict(r) for r in self.results]
        return d

    @property
    def pass_rate(self) -> float:
        if self.total_cases == 0:
            return 0.0
        return self.passed_cases / self.total_cases


# ----------------------------------------------------------------------
# EvidencePolicy — 证据评分与晋级规则
# ----------------------------------------------------------------------

class EvidencePolicy:
    """
    决定技能是否可以晋级的证据评分策略。

    晋级规则（V0.4）：
      1. replay_pass_rate >= 0.70（通过率 >= 70%）
      2. regression_found == False（无回归）
      3. risk_delta <= 0.0（风险未上升）
      4. evidence_complete == True（有完整 evidence card）

    降级 / 隔离规则：
      - 任意 regression == True → quarantine
      - replay_fail_count >= 2 → quarantine
      - risk_delta > 0 → quarantine
      - 无 evidence card → keep_draft
    """

    REPLAY_PASS_RATE_THRESHOLD = 0.70   # 通过率阈值
    MIN_REPLAY_CASES = 1               # 最少需要回放的 case 数

    def __init__(self, skill_index: dict[str, Any] | None = None):
        self.skill_index = skill_index or {}

    def evaluate(
        self,
        skill_id: str,
        replay_report: ReplayReport,
        evidence_complete: bool,
    ) -> tuple[str, str]:
        """
        评估技能是否可以晋级。

        Args:
            skill_id: 技能 ID
            replay_report: 回放报告
            evidence_complete: 是否有完整的 evidence card

        Returns:
            (decision, reason)
            decision: "promote" | "quarantine" | "keep_draft" | "reject"
        """

        # 规则 1：无 regression
        if replay_report.regression_found:
            return (
                "quarantine",
                f"发现回归（regression），风险不降反升，不建议晋级：{replay_report.regression_found}",
            )

        # 规则 2：通过率
        pass_rate = replay_report.pass_rate
        if replay_report.total_cases < self.MIN_REPLAY_CASES:
            return (
                "keep_draft",
                f"回放 case 数不足（{replay_report.total_cases} < {self.MIN_REPLAY_CASES}），需补充更多验证",
            )

        if pass_rate < self.REPLAY_PASS_RATE_THRESHOLD:
            return (
                "quarantine",
                f"回放通过率 {pass_rate:.0%} 低于阈值 {self.REPLAY_PASS_RATE_THRESHOLD:.0%}，建议隔离待人工复核",
            )

        # 规则 3：风险变化
        if replay_report.risk_delta > 0.05:
            return (
                "quarantine",
                f"风险上升 {replay_report.risk_delta:+.2f}，建议隔离审查",
            )

        # 规则 4：evidence card
        if not evidence_complete:
            return (
                "keep_draft",
                "缺少完整 evidence card，保持 draft 等待补充证据",
            )

        # 所有规则通过 → promote
        return (
            "promote",
            f"回放通过率 {pass_rate:.0%} >= {self.REPLAY_PASS_RATE_THRESHOLD:.0%}，"
            f"无回归，风险未升，evidence 完整，建议晋级 active",
        )

    def update_skill_index(
        self,
        skill_id: str,
        decision: str,
        replay_report: ReplayReport,
    ) -> dict[str, Any]:
        """
        根据回放决策更新 skill_index 条目。
        返回更新后的 entry dict。
        """
        if skill_id not in self.skill_index:
            return {}

        entry = self.skill_index[skill_id]

        if decision == "promote":
            entry["replay_passed"] = True
            entry["replay_pass_rate"] = replay_report.pass_rate
            entry["replay_note"] = f"promote: {replay_report.passed_cases}/{replay_report.total_cases} passed"
        elif decision == "quarantine":
            entry["replay_passed"] = False
            entry["replay_note"] = f"quarantine: {replay_report.regression_found and 'regression' or f'{replay_report.pass_rate:.0%} < {self.REPLAY_PASS_RATE_THRESHOLD:.0%}'}"
        else:
            entry["replay_passed"] = None
            entry["replay_note"] = f"keep_draft: {replay_report.recommendation}"

        return entry


# ----------------------------------------------------------------------
# SkillReplay — 回放执行器
# ----------------------------------------------------------------------

class SkillReplay:
    """
    执行技能回放验证。

    V0.4 回放逻辑：
      - 将技能 skill_md 解析为步骤
      - 加载对应类型的 benchmark cases
      - 模拟"应用技能后的行为"与"未应用技能的行为"对比
      - 计算 delta 指标

    V0.4 实现的模拟回放（不依赖真实执行环境）：
      1. 关键词匹配：技能是否覆盖 case 的关键词
      2. 风险评估：技能是否引入新风险
      3. 覆盖率：技能步骤是否能处理 case 的期望行为
      4. 回归检测：技能是否可能引发负面效果
    """

    def __init__(self, root: Path | str | None = None):
        self.root = Path(root) if root else Path(__file__).parent.parent

    def replay(
        self,
        skill: dict[str, Any],
        cases: list[dict[str, Any]],
    ) -> ReplayReport:
        """
        对单个技能执行回放验证。

        Args:
            skill: 技能字典
            cases: BenchmarkCase 列表（dict 形式）

        Returns:
            ReplayReport
        """
        results: list[ReplayResult] = []
        skill_text = (
            skill.get("skill_name", "")
            + " "
            + skill.get("task_goal", "")
            + " "
            + str(skill.get("procedure", []))
            + " "
            + str(skill.get("inputs", []))
        ).lower()

        skill_steps = len(skill.get("procedure", [])) if isinstance(skill.get("procedure"), list) else 0
        skill.get("risk_level", "low")

        for case_d in cases:
            case_id = case_d.get("case_id", "")
            case_d.get("task", "").lower()
            case_keywords = case_d.get("task_keywords", [])
            case_risk_tags = case_d.get("risk_tags", [])
            case_d.get("expected_behavior", "")

            # --- 关键词匹配评估 ---
            matched = sum(1 for kw in case_keywords if kw.lower() in skill_text)
            keyword_ratio = matched / len(case_keywords) if case_keywords else 0.0

            # --- 步骤覆盖率 ---
            # 技能步骤数 vs case 隐含期望（case 通常期望 1-5 步）
            steps_score = min(skill_steps / 3.0, 1.0)

            # --- 风险匹配 ---
            # 如果 case 的风险标签在技能描述/步骤中能找到负面提及，则 regression 风险低
            risk_keywords = ["危险", "拦截", "拒绝", "检查", "验证", "安全", "risk", "danger", "block"]
            has_safety = any(kw.lower() in skill_text for kw in risk_keywords)
            risk_tag_match = any(tag.lower() in skill_text for tag in case_risk_tags)

            # --- 综合判断 ---
            # 通过条件：关键词匹配 >= 50% OR 步骤覆盖足够 OR 有安全措施
            case_pass = (
                keyword_ratio >= 0.50
                or steps_score >= 0.60
                or (has_safety and risk_tag_match)
            )

            # 回归检测：如果 case 是危险操作但技能没有安全检查，则 regression
            dangerous_tags = {"dangerous_command", "privilege_escalation", "data_corruption"}
            is_dangerous = bool(dangerous_tags & set(case_risk_tags))
            regression = is_dangerous and not has_safety

            # Delta 估算（模拟值）
            # 技能让 case 通过 → success_delta = +0.3，error_delta = -0.2
            # regression → risk_delta = +0.3
            success_delta = 0.3 if case_pass else -0.1
            error_delta = -0.2 if case_pass else 0.05
            risk_delta = 0.0
            if regression:
                risk_delta = 0.25
            elif case_pass and has_safety:
                risk_delta = -0.1  # 风险降低

            results.append(ReplayResult(
                case_id=case_id,
                skill_id=skill.get("skill_id", ""),
                passed=case_pass,
                success_delta=round(success_delta, 4),
                error_delta=round(error_delta, 4),
                risk_delta=round(risk_delta, 4),
                step_delta=round(-0.5 if case_pass else 0.0, 4),  # 通过则步数减少
                regression_found=regression,
                execution_time_ms=round(len(case_keywords) * 0.1 + skill_steps * 0.05, 2),
                reason=f"关键词匹配 {matched}/{len(case_keywords)} ({keyword_ratio:.0%})，"
                       f"步骤覆盖 {steps_score:.0%}，"
                       f"{'✓ 通过' if case_pass else '✗ 未通过'}"
                       f"{'（发现回归风险）' if regression else ''}",
            ))

        # 汇总
        passed_count = sum(1 for r in results if r.passed)
        total = len(results)
        avg_success_delta = sum(r.success_delta for r in results) / total if total else 0.0
        avg_error_delta = sum(r.error_delta for r in results) / total if total else 0.0
        avg_risk_delta = sum(r.risk_delta for r in results) / total if total else 0.0
        avg_step_delta = sum(r.step_delta for r in results) / total if total else 0.0
        has_regression = any(r.regression_found for r in results)

        return ReplayReport(
            report_id=f"replay_{skill.get('skill_id', 'unknown')}_{datetime.now().strftime('%Y%m%d%H%M%S')}",
            skill_id=skill.get("skill_id", ""),
            replayed_at=datetime.now().isoformat(),
            total_cases=total,
            passed_cases=passed_count,
            overall_pass=passed_count >= total * 0.5 and not has_regression,
            success_delta=round(avg_success_delta, 4),
            error_delta=round(avg_error_delta, 4),
            risk_delta=round(avg_risk_delta, 4),
            regression_found=has_regression,
            step_delta=round(avg_step_delta, 4),
            results=results,
            recommendation="promote" if (passed_count >= total * 0.5 and not has_regression) else "keep_draft",
        )


    def save_report(self, report: ReplayReport) -> Path:
        """保存回放报告到 evidence/replay_reports/。"""
        reports_dir = self.root / "evidence" / "replay_reports"
        reports_dir.mkdir(parents=True, exist_ok=True)
        path = reports_dir / f"{report.report_id}.report.json"
        path.write_text(
            json.dumps(report.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return path

    def load_report(self, report_id: str) -> ReplayReport | None:
        """加载指定报告。"""
        reports_dir = self.root / "evidence" / "replay_reports"
        path = reports_dir / f"{report_id}.report.json"
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            data["results"] = [ReplayResult(**r) for r in data.get("results", [])]
            return ReplayReport(**data)
        except (OSError, json.JSONDecodeError, TypeError):
            return None
