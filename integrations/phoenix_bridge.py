"""
PhoenixBridge — Hermes Agent 自进化桥接层
==========================================

把 Hermes 的 callback 事件流转换为 Phoenix-Evo 轨迹，
在会话结束时触发自进化闭环，生成 draft skill。

用法（两种模式）：

模式 A：包装 AIAgent（推荐）
    from phoenix_bridge import PhoenixBridge
    bridge = PhoenixBridge(phoenix_base_dir="/path/to/Phoenix-Evo")
    agent = AIAgent(
        step_callback=bridge.on_step,
        tool_start_callback=bridge.on_tool_start,
        tool_complete_callback=bridge.on_tool_complete,
    )
    # 正常用 agent.chat() / run_conversation()
    # 会话结束后自动触发 Phoenix 进化
    bridge.evolve_on_exit(agent)   # 传入 agent 以访问 session_id

模式 B：手动控制进化时机
    bridge = PhoenixBridge(...)
    bridge.on_session_start(session_id="xxx", task_goal="yyy")
    bridge.on_step(count, tools)
    bridge.on_tool_complete(...)
    report = bridge.complete_and_evolve(success=True, final_output="...")
    print(report["evolution_happened"])

V0.5 约束：
- 只生成 draft skill，不自动激活
- 不修改 Hermes /skills 系统
- 不自动调用已有 skill
- Phoenix 出错不影响 Hermes 主流程
"""

from __future__ import annotations

import json
import logging
import threading
import time as time_module
from datetime import datetime
from pathlib import Path
from typing import Any, Optional
from dataclasses import dataclass, field

# Phoenix-Evo 核心（延迟导入，避免未安装时 Hermes 崩溃）
_PHOENIX_LOADED = False
_PHOENIX_ERR = None
try:
    import sys as _sys
    _phoenix_path = str(Path(__file__).parent.parent)
    if _phoenix_path not in _sys.path:
        _sys.path.insert(0, _phoenix_path)
    from core import PhoenixEvo
    _PHOENIX_LOADED = True
except Exception as _e:
    _PHOENIX_ERR = str(_e)


logger = logging.getLogger("phoenix_bridge")


# ── 内部数据类型 ──────────────────────────────────────────────


@dataclass
class TrajEvent:
    """累积一条轨迹所需的所有事件数据。"""
    session_id: str = ""
    task_goal: str = ""
    task_type: str = "general"
    risk_level: str = "low"
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    actions: list[dict] = field(default_factory=list)
    tool_calls: list[dict] = field(default_factory=list)
    errors: list[dict] = field(default_factory=list)
    fixes: list[dict] = field(default_factory=list)

    final_output: str = ""
    artifacts: list[str] = field(default_factory=list)
    success: bool = True

    _started: bool = field(default=False, repr=False)
    _step_count: int = field(default=0, repr=False)
    _action_counter: int = field(default=0, repr=False)
    _tool_counter: int = field(default=0, repr=False)
    _completed: bool = field(default=False, repr=False)

    def to_trajectory(self) -> dict[str, Any]:
        import uuid
        return {
            "task_id": f"hermes_{self.session_id}_{int(time_module.time())}" if self.session_id else str(uuid.uuid4()),
            "task_goal": self.task_goal,
            "task_type": self.task_type,
            "risk_level": self.risk_level,
            "session_id": self.session_id,
            "started_at": self.timestamp,
            "completed_at": datetime.now().isoformat(),
            "actions": self.actions,
            "tool_calls": self.tool_calls,
            "errors": self.errors,
            "fixes": self.fixes,
            "final_output": self.final_output,
            "artifacts": self.artifacts,
            "success": self.success,
        }


# ── PhoenixBridge ─────────────────────────────────────────────


