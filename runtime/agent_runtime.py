"""
agent_runtime.py — Phoenix-Evo V0.8 Agent Runtime
=====================================================

管理任务的完整生命周期：

  created ──► routing ──► injecting ──► running ──► success/failed
                  │                           │
                  └──► no_skill ──► fallback ──┘
                  └──► cancelled ───────────────┘

核心抽象：
  TaskState     — 任务状态的枚举
  TaskContext   — 单次任务的完整上下文（含 PhoenixRuntime 查询结果）
  AgentRuntime  — 任务生命周期管理器（含 Hook 钩子系统）

Hook 生命周期：
  on_task_created   → on_before_route  → on_after_route
  → on_before_inject → on_after_inject → on_before_execute
  → on_execute       (用户回调)         → on_success / on_failure
  → on_before_cleanup → on_after_cleanup → on_task_done

用法：
    runtime = AgentRuntime(phoenix_base_dir=Path("..."))
    # 注册 hook
    runtime.hooks.on_success(lambda ctx: print(f"Done: {ctx.task_id}"))
    # 执行任务
    result = runtime.run("如何修复WSL中文路径", task_type="debugging")
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable

logger = logging.getLogger("agent_runtime")


# ─────────────────────────────────────────────────────────────────────────────
# TaskState — 任务生命周期状态机
# ─────────────────────────────────────────────────────────────────────────────

class TaskState(StrEnum):
    """任务可能处于的状态"""
    CREATED     = "created"      # 刚创建，进入队列
    ROUTING     = "routing"      # 正在路由
    NO_SKILL    = "no_skill"     # 无匹配 skill，触发 fallback
    INJECTING   = "injecting"    # 正在注入上下文
    RUNNING     = "running"      # Skill 正在执行
    SUCCESS     = "success"      # 执行成功
    FAILED      = "failed"       # 执行失败
    CANCELLED   = "cancelled"    # 被取消
    UNKNOWN     = "unknown"


# ─────────────────────────────────────────────────────────────────────────────
# TaskContext — 单次任务的完整上下文
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class TaskContext:
    """
    一次任务的完整执行上下文。
    由 AgentRuntime 创建并贯穿整个生命周期。
    """
    # 身份
    task_id: str
    session_id: str

    # 输入
    task_description: str
    task_type: str | None = None
    risk_level: str = "low"

    # PhoenixRuntime 查询结果（route + guard）
    skill_found: bool = False
    selected_skill_id: str | None = None
    selected_skill_name: str | None = None
    route_score: float = 0.0
    guard_decision: str | None = None
    fallback_reason: str | None = None
    injected_context: str = ""
    context_summary: str = ""

    # 执行结果
    state: TaskState = TaskState.CREATED
    execution_result: str | None = None  # "success" | "failure" | "skipped" | None
    error_message: str | None = None
    failure_reason: str | None = None
    duration_seconds: float = 0.0

    # 生命周期时间戳
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    routing_at: str | None = None
    injecting_at: str | None = None
    running_at: str | None = None
    done_at: str | None = None

    # Cancellation
    cancelled: bool = False

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["state"] = self.state.value
        return d

    @property
    def is_terminal(self) -> bool:
        """是否处于终态"""
        return self.state in (TaskState.SUCCESS, TaskState.FAILED,
                               TaskState.NO_SKILL, TaskState.CANCELLED)

    def can_inject(self) -> bool:
        return self.skill_found and self.guard_decision == "allow"


# ─────────────────────────────────────────────────────────────────────────────
# HookManager — 生命周期钩子
# ─────────────────────────────────────────────────────────────────────────────

class HookManager:
    """
    任务生命周期的钩子系统。
    支持 before / after 两类钩子，before 钩子可以返回 False 拒绝操作。
    """

    def __init__(self):
        self._hooks: dict[str, list[tuple[int, Callable]]] = {}

    def register(self, event: str, callback: Callable, priority: int = 50) -> None:
        """注册钩子，priority 越小越先执行"""
        if event not in self._hooks:
            self._hooks[event] = []
        self._hooks[event].append((priority, callback))
        self._hooks[event].sort(key=lambda x: x[0])

    def emit(self, event: str, context: TaskContext) -> bool:
        """
        触发钩子事件，返回 False 表示阻止操作。
        按 priority 顺序执行，所有 before_* 必须返回 True 才继续。
        """
        if event not in self._hooks:
            return True

        for _, callback in self._hooks[event]:
            try:
                result = callback(context)
                if result is False:
                    logger.warning("[HookManager] %s rejected by %s", event, callback.__name__)
                    return False
            except Exception as e:
                logger.warning("[HookManager] hook %s raised: %s", event, e)
        return True

    # 快捷方法
    def on_task_created(self,   cb: Callable) -> None: self.register("on_task_created",    cb)
    def on_before_route(self,    cb: Callable) -> None: self.register("on_before_route",    cb)
    def on_after_route(self,     cb: Callable) -> None: self.register("on_after_route",      cb)
    def on_before_inject(self,   cb: Callable) -> None: self.register("on_before_inject",   cb)
    def on_after_inject(self,    cb: Callable) -> None: self.register("on_after_inject",    cb)
    def on_before_execute(self,  cb: Callable) -> None: self.register("on_before_execute", cb)
    def on_success(self,         cb: Callable) -> None: self.register("on_success",         cb)
    def on_failure(self,         cb: Callable) -> None: self.register("on_failure",         cb)
    def on_cancelled(self,       cb: Callable) -> None: self.register("on_cancelled",       cb)
    def on_before_cleanup(self,  cb: Callable) -> None: self.register("on_before_cleanup",  cb)
    def on_after_cleanup(self,    cb: Callable) -> None: self.register("on_after_cleanup",   cb)
    def on_task_done(self,       cb: Callable) -> None: self.register("on_task_done",       cb)


# ─────────────────────────────────────────────────────────────────────────────
# CancellationToken — 优雅取消
# ─────────────────────────────────────────────────────────────────────────────

class CancellationToken:
    """可检测取消状态的 token"""

    def __init__(self):
        self._cancelled = False

    def cancel(self) -> None:
        self._cancelled = True

    @property
    def is_cancelled(self) -> bool:
        return self._cancelled


# ─────────────────────────────────────────────────────────────────────────────
# TaskStore — 任务状态持久化
# ─────────────────────────────────────────────────────────────────────────────

class TaskStore:
    """
    任务状态持久化。默认是内存存储，可替换为 SQLite/Redis。
    支持任务重启后恢复。
    """

    def __init__(self, base_dir: Path | str | None = None):
        self.base_dir = Path(base_dir or Path(__file__).parent.parent)
        self._store_path = self.base_dir / "logs" / "task_store.json"
        self._tasks: dict[str, dict[str, Any]] = {}
        self._load()

    def _load(self) -> None:
        if self._store_path.exists():
            try:
                import json
                self._tasks = json.loads(self._store_path.read_text(encoding="utf-8"))
            except Exception:
                self._tasks = {}

    def _save(self) -> None:
        self._store_path.parent.mkdir(parents=True, exist_ok=True)
        import json
        self._store_path.write_text(json.dumps(self._tasks, ensure_ascii=False, indent=2), encoding="utf-8")

    def save(self, context: TaskContext) -> None:
        self._tasks[context.task_id] = context.to_dict()
        self._save()

    def load(self, task_id: str) -> TaskContext | None:
        if task_id not in self._tasks:
            return None
        data = self._tasks[task_id]
        data["state"] = TaskState(data["state"])
        return TaskContext(**data)

    def list_active(self) -> list[str]:
        terminal_states = ("success", "failed", "cancelled")
        return [
            tid for tid, d in self._tasks.items()
            if d.get("state") not in terminal_states
        ]

    def clear_finished(self, older_than_hours: int = 24) -> int:
        """清理超过 N 小时的已完成任务"""
        from datetime import timedelta
        cutoff = datetime.now() - timedelta(hours=older_than_hours)
        before = len(self._tasks)
        self._tasks = {
            tid: d for tid, d in self._tasks.items()
            if d.get("state") not in terminal_states
            or datetime.fromisoformat(d.get("done_at", "1970")).replace(tzinfo=None) > cutoff
        }
        self._save()
        return before - len(self._tasks)


# ─────────────────────────────────────────────────────────────────────────────
# AgentRuntime — 主编排器
# ─────────────────────────────────────────────────────────────────────────────

class AgentRuntime:
    """
    Phoenix-Evo V0.8 Agent Runtime — 任务生命周期管理器。

    串联 PhoenixRuntime 查询 → 上下文注入 → 用户回调执行 → Feedback 汇报。
    """

    def __init__(
        self,
        phoenix_base_dir: Path | str | None = None,
        store: TaskStore | None = None,
    ):
        self.base_dir = Path(phoenix_base_dir or Path(__file__).parent.parent)
        self._store = store or TaskStore(self.base_dir)

        self._phoenix_runtime: Any = None
        self._feedback_dispatcher: Any = None
        self.hooks = HookManager()
        self._cancel_tokens: dict[str, CancellationToken] = {}

    @property
    def phoenix_runtime(self) -> Any:
        if self._phoenix_runtime is None:
            from runtime.phoenix_runtime import PhoenixRuntime
            self._phoenix_runtime = PhoenixRuntime(base_dir=self.base_dir)
        return self._phoenix_runtime

    @property
    def feedback_dispatcher(self) -> Any:
        if self._feedback_dispatcher is None:
            from runtime.feedback_dispatcher import FeedbackDispatcher
            self._feedback_dispatcher = FeedbackDispatcher(
                phoenix_base_dir=self.base_dir,
                reporter_base_dir=self.base_dir,
                mode="sync",
            )
        return self._feedback_dispatcher

    def run(
        self,
        task_description: str,
        task_type: str | None = None,
        risk_level: str = "low",
        session_id: str | None = None,
        task_id: str | None = None,
        execute_fn: Callable[[TaskContext], Any] | None = None,
    ) -> TaskContext:
        """
        执行完整任务生命周期。
        """
        task_id   = task_id   or f"task_{uuid.uuid4().hex[:8]}"
        session_id = session_id or f"session_{uuid.uuid4().hex[:8]}"

        # 1. 创建
        ctx = TaskContext(
            task_id=task_id,
            session_id=session_id,
            task_description=task_description,
            task_type=task_type,
            risk_level=risk_level,
            state=TaskState.CREATED,
        )
        self._store.save(ctx)
        self._cancel_tokens[task_id] = CancellationToken()

        if not self.hooks.emit("on_task_created", ctx):
            return self._cancel_task(ctx, "hook_rejected_on_created")

        # 2. 路由
        ctx.state = TaskState.ROUTING
        ctx.routing_at = datetime.now().isoformat()
        self._store.save(ctx)

        if not self.hooks.emit("on_before_route", ctx):
            return self._cancel_task(ctx, "hook_rejected_on_route")

        try:
            rt_result = self.phoenix_runtime.route(
                task_description=task_description,
                task_type=task_type,
                risk_level=risk_level,
                task_id=task_id,
                session_id=session_id,
            )
        except Exception as e:
            logger.error("PhoenixRuntime.route() failed: %s", e)
            return self._fail_task(ctx, f"route_error: {e}")

        ctx.skill_found        = rt_result.skill_found
        ctx.selected_skill_id  = rt_result.selected_skill_id
        ctx.selected_skill_name = rt_result.selected_skill_name
        ctx.route_score        = rt_result.route_score
        ctx.guard_decision     = rt_result.guard_decision
        ctx.fallback_reason    = rt_result.fallback_reason
        ctx.context_summary    = rt_result.context_summary or rt_result.context

        if not self.hooks.emit("on_after_route", ctx):
            return self._cancel_task(ctx, "hook_rejected_after_route")

        # 3. 无匹配 → fallback
        if not ctx.skill_found:
            ctx.state = TaskState.NO_SKILL
            ctx.done_at = datetime.now().isoformat()
            self._store.save(ctx)
            self._report_skipped(ctx)
            self.hooks.emit("on_task_done", ctx)
            return ctx

        # 4. 注入
        if not self.hooks.emit("on_before_inject", ctx):
            return self._cancel_task(ctx, "hook_rejected_on_inject")

        ctx.state = TaskState.INJECTING
        ctx.injecting_at = datetime.now().isoformat()
        self._store.save(ctx)

        ctx.injected_context = rt_result.context_summary or rt_result.context or ""

        if not self.hooks.emit("on_after_inject", ctx):
            return self._cancel_task(ctx, "hook_rejected_after_inject")

        # 5. 执行
        if not self.hooks.emit("on_before_execute", ctx):
            return self._cancel_task(ctx, "hook_rejected_on_execute")

        ctx.state = TaskState.RUNNING
        ctx.running_at = datetime.now().isoformat()
        self._store.save(ctx)

        if execute_fn:
            try:
                if self._cancel_tokens[task_id].is_cancelled:
                    return self._cancel_task(ctx, "cancelled_before_execution")
                execute_fn(ctx)
                ctx.execution_result = "success"
            except Exception as e:
                ctx.execution_result = "failure"
                ctx.failure_reason = str(e)
                ctx.error_message = str(e)
        else:
            ctx.execution_result = "success"

        # 6. 终态
        if ctx.execution_result == "success":
            self._succeed_task(ctx)
        else:
            self._fail_task(ctx, ctx.failure_reason or "unknown_error")

        return ctx

    def cancel(self, task_id: str) -> bool:
        """取消指定任务"""
        if task_id in self._cancel_tokens:
            self._cancel_tokens[task_id].cancel()
            ctx = self._store.load(task_id)
            if ctx and not ctx.is_terminal:
                self._cancel_task(ctx, "user_requested")
                return True
        return False

    def get_task(self, task_id: str) -> TaskContext | None:
        return self._store.load(task_id)

    def list_tasks(self) -> list[str]:
        return self._store.list_active()

    # ── 内部 ───────────────────────────────────────────────────────────────

    def _cancel_task(self, ctx: TaskContext, reason: str) -> TaskContext:
        ctx.state = TaskState.CANCELLED
        ctx.failure_reason = reason
        ctx.done_at = datetime.now().isoformat()
        self._store.save(ctx)
        self.hooks.emit("on_cancelled", ctx)
        self._cleanup(ctx)
        return ctx

    def _succeed_task(self, ctx: TaskContext) -> TaskContext:
        ctx.state = TaskState.SUCCESS
        ctx.done_at = datetime.now().isoformat()
        self._store.save(ctx)
        self.hooks.emit("on_success", ctx)
        self._cleanup(ctx)
        return ctx

    def _fail_task(self, ctx: TaskContext, reason: str) -> TaskContext:
        ctx.state = TaskState.FAILED
        ctx.failure_reason = reason
        ctx.done_at = datetime.now().isoformat()
        self._store.save(ctx)
        self.hooks.emit("on_failure", ctx)
        self._cleanup(ctx)
        return ctx

    def _cleanup(self, ctx: TaskContext) -> None:
        self.hooks.emit("on_before_cleanup", ctx)

        if ctx.selected_skill_id:
            try:
                if ctx.execution_result == "success":
                    self.feedback_dispatcher.report_success(
                        skill_id=ctx.selected_skill_id,
                        task_id=ctx.task_id,
                        session_id=ctx.session_id,
                        duration=ctx.duration_seconds,
                    )
                else:
                    self.feedback_dispatcher.report_failure(
                        skill_id=ctx.selected_skill_id,
                        failure_reason=ctx.failure_reason or "unknown",
                        risk_flag=(ctx.risk_level in ("high", "critical")),
                        task_id=ctx.task_id,
                        session_id=ctx.session_id,
                        duration=ctx.duration_seconds,
                    )
            except Exception as e:
                logger.warning("FeedbackDispatcher report failed: %s", e)

        self.hooks.emit("on_after_cleanup", ctx)
        self.hooks.emit("on_task_done", ctx)
        self._cancel_tokens.pop(ctx.task_id, None)

    def _report_skipped(self, ctx: TaskContext) -> None:
        try:
            self.feedback_dispatcher.report_skipped(
                skill_id=ctx.selected_skill_id or "",
                reason=ctx.fallback_reason or "no_skill_found",
                task_id=ctx.task_id,
                session_id=ctx.session_id,
            )
        except Exception as e:
            logger.warning("FeedbackDispatcher report_skipped failed: %s", e)
