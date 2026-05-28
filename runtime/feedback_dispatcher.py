"""
feedback_dispatcher.py — V0.7 Feedback 路由分发器
=================================================

把 Runtime 执行结果路由到正确的 Phoenix 反馈处理器：

  outcome = "success"  → 更新 SkillRegistry success_rate
                      → 可选：通知 Evidence 提升 confidence
                      → 可选：通知 Curator 更新相似 skill

  outcome = "failure"  → 更新 SkillRegistry failure_count
                      → 连续失败 → OutcomeTracker 标记 needs_replay
                      → 高风险 → QuarantineManager 隔离
                      → 触发 Curator drift 检测

  outcome = "skipped"  → 路由失败，通知 FallbackManager 记录无匹配

用法：
    dispatcher = FeedbackDispatcher(
        phoenix_base_dir=Path("/path/to/Phoenix-Evo"),
        reporter_base_dir=Path("/path/to/Phoenix-Evo"),
    )
    result = dispatcher.dispatch(
        skill_id="fix_wsl_chinese_path",
        execution_result="success",
        task_id="t123",
        session_id="s456",
        metadata={"duration": 1.5, "risk_flag": False},
    )
"""
from __future__ import annotations

import json
import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger("feedback_dispatcher")


# ── 阈值常量 ──────────────────────────────────────────────────────────────────

class Threshold:
    CONSECUTIVE_FAILURES_FOR_REPLAY = 2
    CONSECUTIVE_FAILURES_FOR_REVIEW = 3
    RISK_INCIDENTS_FOR_QUARANTINE = 2


# ── 数据结构 ──────────────────────────────────────────────────────────────────

class OutcomeStatus(str, Enum):
    PENDING = "pending"
    PROCESSED = "processed"
    FLAGGED = "flagged"
    QUARANTINED = "quarantined"


