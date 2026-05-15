"""
RuntimeReporter: 记录 skill 运行时调用情况，供 V0.7 Feedback Loop 使用
V0.6 - Phoenix-Evo Runtime Skill Router

记录内容：
  - task_id / session_id
  - selected_skill_id / route_score / guard_decision
  - injected_context（摘要）
  - execution_result: success / failure
  - failure_reason
  - timestamp

数据流向：
  RuntimeReporter → Phoenix SkillRegistry.record_usage()
                  → Phoenix SkillCard 更新
                  → V0.7 OutcomeTracker / Curator
"""
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from runtime.runtime_guard import GuardDecision


@dataclass
class RuntimeCallRecord:
    """单次 skill 调用的完整记录"""
    call_id: str
    task_id: str
    session_id: str
    task_description: str
    selected_skill_id: str | None
    selected_skill_name: str | None
    route_score: float | None
    guard_decision: str | None  # GuardDecision.value
    injected: bool
    context_summary: str         # 注入上下文摘要（截断至 200 字符）
    execution_result: str        # "success" | "failure" | "skipped"
    failure_reason: str | None
    error_message: str | None
    duration_seconds: float | None
    timestamp: str = field(
        default_factory=lambda: datetime.now().isoformat()
    )

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["timestamp"] = self.timestamp
        return d


class RuntimeReporter:
    """
    V0.6 运行时调用记录器。
    所有 Hermes skill 路由和调用结果都写入此记录器，
    供 V0.7 OutcomeTracker / Curator 使用。
    """

    def __init__(self, base_dir: Path | str | None = None):
        self.base_dir = Path(base_dir) if base_dir else Path(__file__).parent.parent
        self.log_dir = self.base_dir / "logs" / "runtime"
        self.log_dir.mkdir(parents=True, exist_ok=True)
        # 当天日志文件
        self._log_path: Path | None = None

    # ------------------------------------------------------------------ #
    # 公开接口                                                          #
    # ------------------------------------------------------------------ #

    def record(
        self,
        task_id: str,
        session_id: str,
        task_description: str,
        selected_skill_id: str | None = None,
        selected_skill_name: str | None = None,
        route_score: float | None = None,
        guard_decision: GuardDecision | None = None,
        injected: bool = False,
        context_summary: str = "",
        execution_result: str = "skipped",
        failure_reason: str | None = None,
        error_message: str | None = None,
        duration_seconds: float | None = None,
        call_id: str | None = None,
    ) -> RuntimeCallRecord:
        """
        记录一次 skill 路由调用。

        参数:
            task_id:          任务 ID
            session_id:       会话 ID
            task_description: 任务描述
            selected_skill_*:  被选中的 skill 信息
            route_score:      路由得分
            guard_decision:   Guard 决策
            injected:         是否成功注入 Hermes
            context_summary:   注入上下文摘要
            execution_result: 执行结果（success/failure/skipped）
            failure_reason:   失败原因
            error_message:    错误信息
            duration_seconds: 耗时
            call_id:          调用 ID（不提供则自动生成）
        """
        import uuid

        if call_id is None:
            call_id = f"call_{task_id}_{uuid.uuid4().hex[:8]}"

        # 截断 context_summary
        summary = context_summary[:200] + "..." if len(context_summary) > 200 else context_summary

        record = RuntimeCallRecord(
            call_id=call_id,
            task_id=task_id,
            session_id=session_id,
            task_description=task_description[:100],
            selected_skill_id=selected_skill_id,
            selected_skill_name=selected_skill_name,
            route_score=route_score,
            guard_decision=guard_decision.value if guard_decision else None,
            injected=injected,
            context_summary=summary,
            execution_result=execution_result,
            failure_reason=failure_reason,
            error_message=error_message,
            duration_seconds=duration_seconds,
        )

        self._append_record(record)
        return record

    def record_success(
        self,
        task_id: str,
        session_id: str,
        skill_id: str,
        skill_name: str,
        call_id: str | None = None,
    ) -> RuntimeCallRecord:
        """快捷方法：记录 skill 使用成功"""
        return self.record(
            task_id=task_id,
            session_id=session_id,
            task_description="",
            selected_skill_id=skill_id,
            selected_skill_name=skill_name,
            injected=True,
            execution_result="success",
            call_id=call_id,
        )

    def record_failure(
        self,
        task_id: str,
        session_id: str,
        skill_id: str,
        skill_name: str,
        failure_reason: str,
        error_message: str | None = None,
        call_id: str | None = None,
    ) -> RuntimeCallRecord:
        """快捷方法：记录 skill 使用失败"""
        return self.record(
            task_id=task_id,
            session_id=session_id,
            task_description="",
            selected_skill_id=skill_id,
            selected_skill_name=skill_name,
            injected=True,
            execution_result="failure",
            failure_reason=failure_reason,
            error_message=error_message,
            call_id=call_id,
        )

    def record_skipped(
        self,
        task_id: str,
        session_id: str,
        reason: str = "no_skill_found",
    ) -> RuntimeCallRecord:
        """快捷方法：记录无 skill 路由（跳过）"""
        return self.record(
            task_id=task_id,
            session_id=session_id,
            task_description="",
            selected_skill_id=None,
            selected_skill_name=None,
            injected=False,
            execution_result="skipped",
            failure_reason=reason,
        )

    # ------------------------------------------------------------------ #
    # 查询接口（供 V0.7 / Curator 使用）                                   #
    # ------------------------------------------------------------------ #

    def get_recent_calls(
        self,
        skill_id: str | None = None,
        session_id: str | None = None,
        limit: int = 20,
    ) -> list[RuntimeCallRecord]:
        """查询最近的调用记录（供 V0.7 OutcomeTracker 使用）"""
        records = []
        today_path = self._get_log_path()
        if today_path.exists():
            for line in today_path.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                try:
                    d = json.loads(line)
                    if skill_id and d.get("selected_skill_id") != skill_id:
                        continue
                    if session_id and d.get("session_id") != session_id:
                        continue
                    records.append(RuntimeCallRecord(**d))
                except Exception:
                    continue
        return records[-limit:]

    def get_skill_stats(self, skill_id: str) -> dict[str, Any]:
        """获取某个 skill 的运行时统计（供 Router 和 Guard 使用）"""
        records = self.get_recent_calls(skill_id=skill_id, limit=100)
        if not records:
            return {
                "usage_count": 0,
                "success_count": 0,
                "failure_count": 0,
                "success_rate": 0.0,
                "recent_failures": 0,
            }

        success = sum(1 for r in records if r.execution_result == "success")
        failure = sum(1 for r in records if r.execution_result == "failure")
        total   = len(records)

        # 最近连续失败
        recent_fail = 0
        for r in reversed(records):
            if r.execution_result == "failure":
                recent_fail += 1
            else:
                break

        return {
            "usage_count":     total,
            "success_count":   success,
            "failure_count":   failure,
            "success_rate":    round(success / total, 3) if total else 0.0,
            "recent_failures": recent_fail,
        }

    # ------------------------------------------------------------------ #
    # 内部实现                                                          #
    # ------------------------------------------------------------------ #

    def _get_log_path(self) -> Path:
        if self._log_path is None:
            date_str = datetime.now().strftime("%Y%m%d")
            self._log_path = self.log_dir / f"runtime_{date_str}.jsonl"
        return self._log_path

    def _append_record(self, record: RuntimeCallRecord) -> None:
        path = self._get_log_path()
        line = json.dumps(record.to_dict(), ensure_ascii=False)
        path.open("a", encoding="utf-8").write(line + "\n")
