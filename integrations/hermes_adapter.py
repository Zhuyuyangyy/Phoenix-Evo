"""
Phoenix-Evo V0.5 Hermes Bridge
Hermes 事件适配层：把 Hermes 的回调事件转成 Phoenix 轨迹格式。

集成点：
- step_callback(api_call_count, prev_tools)
- tool_progress_callback(event, tool_name, args, result, duration, is_error)
- tool_complete_callback(tool_call_id, tool_name, tool_args, tool_result)
- plugin hook: on_session_start
- plugin hook: pre_llm_call

V0.5 约束：只生成 draft skill，禁止自动激活/调用/修改 Hermess 系统 skill。
"""

from __future__ import annotations

# Phoenix-Evo 核心模块（假设已安装或通过 path 引用）
import sys
import threading
import time as time_module
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

_phoenix_path = str(Path(__file__).parent.parent)
if _phoenix_path not in sys.path:
    sys.path.insert(0, _phoenix_path)


@dataclass
class HermesEvent:
    """Hermes → Phoenix 的统一事件格式。"""
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    session_id: str = ""
    task_goal: str = ""
    task_type: str = "general"
    risk_level: str = "low"
    # 轨迹数据
    actions: list[dict] = field(default_factory=list)
    tool_calls: list[dict] = field(default_factory=list)
    errors: list[dict] = field(default_factory=list)
    fixes: list[dict] = field(default_factory=list)
    plan: list[dict] = field(default_factory=list)
    final_output: str = ""
    artifacts: list[str] = field(default_factory=list)
    success: bool = True

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
            "plan": self.plan,
            "final_output": self.final_output,
            "artifacts": self.artifacts,
            "success": self.success,
        }