class SkillHealthStatus(str, Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    FAILING = "failing"
    QUARANTINED = "quarantined"


# ── 主类 ──────────────────────────────────────────────────────────────────────

class FeedbackDispatcher:
    """
    同步/异步分发 Runtime 执行结果到 Phoenix 各子系统。
    sync 模式：立即更新 SkillRegistry → 触发健康检查 → quarantine
    async 模式：写入队列，由 OutcomeTracker.process_pending() 批量消费
    """

    def __init__(
        self,
        phoenix_base_dir: Path | str | None = None,
        reporter_base_dir: Path | str | None = None,
        mode: str = "sync",
    ) -> None:
        self.base_dir = Path(phoenix_base_dir or Path(__file__).parent.parent)
        self.reporter_base_dir = Path(reporter_base_dir or self.base_dir)
        self.mode = mode
        self._queue: list[dict[str, Any]] = []
        self._lock = threading.Lock()

        # 延迟导入避免循环依赖
        self._outcome_tracker: Optional[Any] = None

    # ── Phoenix 懒加载 ──────────────────────────────────────────────────────

    @property
    def outcome_tracker(self) -> Any:
        if self._outcome_tracker is None:
            from runtime.outcome_tracker import OutcomeTracker
            self._outcome_tracker = OutcomeTracker(
                phoenix_base_dir=self.base_dir,
                reporter_base_dir=self.reporter_base_dir,
            )
        return self._outcome_tracker

    # ── 公开 API ─────────────────────────────────────────────────────────────

    def dispatch(self, skill_id: str, execution_result: str, **kwargs: Any) -> dict[str, Any]:
        """
        主分发入口。根据 execution_result 路由到对应处理方法。
        """
        if execution_result == "success":
            return self.on_success(skill_id=skill_id, **kwargs)
        elif execution_result == "failure":
            return self.on_failure(skill_id=skill_id, **kwargs)
        elif execution_result == "skipped":
            return self.on_skipped(skill_id=skill_id, **kwargs)
        else:
            return {"error": f"unknown execution_result: {execution_result}"}

    def report_success(
        self,
        skill_id: str,
        task_id: str,
        session_id: str,
        duration: float = 0.0,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """report_success — skill 执行成功"""
        return self.on_success(skill_id=skill_id, task_id=task_id, session_id=session_id, duration=duration, **kwargs)

    def report_failure(
        self,
        skill_id: str,
        failure_reason: str,
        risk_flag: bool = False,
        task_id: str = "",
        session_id: str = "",
        duration: float = 0.0,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """report_failure — skill 执行失败"""
        return self.on_failure(
            skill_id=skill_id,
            failure_reason=failure_reason,
            risk_flag=risk_flag,
            task_id=task_id,
            session_id=session_id,
            duration=duration,
            **kwargs,
        )

    def report_skipped(
        self,
        skill_id: str = "",
        reason: str = "",
        task_id: str = "",
        session_id: str = "",
        **kwargs: Any,
    ) -> dict[str, Any]:
        """report_skipped — 没有可用 skill"""
        return self.on_skipped(skill_id=skill_id, reason=reason, task_id=task_id, session_id=session_id, **kwargs)

    # ── 内部处理器 ───────────────────────────────────────────────────────────

    def on_success(
        self,
        skill_id: str,
        task_id: str = "",
        session_id: str = "",
        duration: float = 0.0,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """
        success 处理路径：
          1. 记录到 reporter 日志
          2. 更新 Phoenix SkillRegistry.success_count
          3. 清除 consecutive_failures
        """
        self._record_to_reporter(skill_id=skill_id, execution_result="success",
                                  task_id=task_id, session_id=session_id, duration=duration, **kwargs)

        if self.mode == "sync":
            return self.outcome_tracker._record_outcome(
                skill_id=skill_id, success=True, task_id=task_id, session_id=session_id,
            )
        else:
            self._enqueue({"skill_id": skill_id, "success": True, "task_id": task_id,
                            "session_id": session_id, "outcome": "success"})
            return {"status": "queued", "skill_id": skill_id}

    def on_failure(
        self,
        skill_id: str,
        failure_reason: str,
        risk_flag: bool = False,
        task_id: str = "",
        session_id: str = "",
        duration: float = 0.0,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """
        failure 处理路径：
          1. 记录到 reporter 日志
          2. 更新 Phoenix SkillRegistry.failure_count
          3. 触发 OutcomeTracker 健康检查
          4. 达到阈值 → quarantine
        """
        self._record_to_reporter(
            skill_id=skill_id, execution_result="failure",
            task_id=task_id, session_id=session_id, duration=duration,
            failure_reason=failure_reason, risk_flag=risk_flag, **kwargs,
        )

        if self.mode == "sync":
            result = self.outcome_tracker._record_outcome(
                skill_id=skill_id, success=False,
                failure_reason=failure_reason, risk_flag=risk_flag,
                task_id=task_id, session_id=session_id,
            )
            health = self.outcome_tracker.check_skill_health(skill_id)
            return {"outcome": result, "health": health.value}
        else:
            self._enqueue({
                "skill_id": skill_id, "success": False,
                "failure_reason": failure_reason, "risk_flag": risk_flag,
                "task_id": task_id, "session_id": session_id, "outcome": "failure",
            })
            return {"status": "queued", "skill_id": skill_id}

    def on_skipped(
        self,
        skill_id: str = "",
        reason: str = "",
        task_id: str = "",
        session_id: str = "",
        **kwargs: Any,
    ) -> dict[str, Any]:
        """skipped 处理路径：通知 FallbackManager 记录无匹配"""
        duration = kwargs.pop("duration", 0.0)
        self._record_to_reporter(
            skill_id=skill_id, execution_result="skipped",
            task_id=task_id, session_id=session_id,
            duration=duration, failure_reason=reason, **kwargs,
        )

        if self.mode == "sync":
            return {"status": "skipped", "skill_id": skill_id, "reason": reason}
        else:
            self._enqueue({"skill_id": skill_id, "outcome": "skipped",
                            "reason": reason, "task_id": task_id, "session_id": session_id})
            return {"status": "queued"}

    def process_pending(self) -> dict[str, Any]:
        """批量消费 async 队列（由 OutcomeTracker 调用）"""
        if self.mode != "async":
            return {"status": "not_async_mode"}

        outcomes = []
        with self._lock:
            queue = self._queue[:]
            self._queue.clear()

        for item in queue:
            result = self.outcome_tracker._record_outcome(
                skill_id=item["skill_id"],
                success=item.get("success", False),
                failure_reason=item.get("failure_reason"),
                risk_flag=item.get("risk_flag", False),
                task_id=item.get("task_id"),
                session_id=item.get("session_id"),
            )
            outcomes.append(result)

        return {"processed": len(outcomes), "outcomes": outcomes}

    # ── 工具 ─────────────────────────────────────────────────────────────────

    def _enqueue(self, item: dict[str, Any]) -> None:
        with self._lock:
            self._queue.append(item)

    def _record_to_reporter(
        self,
        skill_id: str,
        execution_result: str,
        task_id: str,
        session_id: str,
        duration: float,
        **kwargs: Any,
    ) -> None:
        """写入 RuntimeReporter 日志（供 process_pending 消费）"""
        today = datetime.now().strftime("%Y-%m-%d")
        log_dir = self.reporter_base_dir / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        log_path = log_dir / f"runtime_{today}.jsonl"

        record = {
            "call_id": f"{task_id}_{datetime.now().timestamp()}",
            "skill_id": skill_id,
            "selected_skill_id": skill_id,
            "selected_skill_name": skill_id,
            "execution_result": execution_result,
            "task_id": task_id,
            "session_id": session_id,
            "duration": duration,
            "timestamp": datetime.now().isoformat(),
            **kwargs,
        }
        try:
            with log_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
        except Exception as e:
            logger.warning("failed to write reporter log: %s", e)
