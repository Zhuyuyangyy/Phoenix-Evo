"""
PhoenixEvo: 主调度器
V0.2 — Immune Guard

V0.2 流程：
  trajectory
    ↓
  evaluator
    ↓
  skill_miner
    ↓
  skill_verifier
    ↓
  immune_guard  ← 新增
    ↓
  draft / quarantine / reject

V0.2 约束：
  - 禁止自动激活任何技能为 active
  - 所有 quarantine 必须经人工复核
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from .immune_guard import ImmuneGuard
from .post_task_evaluator import EvaluationResult, PostTaskEvaluator
from .skill_miner import SkillMiner
from .skill_registry import SkillRegistry
from .skill_verifier import SkillVerifier
from .trajectory_logger import TrajectoryLogger


class PhoenixEvo:
    """
    Phoenix-Evo 主调度器。
    管理完整自进化闭环：轨迹 → 自评 → 提取 → 验证 → 免疫审查 → 入库
    """

    def __init__(self, base_dir: Path | str | None = None):
        if base_dir is None:
            base_dir = Path(__file__).parent.parent
        elif isinstance(base_dir, str):
            base_dir = Path(base_dir)

        self.logger      = TrajectoryLogger(task_goal="", task_type="general")
        self.evaluator   = PostTaskEvaluator()
        self.miner       = SkillMiner()
        self.verifier    = SkillVerifier()
        self.registry    = SkillRegistry(root=base_dir)
        self.immune_guard = ImmuneGuard(root=base_dir)   # V0.2 新增

        # 内部状态
        self._last_trajectory: dict[str, Any] | None = None
        self._last_evaluation: EvaluationResult | None = None
        self._last_immune_decision: Any | None = None
        self._module_config: dict[str, bool] = {
            "evaluator": True, "miner": True, "verifier": True, "immune_guard": True,
        }

    @classmethod
    def create_configured(
        cls,
        base_dir: Path | str | None = None,
        modules: dict[str, bool] | None = None,
    ) -> "PhoenixEvo":
        """
        Create a PhoenixEvo instance with selectable modules.

        Args:
            base_dir: Base directory for skills/data
            modules: Dict of module names to enable/disable.
                     Available: evaluator, miner, verifier, immune_guard
                 Default: all enabled

        Returns:
            Configured PhoenixEvo instance
        """
        instance = cls(base_dir=base_dir)
        if modules:
            instance._module_config.update(modules)
        return instance

    # ── 主入口 ──────────────────────────────────────────────

    def run_full_loop(
        self,
        task_goal: str,
        task_type: str = "general",
        risk_level: str = "low",
        session_id: str | None = None,
    ) -> None:
        """开始一个新任务的完整轨迹记录。"""
        self.logger = TrajectoryLogger(
            task_goal=task_goal,
            task_type=task_type,
            risk_level=risk_level,
            session_id=session_id or self._new_session_id(),
        )

    def complete_task(
        self,
        success: bool,
        final_output: str = "",
        artifacts: list[str] | None = None,
    ) -> dict[str, Any]:
        """
        完成当前任务，触发自进化闭环。
        返回完整报告。
        """
        trajectory = self.logger.complete(
            success=success,
            final_output=final_output,
            artifacts=artifacts or [],
        )
        return self.evolve_from_trajectory(trajectory)

    # ── 核心进化闭环 ────────────────────────────────────────

    def evolve_from_trajectory(self, trajectory: dict[str, Any]) -> dict[str, Any]:
        """
        给定一条轨迹，执行完整的自进化闭环。
        V0.2 在 skill_verifier 之后加入了 immune_guard 审查。
        V1.1 支持 module config 跳过指定模块。
        """
        self._last_trajectory = trajectory
        config = self._module_config

        # Step 1: 自评
        if config["evaluator"]:
            eval_result = self.evaluator.evaluate(trajectory)
        else:
            eval_result = EvaluationResult(
                task_success=trajectory.get("success", False),
                quality_score=0.8,
                reuse_potential=0.7,
                should_extract_skill=trajectory.get("success", False),
                reason="evaluation disabled",
                failure_type=None,
                root_cause=None,
                improvement_suggestion="",
                skill_candidate_name=None,
            )
        self._last_evaluation = eval_result

        report: dict[str, Any] = {
            "trajectory":      trajectory,
            "evaluation": {
                "task_success":    eval_result.task_success,
                "quality_score":   eval_result.quality_score,
                "reuse_potential": eval_result.reuse_potential,
                "should_extract":   eval_result.should_extract_skill,
                "failure_type":     eval_result.failure_type,
                "root_cause":       eval_result.root_cause,
                "reason":           eval_result.reason,
            },
            "skill_candidate": None,
            "verification":    None,
            "immune_guard":    None,
            "registry_entry":  None,
            "evolution_happened": False,
        }

        # Step 2: 判断是否提取技能
        if not eval_result.should_extract_skill:
            return report

        # Step 3: 提取候选技能
        if config["miner"]:
            skill_candidate = self.miner.mine(trajectory, eval_result)
        else:
            skill_candidate = {
                "skill_id": f"skip_{trajectory.get('task_id', 'unknown')}",
                "skill_name": "skipped",
                "skill_md": "",
                "source_trajectory": trajectory.get("task_id", ""),
                "quality_score": 0.0,
            }
        report["skill_candidate"] = skill_candidate

        # Step 4: 验证器审查
        verify_result = None
        if config["verifier"]:
            verify_result = self.verifier.verify(skill_candidate, trajectory)
            report["verification"] = {
                "passed":           verify_result.passed,
                "confidence":       verify_result.confidence,
                "risk_level":       verify_result.risk_level,
                "activation_level": verify_result.activation_level,
                "reason":           verify_result.reason,
                "warnings":         verify_result.warnings,
            }
            if not verify_result.passed:
                self._save_rejection(skill_candidate, verify_result, trajectory)
                return report
        else:
            report["verification"] = None

        # Step 5: immune_guard 审查
        immune_decision = None
        if config["immune_guard"]:
            immune_decision = self.immune_guard.examine(
                skill_candidate=skill_candidate,
                trajectory=trajectory,
                verification_result=report["verification"] or {"passed": True},
            )
            self._last_immune_decision = immune_decision
            report["immune_guard"] = {
                "decision":          immune_decision.decision,
                "risk_level":        immune_decision.risk_profile.risk_level,
                "risk_tags":         immune_decision.risk_profile.tags,
                "immune_rules":      immune_decision.immune_rules_triggered,
                "reason":            immune_decision.reason,
                "warnings":          immune_decision.risk_profile.warnings,
            }
        else:
            report["immune_guard"] = {
                "decision": "draft", "risk_level": "low",
                "immune_rules": [], "reason": "immune_guard disabled",
            }

        # Step 6: 根据免疫决策路由
        skill_md_path = self._write_skill_md(skill_candidate)

        if immune_decision and immune_decision.decision == "reject":
            from .skill_verifier import VerificationResult as VR
            vr = verify_result or VR(passed=False, confidence=0.0, risk_level="rejected",
                                     activation_level="reject", reason="skipped", warnings=[], checked_items={})
            self._save_rejection(skill_candidate, vr, trajectory,
                                 immune_decision=immune_decision)
            report["evolution_happened"] = False

        elif immune_decision and immune_decision.decision == "quarantine":
            self.immune_guard.quarantine_mgr.quarantine_skill(
                skill_md_path=skill_md_path,
                reason=immune_decision.reason,
                quarantine_rules=immune_decision.immune_rules_triggered,
                risk_profile=self._profile_to_dict(immune_decision.risk_profile),
            )
            report["registry_entry"] = {
                "skill_id":   skill_candidate["skill_id"],
                "path":       str(self.immune_guard.quarantine_mgr.quarantine_dir / f"{skill_candidate['skill_id']}.md"),
                "status":     "quarantine",
                "reason":     immune_decision.reason,
                "rules":      immune_decision.immune_rules_triggered,
            }
            report["evolution_happened"] = True

        else:  # "draft"
            from .skill_verifier import VerificationResult as VR
            vr = verify_result or VR(passed=True, confidence=1.0, risk_level="low",
                                     activation_level="draft", reason="skipped", warnings=[], checked_items={})
            path = self.registry.add_draft(skill_candidate, vr)
            report["registry_entry"] = {
                "skill_id": skill_candidate["skill_id"],
                "path":     str(path),
                "status":   "draft",
            }
            report["evolution_happened"] = True

        return report

    # ── 外部轨迹导入 ───────────────────────────────────────

    def import_trajectory(self, trajectory: dict[str, Any]) -> dict[str, Any]:
        """从外部导入一条轨迹，手动触发自进化闭环。"""
        # 补全必要字段
        trajectory.setdefault("started_at", datetime.now().isoformat())
        trajectory.setdefault("completed_at", datetime.now().isoformat())
        trajectory.setdefault("session_id", "imported")
        return self.evolve_from_trajectory(trajectory)

    # ── 查询接口 ────────────────────────────────────────────

    def get_trajectory_history(self, limit: int = 20) -> list[dict[str, Any]]:
        """返回轨迹历史。"""
        return self.registry.get_trajectory_history(limit=limit)

    def get_status(self) -> dict[str, Any]:
        """返回 Phoenix-Evo 系统状态。"""
        status = self.registry.get_status()
        qm = self.immune_guard.quarantine_mgr
        status["quarantine_count"] = len(qm.get_all_entries())
        status["quarantine_pending"] = qm.count_pending()
        return status

    # ── 内部工具 ───────────────────────────────────────────

    def _new_session_id(self) -> str:
        return datetime.now().strftime("%Y%m%d_%H%M%S")

    def _write_skill_md(self, skill_candidate: dict[str, Any]) -> Path:
        """将技能候选写入临时路径（待后续移动到正确目录）。"""
        skill_dir = self.registry.draft_dir
        skill_dir.mkdir(parents=True, exist_ok=True)
        path = skill_dir / f"{skill_candidate['skill_id']}.md"
        path.write_text(skill_candidate["skill_md"], encoding="utf-8")
        return path

    def _save_rejection(
        self,
        skill_candidate: dict[str, Any],
        verify_result,           # VerificationResult
        trajectory: dict[str, Any],
        immune_decision=None,   # ImmuneDecision | None
    ) -> None:
        """记录被拒绝的技能候选到 rejections/。"""
        reject_dir = self.registry.root / "skills" / "rejections"
        reject_dir.mkdir(parents=True, exist_ok=True)

        record = {
            "skill_id":          skill_candidate["skill_id"],
            "skill_name":        skill_candidate.get("skill_name", ""),
            "rejected_at":       datetime.now().isoformat(),
            "trajectory_id":     trajectory.get("task_id", ""),
            "verify_passed":     verify_result.passed,
            "verify_reason":     verify_result.reason,
            "immune_decision":   immune_decision.decision if immune_decision else None,
            "immune_rules":      immune_decision.immune_rules_triggered if immune_decision else [],
            "immune_reason":     immune_decision.reason if immune_decision else None,
        }

        path = reject_dir / f"{skill_candidate['skill_id']}.json"
        path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")

    def _profile_to_dict(self, profile) -> dict[str, Any]:
        """RiskProfile dataclass → dict（供 JSON 序列化）。"""
        return {
            "risk_level":              profile.risk_level,
            "tags":                    profile.tags,
            "dangerous_patterns_found": profile.dangerous_patterns_found,
            "source_failed":           profile.source_failed,
            "has_trajectory_id":       profile.has_trajectory_id,
            "has_artifacts":          profile.has_artifacts,
            "has_verification":       profile.has_verification,
            "procedure_step_count":    profile.procedure_step_count,
            "goal_length":             profile.goal_length,
            "similar_skill_failures":  profile.similar_skill_failures,
            "warnings":               profile.warnings,
        }
