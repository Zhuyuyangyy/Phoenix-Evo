"""
benchmark_runner: Phoenix-Bench 运行器
V1.1 — Phoenix-Evo Benchmark

职责：
  - 定义 A-E 五个 ablation group 的模块配置
  - 对每个 group 运行所有 benchmark cases
  - 收集每个 case 的运行结果
  - 输出 GroupRunResult（含 MetricResult）
"""

from __future__ import annotations

import json
import tempfile
import shutil
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Any

from .phoenix_evo import PhoenixEvo
from .skill_benchmark import SkillBenchmark
from .benchmark_metrics import BenchmarkMetrics, MetricResult


# ----------------------------------------------------------------------
# GroupConfig — 单个 ablation group 的配置
# ----------------------------------------------------------------------

@dataclass
class GroupConfig:
    """一个 ablation group 的配置。"""
    name: str                              # A / B / C / D / E
    label: str                             # human-readable label
    modules: dict[str, bool]               # module name → enabled
    description: str = ""


# ----------------------------------------------------------------------
# 五个预定义 group
# ----------------------------------------------------------------------

GROUP_A = GroupConfig(
    name="A",
    label="baseline",
    modules={"evaluator": True, "miner": True, "verifier": False, "immune_guard": False},
    description="Hermes only — no Phoenix verification or immune guard",
)

GROUP_B = GroupConfig(
    name="B",
    label="+SkillRetrieval",
    modules={"evaluator": True, "miner": True, "verifier": True, "immune_guard": False},
    description="+ Skill Verification — skills verified but no immune guard",
)

GROUP_C = GroupConfig(
    name="C",
    label="+ImmuneGuard",
    modules={"evaluator": True, "miner": True, "verifier": True, "immune_guard": True},
    description="+ Immune Guard — full pipeline with risk blocking",
)

GROUP_D = GroupConfig(
    name="D",
    label="+ReplayEvidence",
    modules={"evaluator": True, "miner": True, "verifier": True, "immune_guard": True},
    description="+ Replay Evidence — full pipeline, replay validates before promote",
)

GROUP_E = GroupConfig(
    name="E",
    label="+ProjectRouter",
    modules={"evaluator": True, "miner": True, "verifier": True, "immune_guard": True},
    description="+ Project Router — full pipeline with cross-project routing",
)

ALL_GROUPS = [GROUP_A, GROUP_B, GROUP_C, GROUP_D, GROUP_E]


# ----------------------------------------------------------------------
# CaseRunResult — 单个 case 的运行结果
# ----------------------------------------------------------------------

@dataclass
class CaseRunResult:
    """单个 case 在某个 group 下的运行结果。"""
    case_id: str = ""
    task_success: bool = False
    skill_extracted: bool = False
    skill_duplicate: bool = False
    risk_blocked: bool = False
    regression: bool = False
    repair_steps: int = 0
    has_evidence: bool = False
    immune_decision: str = ""
    verification_passed: bool | None = None
    error: str = ""


# ----------------------------------------------------------------------
# GroupRunResult — 单个 group 的完整结果
# ----------------------------------------------------------------------

@dataclass
class GroupRunResult:
    """一个 group 的完整运行结果。"""
    group_name: str = ""
    group_label: str = ""
    total_cases: int = 0
    run_results: list[CaseRunResult] = field(default_factory=list)
    metrics: MetricResult | None = None
    started_at: str = ""
    completed_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        if self.metrics:
            d["metrics"] = self.metrics.to_dict()
        return d


# ----------------------------------------------------------------------
# BenchmarkRunner
# ----------------------------------------------------------------------

