"""
outcome_tracker.py — V0.7 Runtime Feedback Loop 核心
=====================================================

消费 RuntimeReporter 日志，把 skill 使用结果反哺 Phoenix：
  1. 更新 SkillRegistry（usage_count / success_rate）
  2. 触发 Curator 漂移检测
  3. 高风险上升时调用 QuarantineManager

用法：
    tracker = OutcomeTracker(phoenix_base_dir=Path("/path/to/Phoenix-Evo"))
    tracker.process_pending()           # 消费 reporter 日志
    tracker.check_skill_health("xxx")    # 单独检查某个 skill
"""
from __future__ import annotations

import json
import logging
import sys
import threading
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Optional

# Phoenix 核心（延迟导入）
_PHOENIX_LOADED = False
_PHOENIX_ERR: str | None = None
try:
    _phoenix_path = str(Path(__file__).parent.parent)
    if _phoenix_path not in sys.path:
        sys.path.insert(0, _phoenix_path)
    from core import PhoenixEvo
    from core.skill_registry import SkillRegistry
    from core.quarantine_manager import QuarantineManager
    _PHOENIX_LOADED = True
except Exception as e:
    _PHOENIX_ERR = str(e)

logger = logging.getLogger("outcome_tracker")


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


@dataclass
class SkillOutcome:
    skill_id: str
    status: OutcomeStatus = OutcomeStatus.PENDING
    success_count: int = 0
    failure_count: int = 0
    consecutive_failures: int = 0
    last_outcome: str = "unknown"
    last_failure_reason: Optional[str] = None
    risk_flags: int = 0
    last_used: Optional[str] = None
    needs_replay: bool = False
    needs_review: bool = False
    flagged_at: Optional[str] = None
    quarantined_at: Optional[str] = None
    # V0.9.3: track which skills were injected when this outcome was recorded
    injected_skill_ids: list[str] = field(default_factory=list)


# ── 主类 ──────────────────────────────────────────────────────────────────────

