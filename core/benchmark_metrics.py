"""
benchmark_metrics: Phoenix-Bench 指标计算
V1.1 — Phoenix-Evo Benchmark

计算 7 个核心指标：
  1. Task Success Rate      — 任务成功率
  2. Skill Reuse Rate       — 技能提取率（成功任务中提取了技能的比例）
  3. Risk Blocking Rate     — 风险拦截率（危险任务被拦截的比例）
  4. Regression Rate        — 回归率（提取的技能中引入回归的比例）
  5. Duplicate Skill Rate   — 重复技能率（提取的技能中重复的比例）
  6. Average Repair Steps   — 平均修复步数
  7. Evidence Coverage      — 证据覆盖率（有证据卡的技能比例）
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any


@dataclass
class MetricResult:
    """完整的指标结果。"""
    task_success_rate: float = 0.0
    skill_reuse_rate: float = 0.0
    risk_blocking_rate: float = 0.0
    regression_rate: float = 0.0
    duplicate_skill_rate: float = 0.0
    avg_repair_steps: float = 0.0
    evidence_coverage: float = 0.0
    total_cases: int = 0
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d.pop("details", None)
        return d


class BenchmarkMetrics:
    """
    从 benchmark 运行结果计算 7 个核心指标。

    每个 run dict 应包含：
      case_id         — case 标识
      task_success    — bool: 任务是否成功
      skill_extracted — bool: 是否提取了技能
      skill_duplicate — bool: 提取的技能是否与已有重复
      risk_blocked    — bool: 是否被风险系统拦截
      regression      — bool: 是否发现回归
      repair_steps    — int: 修复步数（0 = 无需修复）
      has_evidence    — bool: 是否有证据卡
    """

    def compute(self, runs: list[dict[str, Any]]) -> MetricResult:
        if not runs:
            return MetricResult()

        n = len(runs)

        # 1. Task Success Rate
        successes = sum(1 for r in runs if r.get("task_success"))
        task_success_rate = successes / n

        # 2. Skill Reuse Rate (among successful tasks)
        successful_runs = [r for r in runs if r.get("task_success")]
        extracted = sum(1 for r in successful_runs if r.get("skill_extracted"))
        skill_reuse_rate = extracted / len(successful_runs) if successful_runs else 0.0

        # 3. Risk Blocking Rate
        blocked = sum(1 for r in runs if r.get("risk_blocked"))
        risk_blocking_rate = blocked / n

        # 4. Regression Rate (among extracted skills)
        extracted_runs = [r for r in runs if r.get("skill_extracted")]
        regressions = sum(1 for r in extracted_runs if r.get("regression"))
        regression_rate = regressions / len(extracted_runs) if extracted_runs else 0.0

        # 5. Duplicate Skill Rate (among extracted skills)
        duplicates = sum(1 for r in extracted_runs if r.get("skill_duplicate"))
        duplicate_skill_rate = duplicates / len(extracted_runs) if extracted_runs else 0.0

        # 6. Average Repair Steps
        total_steps = sum(r.get("repair_steps", 0) for r in runs)
        avg_repair_steps = total_steps / n

        # 7. Evidence Coverage (among extracted skills)
        with_evidence = sum(1 for r in extracted_runs if r.get("has_evidence"))
        evidence_coverage = with_evidence / len(extracted_runs) if extracted_runs else 0.0

        return MetricResult(
            task_success_rate=round(task_success_rate, 4),
            skill_reuse_rate=round(skill_reuse_rate, 4),
            risk_blocking_rate=round(risk_blocking_rate, 4),
            regression_rate=round(regression_rate, 4),
            duplicate_skill_rate=round(duplicate_skill_rate, 4),
            avg_repair_steps=round(avg_repair_steps, 4),
            evidence_coverage=round(evidence_coverage, 4),
            total_cases=n,
            details={
                "successes": successes,
                "extracted": extracted,
                "blocked": blocked,
                "regressions": regressions,
                "duplicates": duplicates,
                "total_steps": total_steps,
                "with_evidence": with_evidence,
            },
        )