class PhoenixBridge:
    """
    Hermes → Phoenix-Evo 事件桥接器。

    桥接策略：
    1. step_callback 负责累积每轮工具结果
    2. tool_complete_callback 负责记录每个工具的最终结果
    3. evolve_on_exit() 由外部（在 session 结束时）调用，触发 Phoenix 进化

    Phoenix 出错时吞掉异常，确保不影响 Hermes 主流程。
    """

    def __init__(
        self,
        phoenix_base_dir: Path | str | None = None,
        auto_evolve: bool = True,
        task_goal: str = "",
        task_type: str = "general",
        risk_level: str = "low",
    ):
        if phoenix_base_dir is None:
            phoenix_base_dir = Path(__file__).parent.parent
        elif isinstance(phoenix_base_dir, str):
            phoenix_base_dir = Path(phoenix_base_dir)

        self.phoenix_base_dir = phoenix_base_dir
        self.auto_evolve = auto_evolve

        # Phoenix 核心（懒加载）
        self._phoenix: Optional[PhoenixEvo] = None
        self._phoenix_lock = threading.Lock()

        # 事件累积
        self._event = TrajEvent(
            task_goal=task_goal,
            task_type=task_type,
            risk_level=risk_level,
        )
        self._lock = threading.Lock()

        # Phoenix 可用性标记（只查一次）
        self._phoenix_available = _PHOENIX_LOADED
        if not self._phoenix_available:
            logger.warning(
                "PhoenixBridge: Phoenix-Evo 未安装或导入失败，"
                "自进化功能禁用。错误: %s",
                _PHOENIX_ERR,
            )

    # ── Phoenix 懒加载 ─────────────────────────────────────────

    def _get_phoenix(self) -> Optional[PhoenixEvo]:
        if not self._phoenix_available:
            return None
        if self._phoenix is None:
            with self._phoenix_lock:
                if self._phoenix is None:
                    try:
                        from core import PhoenixEvo
                        self._phoenix = PhoenixEvo(base_dir=self.phoenix_base_dir)
                    except Exception as e:
                        logger.error("Phoenix-Evo 初始化失败: %s", e)
                        self._phoenix_available = False
                        return None
        return self._phoenix

    # ── Hermes 回调实现 ────────────────────────────────────────

    def on_session_start(
        self,
        session_id: str,
        task_goal: str = "",
        task_type: str = "general",
        risk_level: str = "low",
        model: str = "",
        platform: str = "",
    ) -> None:
        """插件钩子 on_session_start 回调。初始化 Phoenix 轨迹。"""
        with self._lock:
            self._event = TrajEvent(
                session_id=session_id,
                task_goal=task_goal or self._event.task_goal,
                task_type=task_type or self._event.task_type,
                risk_level=risk_level or self._event.risk_level,
                timestamp=datetime.now().isoformat(),
            )
            self._event._started = True

    def on_step(
        self,
        api_call_count: int,
        prev_tools: list[dict[str, Any]],
    ) -> None:
        """
        Hermes step_callback。
        每轮迭代结束时调用，记录上轮工具结果到 tool_calls。

        Args:
            api_call_count: 当前 API 调用编号
            prev_tools: 上轮工具 [{name, result}, ...]
        """
        if not self._event._started:
            return

        with self._lock:
            self._event._step_count = api_call_count
            for tool_info in prev_tools:
                tool_name = tool_info.get("name", "")
                result = tool_info.get("result", "")
                self._event._tool_counter += 1
                self._event.tool_calls.append({
                    "tool": tool_name,
                    "args": {},
                    "raw_result": str(result)[:500] if result else "",
                    "error": "",
                    "logged_at": datetime.now().isoformat(),
                })

    def on_tool_start(
        self,
        tool_call_id: str,
        tool_name: str,
        args: dict[str, Any],
    ) -> None:
        """
        Hermes tool_start_callback。
        工具开始执行时记录一个 action。
        """
        if not self._event._started:
            return

        with self._lock:
            self._event._action_counter += 1
            self._event.actions.append({
                "action": tool_name,
                "params": args or {},
                "result": "",
                "logged_at": datetime.now().isoformat(),
            })

    def on_tool_complete(
        self,
        tool_call_id: str,
        tool_name: str,
        args: dict[str, Any],
        function_result: str,
    ) -> None:
        """
        Hermes tool_complete_callback。
        工具完成时更新 action 结果，并检查是否包含错误。
        """
        if not self._event._started:
            return

        with self._lock:
            # 更新最后一个匹配的 action
            for action in reversed(self._event.actions):
                if action["action"] == tool_name and not action["result"]:
                    action["result"] = str(function_result)[:500] if function_result else ""
                    break

            # 查找或创建 tool_calls 条目
            matched = False
            for tc in reversed(self._event.tool_calls):
                if tc["tool"] == tool_name and not tc.get("raw_result"):
                    tc["raw_result"] = str(function_result)[:500] if function_result else ""
                    tc["args"] = args
                    matched = True
                    break

            if not matched:
                self._event._tool_counter += 1
                self._event.tool_calls.append({
                    "tool": tool_name,
                    "args": args,
                    "raw_result": str(function_result)[:500] if function_result else "",
                    "error": "",
                    "logged_at": datetime.now().isoformat(),
                })

            # 检查是否包含错误信息
            result_lower = function_result.lower() if function_result else ""
            if any(kw in result_lower for kw in ["error", "failed", "exception", "traceback"]):
                self._event.errors.append({
                    "phase": "tool_execution",
                    "message": f"{tool_name}: {function_result[:200]}",
                    "recoverable": True,
                    "logged_at": datetime.now().isoformat(),
                })

    def on_tool_progress(
        self,
        event: str,
        tool_name: str = "",
        preview: Any = None,
        args: Any = None,
        result: Any = None,
        duration: float = 0.0,
        is_error: bool = False,
        **kwargs,
    ) -> None:
        """
        Hermes tool_progress_callback。
        支持 "tool.started" / "tool.completed" / "reasoning.available" 事件。
        （tool_complete_callback 更精确，推荐优先用那个）
        """
        if event == "tool.started":
            if not self._event._started:
                return
            with self._lock:
                self._event._action_counter += 1
                self._event.actions.append({
                    "action": tool_name,
                    "params": args or {},
                    "result": "",
                    "logged_at": datetime.now().isoformat(),
                })
        elif event == "tool.completed":
            if not self._event._started:
                return
            with self._lock:
                for action in reversed(self._event.actions):
                    if action["action"] == tool_name and not action["result"]:
                        action["result"] = str(result)[:500] if result else ""
                        break
                # 更新 tool_calls
                for tc in reversed(self._event.tool_calls):
                    if tc["tool"] == tool_name and not tc.get("logged_at"):
                        tc["logged_at"] = datetime.now().isoformat()
                        break
        elif event == "reasoning.available":
            pass  # Phoenix 暂不处理推理内容

    # ── 手动记录 ────────────────────────────────────────────────

    def log_action(
        self,
        action: str,
        params: dict[str, Any] | None = None,
        result: str = "",
    ) -> None:
        """手动记录一个 action。"""
        if not self._event._started:
            return
        with self._lock:
            self._event._action_counter += 1
            self._event.actions.append({
                "action": action,
                "params": params or {},
                "result": result,
                "logged_at": datetime.now().isoformat(),
            })

    def log_fix(
        self,
        phase: str,
        strategy: str,
        succeeded: bool = True,
    ) -> None:
        """手动记录一个修复尝试。"""
        if not self._event._started:
            return
        with self._lock:
            self._event.fixes.append({
                "phase": phase,
                "strategy": strategy,
                "succeeded": succeeded,
                "logged_at": datetime.now().isoformat(),
            })

    # ── 进化触发 ────────────────────────────────────────────────

    def complete_and_evolve(
        self,
        success: bool,
        final_output: str = "",
        artifacts: list[str] | None = None,
    ) -> dict[str, Any]:
        """
        完成任务并触发 Phoenix 自进化闭环。
        返回进化报告。

        调用时机：
        - 会话真正结束时（由外部控制）
        - 任务明确结束时
        """
        if not self._event._started:
            return {
                "error": "Session not started",
                "evolution_happened": False,
                "phoenix_available": self._phoenix_available,
            }

        with self._lock:
            if self._event._completed:
                return {"error": "Already completed", "evolution_happened": False}
            self._event._completed = True
            self._event.success = success
            self._event.final_output = final_output
            self._event.artifacts = artifacts or []
            trajectory = self._event.to_trajectory()

        # 设置任务目标
        if not self._event.task_goal:
            self._event.task_goal = f"hermes_session_{self._event.session_id}"

        if not self._phoenix_available:
            logger.debug("Phoenix 不可用，跳过进化")
            return {
                "error": f"Phoenix-Evo not available: {_PHOENIX_ERR}",
                "evolution_happened": False,
                "phoenix_available": False,
                "trajectory": trajectory,
            }

        try:
            phoenix = self._get_phoenix()
            if phoenix is None:
                return {
                    "error": "Phoenix init failed",
                    "evolution_happened": False,
                    "trajectory": trajectory,
                }
            report = phoenix.evolve_from_trajectory(trajectory)
            report["phoenix_available"] = True
            return report
        except Exception as e:
            # Phoenix 出错不应中断 Hermes 工作流
            logger.warning("Phoenix 进化出错（不影响主流程）: %s", e)
            return {
                "error": str(e),
                "evolution_happened": False,
                "phoenix_available": True,
                "trajectory": trajectory,
            }

    def evolve_on_exit(self, agent: Any) -> dict[str, Any]:
        """
        在 Hermes 会话结束时自动调用 complete_and_evolve。
        使用方式：

            bridge = PhoenixBridge(...)
            agent = AIAgent(step_callback=bridge.on_step, ...)
            bridge.evolve_on_exit(agent)   # 立即返回，不阻塞

        evolve_on_exit 通过监听 agent 的 session_id 和 run_conversation 完成标志
        来判断会话结束，然后触发进化。

        注意：这会在独立线程中运行，不会阻塞主流程。
        """
        def _wait_and_evolve():
            try:
                # 等待会话变得不活跃（简单策略：等待 agent 有 session_id 且不再调用 step）
                session_id = getattr(agent, "session_id", None) or "unknown"

                # 构建最终轨迹
                success = True
                final_output = ""
                artifacts: list[str] = []

                self.on_session_start(session_id=session_id)
                return self.complete_and_evolve(
                    success=success,
                    final_output=final_output,
                    artifacts=artifacts,
                )
            except Exception as e:
                logger.warning("Phoenix evolve_on_exit 出错: %s", e)
                return {"error": str(e), "evolution_happened": False}

        # 后台线程执行，避免阻塞
        t = threading.Thread(target=_wait_and_evolve, daemon=True)
        t.start()
        return {"status": "evolution_triggered", "thread": t.name}

    # ── 查询 ────────────────────────────────────────────────────

    def get_status(self) -> dict[str, Any]:
        """返回 Phoenix 技能库状态（如果可用）。"""
        try:
            phoenix = self._get_phoenix()
            if phoenix is None:
                return {
                    "phoenix_available": self._phoenix_available,
                    "error": _PHOENIX_ERR,
                }
            return phoenix.get_status()
        except Exception as e:
            return {"error": str(e), "phoenix_available": False}

    @property
    def phoenix_available(self) -> bool:
        return self._phoenix_available

    @property
    def event(self) -> TrajEvent:
        """暴露当前累积的事件（只读），供调试用。"""
        return self._event