class HermesAdapter:
    """
    Hermes 事件适配器。

    使用方式：

    ```python
    from run_agent import AIAgent
    from integrations.hermes_adapter import HermesAdapter

    adapter = HermesAdapter(
        phoenix_base_dir=Path("/path/to/Phoenix-Evo"),
        hermes_session_id="session_abc123",
        task_goal="用户目标描述",
        task_type="coding",
        risk_level="low",
    )

    agent = AIAgent(
        step_callback=adapter.on_step,
        tool_progress_callback=adapter.on_tool_progress,
        tool_complete_callback=adapter.on_tool_complete,
    )

    # 任务结束后
    report = adapter.complete_and_evolve(success=True, final_output="...")
    print(report)
    ```

    V0.5 约束：
    - 只生成 draft skill，不自动激活
    - 不修改 Hermes /skills 系统
    - 不自动调用已有 skill
    """

    def __init__(
        self,
        phoenix_base_dir: Path | str | None = None,
        hermes_session_id: str = "",
        task_goal: str = "",
        task_type: str = "general",
        risk_level: str = "low",
    ):
        if phoenix_base_dir is None:
            phoenix_base_dir = Path(__file__).parent.parent
        elif isinstance(phoenix_base_dir, str):
            phoenix_base_dir = Path(phoenix_base_dir)

        self.phoenix_base_dir = phoenix_base_dir
        self.session_id = hermes_session_id
        self.task_goal = task_goal
        self.task_type = task_type
        self.risk_level = risk_level

        # Phoenix 核心组件（延迟导入，避免循环依赖）
        self._phoenix = None
        self._phoenix_lock = threading.Lock()

        # 内部状态
        self._event = HermesEvent(
            session_id=hermes_session_id,
            task_goal=task_goal,
            task_type=task_type,
            risk_level=risk_level,
        )
        self._action_counter = 0
        self._tool_counter = 0
        self._started = False
        self._completed = False
        self._step_count = 0
        self._last_tool_name = ""

    # ── Phoenix 懒加载 ───────────────────────────────────────

    def _get_phoenix(self):
        """懒加载 Phoenix 核心（避免启动时未安装则报错）。"""
        if self._phoenix is None:
            with self._phoenix_lock:
                if self._phoenix is None:
                    try:
                        from core import PhoenixEvo
                        self._phoenix = PhoenixEvo(base_dir=self.phoenix_base_dir)
                    except Exception as e:
                        raise RuntimeError(
                            f"Phoenix-Evo 导入失败，请确认 core/ 在 Python path 中: {e}"
                        )
        return self._phoenix

    # ── Hermes 回调实现 ─────────────────────────────────────

    def on_session_start(
        self,
        session_id: str,
        model: str,
        platform: str = "",
    ) -> None:
        """
        插件钩子 on_session_start 回调。
        新会话创建时初始化 Phoenix 轨迹。
        """
        self.session_id = session_id
        self._event.session_id = session_id
        self._started = True
        self._event.timestamp = datetime.now().isoformat()

    def on_step(
        self,
        api_call_count: int,
        prev_tools: list[dict[str, Any]],
    ) -> None:
        """
        Hermes step_callback。
        每轮迭代开始时调用，记录上轮工具结果。

        Args:
            api_call_count: 当前 API 调用编号
            prev_tools: 上轮工具 [{name, result}, ...]
        """
        self._step_count = api_call_count

        # 记录上轮工具调用的结果
        for tool_info in prev_tools:
            tool_name = tool_info.get("name", "")
            result = tool_info.get("result", "")
            self._tool_counter += 1
            self._event.tool_calls.append({
                "tool": tool_name,
                "args": {},
                "raw_result": str(result)[:500] if result else "",
                "error": "",
                "logged_at": datetime.now().isoformat(),
            })

    def on_tool_progress(
        self,
        event: str,  # "tool.started" | "tool.completed" | "reasoning.available"
        tool_name: str = "",
        args: Any = None,
        result: Any = None,
        duration: float = 0.0,
        is_error: bool = False,
        **kwargs,
    ) -> None:
        """
        Hermes tool_progress_callback。
        工具开始/完成时调用。

        Events:
            "tool.started"      — 工具开始执行
            "tool.completed"     — 工具完成
            "reasoning.available"— 模型在思考
        """
        if event == "tool.started":
            self._last_tool_name = tool_name
            self._action_counter += 1
            self._event.actions.append({
                "action": tool_name,
                "params": args or {},
                "result": "",
                "logged_at": datetime.now().isoformat(),
            })

        elif event == "tool.completed":
            # 更新最后一个 action 的结果
            if self._event.actions and self._event.actions[-1]["action"] == tool_name:
                self._event.actions[-1]["result"] = str(result)[:500] if result else ""

            # 更新 tool_calls 中匹配的记录
            for tc in reversed(self._event.tool_calls):
                if tc["tool"] == tool_name and not tc.get("logged_at"):
                    tc["logged_at"] = datetime.now().isoformat()
                    break

        elif event == "reasoning.available":
            pass  # Phoenix 暂不处理推理内容

    def on_tool_complete(
        self,
        tool_call_id: str,
        tool_name: str,
        tool_args: dict[str, Any],
        tool_result: str,
    ) -> None:
        """
        Hermes tool_complete_callback。
        工具完成时调用，记录最终结果。
        """
        # 查找或创建 tool_calls 条目
        matched = False
        for tc in self._event.tool_calls:
            if tc["tool"] == tool_name and not tc.get("raw_result"):
                tc["raw_result"] = tool_result[:500] if tool_result else ""
                tc["args"] = tool_args
                matched = True
                break

        if not matched:
            self._tool_counter += 1
            self._event.tool_calls.append({
                "tool": tool_name,
                "args": tool_args,
                "raw_result": tool_result[:500] if tool_result else "",
                "error": "",
                "logged_at": datetime.now().isoformat(),
            })

        # 检查是否包含错误信息
        if "error" in tool_result.lower() or "failed" in tool_result.lower():
            self._event.errors.append({
                "phase": "tool_execution",
                "message": f"{tool_name}: {tool_result[:200]}",
                "recoverable": True,
                "logged_at": datetime.now().isoformat(),
            })

    def on_task_end(
        self,
        success: bool,
        final_output: str = "",
        artifacts: list[str] | None = None,
    ) -> dict[str, Any]:
        """
        任务结束时调用。
        注意：Hermes 的 run_conversation 返回后调用此方法。
        """
        self._completed = True
        self._event.success = success
        self._event.final_output = final_output
        self._event.artifacts = artifacts or []

        return self.evolve()

    def evolve(self) -> dict[str, Any]:
        """
        触发 Phoenix 自进化闭环。
        V0.5 约束：只生成 draft，不自动激活。
        """
        if not self._started:
            return {"error": "Session not started", "evolution_happened": False}

        trajectory = self._event.to_trajectory()

        # 设置任务目标（如果没有在构造时提供）
        if not self._event.task_goal:
            self._event.task_goal = f"hermes_session_{self.session_id}"

        try:
            phoenix = self._get_phoenix()
            return phoenix.evolve_from_trajectory(trajectory)
        except Exception as e:
            # Phoenix 出错不应中断 Hermes 工作流
            return {
                "error": str(e),
                "evolution_happened": False,
                "trajectory": trajectory,
            }

    # ── 快捷方法 ─────────────────────────────────────────────

    def run_full_loop(
        self,
        task_goal: str,
        task_type: str = "general",
        risk_level: str = "low",
    ) -> None:
        """
        手动启动一个 Phoenix 轨迹记录。
        用于 Hermes 任务开始时。
        """
        self.task_goal = task_goal
        self.task_type = task_type
        self.risk_level = risk_level
        self._event.task_goal = task_goal
        self._event.task_type = task_type
        self._event.risk_level = risk_level
        self._started = True
        self._event.timestamp = datetime.now().isoformat()

    def complete_task(
        self,
        success: bool,
        final_output: str = "",
        artifacts: list[str] | None = None,
    ) -> dict[str, Any]:
        """
        手动完成任务并触发自进化。
        相当于 on_task_end + evolve。
        """
        return self.on_task_end(success, final_output, artifacts)

    def get_status(self) -> dict[str, Any]:
        """返回 Phoenix 技能库状态。"""
        try:
            phoenix = self._get_phoenix()
            return phoenix.get_status()
        except Exception as e:
            return {"error": str(e)}

    def log_action(
        self,
        action: str,
        params: dict[str, Any],
        result: str = "",
    ) -> None:
        """手动记录一个 action。"""
        self._action_counter += 1
        self._event.actions.append({
            "action": action,
            "params": params,
            "result": result,
            "logged_at": datetime.now().isoformat(),
        })

    def log_error(
        self,
        phase: str,
        message: str,
        recoverable: bool = True,
    ) -> None:
        """手动记录一个错误。"""
        self._event.errors.append({
            "phase": phase,
            "message": message,
            "recoverable": recoverable,
            "logged_at": datetime.now().isoformat(),
        })

    def log_fix(
        self,
        phase: str,
        strategy: str,
        succeeded: bool,
    ) -> None:
        """手动记录一个修复尝试。"""
        self._event.fixes.append({
            "phase": phase,
            "strategy": strategy,
            "succeeded": succeeded,
            "logged_at": datetime.now().isoformat(),
        })