class OutcomeTracker:
    """
    消费 RuntimeReporter 日志 → 更新 Phoenix SkillRegistry
    → 触发 Curator drift 检测 → 高风险时 quarantine
    """

    def __init__(
        self,
        phoenix_base_dir: Path | str | None = None,
        reporter_base_dir: Path | str | None = None,
        feedback_file: str = "outcome_feedback.json",
    ) -> None:
        self.base_dir = Path(phoenix_base_dir or Path(__file__).parent.parent)
        self.reporter_base_dir = Path(reporter_base_dir or self.base_dir)
        self._feedback_path = self.base_dir / "logs" / feedback_file
        self._feedback_path.parent.mkdir(parents=True, exist_ok=True)

        self._phoenix: Optional[PhoenixEvo] = None
        self._registry: Optional[SkillRegistry] = None
        self._quarantine: Optional[QuarantineManager] = None
        self._pending: list[dict[str, Any]] = []
        self._processed_ids: set[str] = set()
        self._lock = threading.Lock()

        self._load_processed_ids()

    # ── Phoenix 懒加载 ──────────────────────────────────────────────────────

    def _ensure_phoenix(self) -> None:
        if _PHOENIX_LOADED and self._phoenix is None:
            try:
                # PhoenixEvo 无 load() 方法，用 create_configured() 代替
                self._phoenix = PhoenixEvo.create_configured(self.base_dir)
                self._registry = self._phoenix.registry
                self._quarantine = getattr(self._phoenix, 'quarantine_manager', None)
            except Exception:
                # 无法加载 Phoenix 核心，降级到无 Phoenix 模式
                self._phoenix = None
                self._registry = None
                self._quarantine = None

    # ── 已处理 ID 持久化 ────────────────────────────────────────────────────

    def _load_processed_ids(self) -> None:
        # _processed_ids tracks call_ids (unique per reporter log entry), not skill_ids.
        # Previously this incorrectly tracked skill_ids, causing new log entries to be
        # silently skipped because their empty skill_id matched the set entry.
        if self._feedback_path.exists():
            try:
                data = json.loads(self._feedback_path.read_text(encoding="utf-8"))
                self._processed_ids = {r.get("call_id", r.get("skill_id")) for r in data.get("processed_calls", [])}
            except Exception:
                self._processed_ids = set()

    def _save_processed_ids(self) -> None:
        # Save call_ids, not skill_ids (skill_id can be empty for Phoenix advisory calls)
        data = {"processed_calls": [{"call_id": k} for k in self._processed_ids]}
        self._feedback_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    # ── 核心处理 ────────────────────────────────────────────────────────────

    def process_pending(self) -> dict[str, Any]:
        """
        扫描 reporter 日志，消费所有 pending 结果。
        返回处理摘要。
        """
        self._ensure_phoenix()

        today = datetime.now().strftime("%Y-%m-%d")
        reporter_log = self.reporter_base_dir / "logs" / f"runtime_{today}.jsonl"

        new_outcomes: list[dict[str, Any]] = []
        processed_count = 0

        if reporter_log.exists():
            for line in reporter_log.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                try:
                    record = json.loads(line)
                except Exception:
                    continue

                record_id = record.get("call_id", "")
                skill_id = record.get("selected_skill_id", "")

                # V0.9.2: advisory-only calls have empty skill_id.
                # Map them to a generic Phoenix outcome so the call_id IS tracked.
                # This ensures each bridge write-back is consumed exactly once.
                if not skill_id:
                    skill_id = "phoenix_advisory_call"

                if record_id in self._processed_ids:
                    continue

                execution = record.get("execution_result", "unknown")

                outcome = self._record_outcome(
                    skill_id=skill_id,
                    success=(execution == "success"),
                    failure_reason=record.get("failure_reason"),
                    risk_flag=record.get("risk_flag", False),
                    task_id=record.get("task_id"),
                    session_id=record.get("session_id"),
                    outcome_time=record.get("timestamp"),
                    injected_skill_ids=record.get("injected_skill_ids"),
                )

                # Always track call_id even if _record_outcome returns None
                # (e.g. skill_id was empty before the fix — legacy entries)
                if outcome:
                    new_outcomes.append(outcome)
                self._processed_ids.add(record_id)
                processed_count += 1

        self._save_processed_ids()

        # 漂移检测
        curated = self._auto_curate()

        return {
            "processed": processed_count,
            "new_outcomes": new_outcomes,
            "curated": curated,
        }

    def _record_outcome(
        self,
        skill_id: str,
        success: bool,
        failure_reason: Optional[str] = None,
        risk_flag: bool = False,
        task_id: Optional[str] = None,
        session_id: Optional[str] = None,
        outcome_time: Optional[str] = None,
        injected_skill_ids: Optional[list[str]] = None,
    ) -> Optional[dict[str, Any]]:
        """记录单条 outcome，更新 Phoenix SkillRegistry"""
        if not skill_id:
            return None

        outcome_time = outcome_time or datetime.now().isoformat()

        # 调用 Phoenix SkillRegistry.record_usage
        if self._registry:
            try:
                self._registry.record_usage(skill_id, success)
            except Exception as e:
                logger.warning("record_usage failed for %s: %s", skill_id, e)

        # 追踪连续失败
        outcome = self._load_or_create_outcome(skill_id)

        if success:
            outcome.success_count += 1
            outcome.consecutive_failures = 0
            outcome.last_outcome = "success"
        else:
            outcome.failure_count += 1
            outcome.consecutive_failures += 1
            outcome.last_outcome = "failure"
            outcome.last_failure_reason = failure_reason

        if risk_flag:
            outcome.risk_flags += 1

        outcome.last_used = outcome_time

        # V0.9.3: store injected skill attribution
        if injected_skill_ids:
            outcome.injected_skill_ids = injected_skill_ids

        # 判断状态阈值
        if outcome.consecutive_failures >= Threshold.CONSECUTIVE_FAILURES_FOR_REPLAY:
            outcome.needs_replay = True
        if outcome.consecutive_failures >= Threshold.CONSECUTIVE_FAILURES_FOR_REVIEW:
            outcome.needs_review = True
        if outcome.risk_flags >= Threshold.RISK_INCIDENTS_FOR_QUARANTINE:
            outcome.status = OutcomeStatus.QUARANTINED
            outcome.quarantined_at = outcome_time
            self._quarantine_skill(skill_id, failure_reason or "risk_threshold")

        elif outcome.needs_review:
            outcome.status = OutcomeStatus.FLAGGED
            outcome.flagged_at = outcome_time

        self._save_outcome(outcome)

        return {
            "skill_id": skill_id,
            "status": outcome.status.value,
            "success": success,
            "consecutive_failures": outcome.consecutive_failures,
            "needs_replay": outcome.needs_replay,
            "needs_review": outcome.needs_review,
            "risk_flags": outcome.risk_flags,
            "injected_skill_ids": outcome.injected_skill_ids,
        }

    def _quarantine_skill(self, skill_id: str, reason: str) -> None:
        if self._quarantine:
            try:
                self._quarantine.quarantine_skill(skill_id, reason)
            except Exception as e:
                logger.warning("quarantine failed for %s: %s", skill_id, e)

    def _auto_curate(self) -> int:
        """触发 Curator 漂移检测，返回处理 skill 数"""
        if not _PHOENIX_LOADED:
            return 0
        try:
            self._ensure_phoenix()
            from core.skill_curator import SkillCurator
            curator = SkillCurator(self.base_dir)
            results = curator.scan()
            return len(results)
        except Exception as e:
            logger.warning("auto_curate failed: %s", e)
            return 0

    # ── 健康检查 ─────────────────────────────────────────────────────────────

    def check_skill_health(self, skill_id: str) -> SkillHealthStatus:
        outcome = self._load_or_create_outcome(skill_id)

        if outcome.status == OutcomeStatus.QUARANTINED:
            return SkillHealthStatus.QUARANTINED
        if outcome.consecutive_failures >= Threshold.CONSECUTIVE_FAILURES_FOR_REVIEW:
            return SkillHealthStatus.FAILING
        if outcome.consecutive_failures >= Threshold.CONSECUTIVE_FAILURES_FOR_REPLAY:
            return SkillHealthStatus.DEGRADED
        return SkillHealthStatus.HEALTHY

    def get_skill_outcomes(self) -> list[dict[str, Any]]:
        """返回所有 skill 的 outcome 快照"""
        outcomes = []
        for skill_id in self._processed_ids:
            outcome = self._load_or_create_outcome(skill_id)
            outcomes.append({
                "skill_id": outcome.skill_id,
                "status": outcome.status.value,
                "success_count": outcome.success_count,
                "failure_count": outcome.failure_count,
                "consecutive_failures": outcome.consecutive_failures,
                "last_outcome": outcome.last_outcome,
                "risk_flags": outcome.risk_flags,
                "needs_replay": outcome.needs_replay,
                "needs_review": outcome.needs_review,
                "last_used": outcome.last_used,
            })
        return outcomes

    # ── 持久化 ───────────────────────────────────────────────────────────────

    @property
    def _store_path(self) -> Path:
        return self.base_dir / "logs" / "outcome_tracker_store.json"

    def _load_or_create_outcome(self, skill_id: str) -> SkillOutcome:
        store = self._read_store()
        if skill_id in store:
            data = store[skill_id]
            return SkillOutcome(
                skill_id=skill_id,
                status=OutcomeStatus(data.get("status", "pending")),
                success_count=data.get("success_count", 0),
                failure_count=data.get("failure_count", 0),
                consecutive_failures=data.get("consecutive_failures", 0),
                last_outcome=data.get("last_outcome", "unknown"),
                last_failure_reason=data.get("last_failure_reason"),
                risk_flags=data.get("risk_flags", 0),
                last_used=data.get("last_used"),
                needs_replay=data.get("needs_replay", False),
                needs_review=data.get("needs_review", False),
                flagged_at=data.get("flagged_at"),
                quarantined_at=data.get("quarantined_at"),
            )
        return SkillOutcome(skill_id=skill_id)

    def _save_outcome(self, outcome: SkillOutcome) -> None:
        store = self._read_store()
        store[outcome.skill_id] = {
            "status": outcome.status.value,
            "success_count": outcome.success_count,
            "failure_count": outcome.failure_count,
            "consecutive_failures": outcome.consecutive_failures,
            "last_outcome": outcome.last_outcome,
            "last_failure_reason": outcome.last_failure_reason,
            "risk_flags": outcome.risk_flags,
            "last_used": outcome.last_used,
            "needs_replay": outcome.needs_replay,
            "needs_review": outcome.needs_review,
            "flagged_at": outcome.flagged_at,
            "quarantined_at": outcome.quarantined_at,
        }
        self._write_store(store)

    def _read_store(self) -> dict[str, dict[str, Any]]:
        if self._store_path.exists():
            try:
                return json.loads(self._store_path.read_text(encoding="utf-8"))
            except Exception:
                return {}
        return {}

    def _write_store(self, store: dict[str, dict[str, Any]]) -> None:
        self._store_path.parent.mkdir(parents=True, exist_ok=True)
        self._store_path.write_text(json.dumps(store, ensure_ascii=False, indent=2), encoding="utf-8")
