"""
fallback_manager: 技能调用失败后的回退管理
V0.5 — Phoenix-Evo Runtime Skill Router

职责：
  - 接收技能调用失败信号（异常 / 超时 / 退出码非零 / 用户拒绝）
  - 根据失败类型决定回退策略
  - 更新 skill_registry 中的技能使用统计
  - 必要时将技能降级或送回 Curator / Replay 重新评估
  - 记录回退日志供后续分析
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

# ----------------------------------------------------------------------
# FallbackResult
# ----------------------------------------------------------------------

@dataclass
class FallbackAction:
    """
    单次回退决策。

    字段：
      action         — 回退动作
      reason         — 回退原因
      skill_id       — 涉及技能 ID
      degraded_to     — 如果降级，目标状态是什么
      escalate       — 是否上报人工处理
      retry_allowed  — 是否允许重试
      retry_after_sec — 如果允许重试，间隔秒数
    """
    action: str = ""          # "retry" | "use_older" | "use_manual" | "skip" | "degrade" | "escalate"
    reason: str = ""
    skill_id: str = ""
    degraded_to: str = ""     # "quarantine" | "archived"
    escalate: bool = False
    retry_allowed: bool = False
    retry_after_sec: int = 0


# ----------------------------------------------------------------------
# FallbackManager
# ----------------------------------------------------------------------

class FallbackManager:
    """
    技能调用回退管理器。

    V0.5 回退策略：

    失败类型 → 回退动作：

    1. TIMEOUT（调用超时）
       - retry_allowed = True
       - retry_after_sec = 30s
       - 超过 2 次超时 → 降级为 quarantine

    2. ERROR（执行异常）
       - retry_allowed = False（异常不应盲目重试）
       - 记录失败原因
       - 超过 2 次 → 降级为 quarantine

    3. USER_REJECTED（用户拒绝使用）
       - retry_allowed = False
       - 记录用户拒绝原因
       - 超过 3 次 → 降级为 quarantine

    4. CONTEXT_MISMATCH（上下文不匹配）
       - retry_allowed = False
       - 建议用手动方式处理
       - 不影响技能状态

    5. SUCCESS（成功）
       - 更新 usage_count + success_count
       - skill_score 微调上升

    回退链路（从高优先级到低）：
      primary_skill FAILED
        → retry（最多 1 次）
          → fallback_skill（次优候选）
            → manual_handling（人工处理）

    降级规则：
      连续失败 >= 2 次（同类）→ quarantine
      累计失败 >= 3 次（不同类）→ quarantine
      高风险技能失败 1 次 → quarantine
    """

    # 降级阈值
    CONSECUTIVE_FAIL_THRESHOLD = 2
    TOTAL_FAIL_THRESHOLD = 3

    def __init__(self, root: Path | str | None = None):
        self.root = Path(root) if root else Path(__file__).parent.parent
        self.fallback_dir = self.root / "runtime" / "fallback_logs"
        self.fallback_dir.mkdir(parents=True, exist_ok=True)
        self.failure_history: dict[str, list[dict]] = {}  # skill_id → failure list

    # ------------------------------------------------------------------
    # Main API
    # ------------------------------------------------------------------

    def handle_failure(
        self,
        skill_id: str,
        failure_type: str,      # "timeout" | "error" | "user_rejected" | "context_mismatch"
        failure_detail: str = "",
        skill_registry_path: Path | str | None = None,
    ) -> FallbackAction:
        """
        处理技能调用失败，返回回退决策。

        Args:
            skill_id: 失败的技能 ID
            failure_type: 失败类型
            failure_detail: 失败详情
            skill_registry_path: 可选，显式传入 skill_index 路径

        Returns:
            FallbackAction
        """
        self._record_failure(skill_id, failure_type, failure_detail)

        # 读取失败历史
        history = self.failure_history.get(skill_id, [])
        consecutive = self._count_consecutive_failures(history, failure_type)
        total = len(history)

        # 读取技能状态
        skill_status = self._get_skill_status(skill_id, skill_registry_path)
        skill_risk = skill_status.get("risk_level", "low")

        # ── 决策 ──
        # 高风险技能失败 1 次 → 立即 quarantine
        if skill_risk == "high" or skill_risk == "critical":
            self._degrade_skill(skill_id, "quarantine", skill_registry_path)
            return FallbackAction(
                action="degrade",
                reason=f"高风险技能（{skill_risk}）失败，立即降级",
                skill_id=skill_id,
                degraded_to="quarantine",
                escalate=False,
                retry_allowed=False,
            )

        # 连续失败 >= 2 → quarantine
        if consecutive >= self.CONSECUTIVE_FAIL_THRESHOLD:
            self._degrade_skill(skill_id, "quarantine", skill_registry_path)
            return FallbackAction(
                action="degrade",
                reason=f"连续失败 {consecutive} 次 >= {self.CONSECUTIVE_FAIL_THRESHOLD}，降级 quarantine",
                skill_id=skill_id,
                degraded_to="quarantine",
                escalate=True,
                retry_allowed=False,
            )

        # 累计失败 >= 3 → quarantine
        if total >= self.TOTAL_FAIL_THRESHOLD:
            self._degrade_skill(skill_id, "quarantine", skill_registry_path)
            return FallbackAction(
                action="degrade",
                reason=f"累计失败 {total} >= {self.TOTAL_FAIL_THRESHOLD}，降级 quarantine",
                skill_id=skill_id,
                degraded_to="quarantine",
                escalate=True,
                retry_allowed=False,
            )

        # 根据失败类型决定回退
        if failure_type == "timeout":
            return FallbackAction(
                action="retry",
                reason="调用超时，允许重试",
                skill_id=skill_id,
                retry_allowed=True,
                retry_after_sec=30,
            )

        if failure_type == "error":
            return FallbackAction(
                action="retry",
                reason="执行异常，允许重试 1 次",
                skill_id=skill_id,
                retry_allowed=True,
                retry_after_sec=10,
            )

        if failure_type == "user_rejected":
            return FallbackAction(
                action="use_older",
                reason="用户拒绝，建议使用次优候选或手动处理",
                skill_id=skill_id,
                retry_allowed=False,
            )

        # context_mismatch
        return FallbackAction(
            action="use_manual",
            reason="上下文不匹配，建议手动处理",
            skill_id=skill_id,
            retry_allowed=False,
        )

    def handle_success(
        self,
        skill_id: str,
        skill_registry_path: Path | str | None = None,
    ) -> None:
        """
        技能调用成功：更新使用统计，重置信次数清零。
        """
        self._record_success(skill_id)
        self._update_skill_on_success(skill_id, skill_registry_path)

    def get_fallback_chain(
        self,
        skill_id: str,
        all_skills: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """
        给定主技能，获取回退链路（按优先级排序的候选列表）。

        Returns:
            按优先级排序的技能列表（排除主技能、archived、quarantine）
        """
        # 从 all_skills 中排除当前技能和不可用状态
        candidates = [
            s for s in all_skills
            if s.get("skill_id") != skill_id
            and s.get("status") not in ("archived", "quarantine")
        ]

        def sort_key(s: dict[str, Any]) -> tuple:
            status_order = {"active": 0, "draft": 1}
            status = s.get("status", "unknown")
            score = s.get("evidence_score", 0.0)
            usage = s.get("usage_count", 0)
            return (
                status_order.get(status, 99),
                -score,
                -usage,
            )

        candidates.sort(key=sort_key)
        return candidates[:3]  # 最多 3 个回退候选

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _record_failure(
        self,
        skill_id: str,
        failure_type: str,
        failure_detail: str,
    ) -> None:
        """记录失败到内存和磁盘。"""
        if skill_id not in self.failure_history:
            self.failure_history[skill_id] = []

        entry = {
            "type": failure_type,
            "detail": failure_detail,
            "at": datetime.now().isoformat(),
            "result": "fail",
        }
        self.failure_history[skill_id].append(entry)

        # 持久化
        log_path = self.fallback_dir / f"{skill_id}.jsonl"
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def _record_success(self, skill_id: str) -> None:
        """记录成功，清空同类连续失败计数。"""
        if skill_id in self.failure_history:
            self.failure_history[skill_id].append({
                "type": "success",
                "at": datetime.now().isoformat(),
                "result": "success",
            })

    def _count_consecutive_failures(
        self,
        history: list[dict],
        failure_type: str,
    ) -> int:
        """统计最近同类连续失败次数。"""
        count = 0
        for entry in reversed(history):
            if entry.get("result") == "fail" and entry.get("type") == failure_type:
                count += 1
            elif entry.get("result") == "success":
                break
            else:
                count = 0  # 不同类失败，不计入连续
        return count

    def _get_skill_status(
        self,
        skill_id: str,
        skill_registry_path: Path | str | None = None,
    ) -> dict[str, Any]:
        """读取技能当前状态。"""
        path = Path(skill_registry_path) if skill_registry_path else self.root / "skills" / "skill_index.json"
        if not path.exists():
            return {}
        try:
            index = json.loads(path.read_text(encoding="utf-8"))
            return index.get(skill_id, {})
        except (OSError, json.JSONDecodeError):
            return {}

    def _degrade_skill(
        self,
        skill_id: str,
        to_status: str,          # "quarantine" | "archived"
        skill_registry_path: Path | str | None = None,
    ) -> None:
        """将技能降级。"""
        path = Path(skill_registry_path) if skill_registry_path else self.root / "skills" / "skill_index.json"
        if not path.exists():
            return
        try:
            index = json.loads(path.read_text(encoding="utf-8"))
            if skill_id in index:
                index[skill_id]["status"] = to_status
                index[skill_id]["degraded_at"] = datetime.now().isoformat()
                index[skill_id]["degrade_reason"] = "fallback_manager: consecutive/total failure threshold"
                path.write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")
        except (OSError, json.JSONDecodeError):
            pass

    def _update_skill_on_success(
        self,
        skill_id: str,
        skill_registry_path: Path | str | None = None,
    ) -> None:
        """技能成功后更新统计。"""
        path = Path(skill_registry_path) if skill_registry_path else self.root / "skills" / "skill_index.json"
        if not path.exists():
            return
        try:
            index = json.loads(path.read_text(encoding="utf-8"))
            if skill_id in index:
                entry = index[skill_id]
                entry["usage_count"] = entry.get("usage_count", 0) + 1
                entry["success_count"] = entry.get("success_count", 0) + 1
                total = entry["usage_count"]
                entry["success_rate"] = round(entry["success_count"] / total, 4)
                entry["last_used"] = datetime.now().isoformat()
                path.write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")
        except (OSError, json.JSONDecodeError):
            pass

    def get_failure_stats(self, skill_id: str) -> dict[str, Any]:
        """获取技能失败统计。"""
        history = self.failure_history.get(skill_id, [])
        total = len(history)
        successes = sum(1 for e in history if e.get("result") == "success")
        failures = total - successes
        return {
            "skill_id": skill_id,
            "total_invocations": total,
            "successes": successes,
            "failures": failures,
            "success_rate": round(successes / total, 4) if total > 0 else 0.0,
            "recent_failures": [
                {"type": e.get("type"), "at": e.get("at")}
                for e in history[-5:]
            ],
        }