class BenchmarkRunner:
    """
    Phoenix-Bench 运行器。

    用法：
        runner = BenchmarkRunner(base_dir="/tmp/phoenix_bench")
        results = runner.run_all_groups()
        runner.save_results(results)
    """

    def __init__(self, base_dir: Path | str | None = None):
        if base_dir is None:
            base_dir = Path(tempfile.mkdtemp(prefix="phoenix_bench_"))
        elif isinstance(base_dir, str):
            base_dir = Path(base_dir)
        self.base_dir = base_dir
        self.benchmark = SkillBenchmark(root=base_dir)
        self.metrics_computer = BenchmarkMetrics()

    def run_group(
        self,
        group: GroupConfig,
        case_ids: list[str] | None = None,
    ) -> GroupRunResult:
        """
        运行单个 ablation group。

        Args:
            group: GroupConfig
            case_ids: 可选，只运行指定 case。None = 运行全部。

        Returns:
            GroupRunResult
        """
        started = datetime.now().isoformat()

        # 获取 cases
        if case_ids:
            cases = [self.benchmark.get_case(cid) for cid in case_ids]
            cases = [c for c in cases if c is not None]
        else:
            cases = self.benchmark.list_cases()

        run_results: list[CaseRunResult] = []

        for case in cases:
            run_result = self._run_single_case(case, group)
            run_results.append(run_result)

        # 计算指标
        metrics_input = [asdict(r) for r in run_results]
        metrics = self.metrics_computer.compute(metrics_input)

        completed = datetime.now().isoformat()

        return GroupRunResult(
            group_name=group.name,
            group_label=group.label,
            total_cases=len(run_results),
            run_results=run_results,
            metrics=metrics,
            started_at=started,
            completed_at=completed,
        )

    def run_all_groups(
        self,
        groups: list[GroupConfig] | None = None,
        case_ids: list[str] | None = None,
    ) -> list[GroupRunResult]:
        """运行所有 group。"""
        groups = groups or ALL_GROUPS
        results = []
        for group in groups:
            result = self.run_group(group, case_ids=case_ids)
            results.append(result)
        return results

    def save_results(
        self,
        results: list[GroupRunResult],
        output_dir: Path | str | None = None,
    ) -> Path:
        """将结果保存为 JSON。"""
        out = Path(output_dir) if output_dir else self.base_dir / "bench_results"
        out.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = out / f"bench_run_{timestamp}.json"

        data = {
            "run_id": f"bench_{timestamp}",
            "total_groups": len(results),
            "groups": [r.to_dict() for r in results],
        }

        output_file.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return output_file

    def _run_single_case(self, case, group: GroupConfig) -> CaseRunResult:
        """运行单个 case，返回结果。"""
        result = CaseRunResult(case_id=case.case_id)

        try:
            # 创建隔离的 PhoenixEvo 实例
            case_dir = self.base_dir / f"run_{group.name}_{case.case_id}"
            case_dir.mkdir(parents=True, exist_ok=True)

            evo = PhoenixEvo.create_configured(base_dir=case_dir, modules=group.modules)

            # 模拟任务执行
            evo.run_full_loop(
                task_goal=case.task,
                task_type=self._infer_task_type(case),
                risk_level=self._infer_risk_level(case),
            )

            # 模拟 actions
            self._simulate_actions(evo, case)

            # 完成任务
            is_dangerous = any(
                tag in case.risk_tags
                for tag in ["dangerous_command", "privilege_escalation", "data_corruption", "destructive"]
            )
            task_success = not is_dangerous

            report = evo.complete_task(
                success=task_success,
                final_output=f"Simulated completion for {case.case_id}",
                artifacts=[f"/tmp/{case.case_id}.out"] if task_success else [],
            )

            # 提取结果
            result.task_success = task_success
            result.skill_extracted = report.get("evolution_happened", False)

            if report.get("verification"):
                result.verification_passed = report["verification"].get("passed")

            if report.get("immune_guard"):
                result.immune_decision = report["immune_guard"].get("decision", "")
                result.risk_blocked = report["immune_guard"].get("decision") == "reject"

            # 检查重复
            if result.skill_extracted:
                registry = evo.registry
                skill_id = report.get("skill_candidate", {}).get("skill_id", "")
                similar = registry.find_similar(skill_id)
                result.skill_duplicate = len(similar) > 1

            # 检查证据
            if result.skill_extracted:
                from .skill_evidence import SkillEvidenceManager
                evidence_mgr = SkillEvidenceManager(root=case_dir)
                card = evidence_mgr.get_card(
                    report.get("skill_candidate", {}).get("skill_id", "")
                )
                result.has_evidence = card is not None

            # 估算修复步数
            result.repair_steps = len(report.get("trajectory", {}).get("fixes", []))

            # 清理
            shutil.rmtree(case_dir, ignore_errors=True)

        except Exception as e:
            result.error = str(e)

        return result

    def _simulate_actions(self, evo: PhoenixEvo, case) -> None:
        """根据 case 的 expected_behavior 模拟 actions。"""
        behavior = case.expected_behavior.lower()

        if "验证" in behavior or "verify" in behavior or "check" in behavior:
            evo.logger.log_action("verify", {"target": case.case_id}, "verified")
        if "写入" in behavior or "write" in behavior:
            evo.logger.log_action("write_file", {"path": f"/tmp/{case.case_id}.out"}, "written")
        if "读取" in behavior or "read" in behavior:
            evo.logger.log_action("read_file", {"path": f"/tmp/{case.case_id}.in"}, "read")
        if "拦截" in behavior or "block" in behavior or "拒绝" in behavior:
            evo.logger.log_action("security_check", {"target": case.case_id}, "blocked")
        if "合并" in behavior or "merge" in behavior:
            evo.logger.log_action("merge_skills", {"target": case.case_id}, "merged")
        if "回放" in behavior or "replay" in behavior:
            evo.logger.log_action("replay", {"target": case.case_id}, "replayed")
        if "索引" in behavior or "index" in behavior:
            evo.logger.log_action("index", {"target": case.case_id}, "indexed")

        # Default: at least one action
        if not evo.logger._actions:
            evo.logger.log_action("execute", {"target": case.case_id}, "done")

    def _infer_task_type(self, case) -> str:
        """从 case 的 risk_tags 推断 task_type。"""
        tags = case.risk_tags
        if any(t in tags for t in ["dangerous_command", "privilege_escalation", "security"]):
            return "coding"
        if any(t in tags for t in ["data_corruption", "data_loss"]):
            return "debugging"
        if any(t in tags for t in ["performance", "resource_exhaustion"]):
            return "debugging"
        if any(t in tags for t in ["skill_reuse", "skill_redundancy", "skill_drift"]):
            return "general"
        return "general"

    def _infer_risk_level(self, case) -> str:
        """从 case 的 risk_tags 推断 risk_level。"""
        high_risk = {"dangerous_command", "privilege_escalation", "data_corruption", "destructive", "security"}
        if set(case.risk_tags) & high_risk:
            return "high"
        medium_risk = {"concurrency", "performance", "regression"}
        if set(case.risk_tags) & medium_risk:
            return "medium"
        return "low"
