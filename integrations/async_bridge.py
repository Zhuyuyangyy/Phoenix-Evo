"""
Phoenix-Evo V0.5 Async Bridge
解决 Hermes（异步）与 Phoenix（同步）的调用模式差异。

问题：
- Hermes 是 async 主循环，Phoenix 是同步函数调用
- 自进化闭环不应阻塞 Hermes 的主执行链
- 但 Phoenix 的 evolve_from_trajectory 需要在任务结束后同步调用

方案：队列解耦
```
Hermes event → event queue → Phoenix worker → skill draft
                 (非阻塞)        (后台线程)        (异步写入)
```

Hermes 主线程：直接入队，立即返回
Phoenix worker：后台线程消费队列，调用 Phoenix 闭环

V0.5 约束：
- event queue 有界（maxsize=100），满则丢弃最旧事件
- Phoenix worker 异常不能泄露到 Hermes 主线程
- 不在 Hermes 主线程中调用任何 Phoenix 同步阻塞操作
"""

from __future__ import annotations

import atexit
import logging
import queue
import threading
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from threading import Thread
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class PhoenixEvent:
    """
    Phoenix 可以消费的事件类型。
    """
    # 事件类型
    type: str = ""
    # 时间戳
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    # 事件数据
    data: dict[str, Any] = field(default_factory=dict)


class AsyncBridge:
    """
    异步桥接器。

    使用方式（Hermes 端）：

    ```python
    from integrations.async_bridge import AsyncBridge

    bridge = AsyncBridge(
        phoenix_base_dir=Path("/path/to/Phoenix-Evo"),
        queue_maxsize=100,
    )
    bridge.start()

    # Hermes 事件直接入队，不阻塞
    bridge.enqueue("tool_complete", {
        "tool_name": "read_file",
        "args": {"path": "/tmp/foo.py"},
        "result": "file content...",
        "error": "",
    })

    # 任务结束后通知完成（触发 Phoenix 闭环）
    bridge.enqueue("task_end", {
        "session_id": "abc123",
        "success": True,
        "final_output": "...",
        "artifacts": [],
    })

    # Hermes 退出时优雅关闭
    bridge.stop()
    ```

    V0.5 约束：
    - Phoenix worker 异常不能 crash Hermes
    - 队列满时丢弃最旧事件，不阻塞 Hermes
    - stop() 等待 worker 最多 5 秒
    """

    QUEUE_EVENT_TYPES = frozenset([
        "task_start",
        "tool_call",
        "tool_complete",
        "error",
        "fix",
        "task_end",
        "session_end",
    ])

    def __init__(
        self,
        phoenix_base_dir: Path | str | None = None,
        queue_maxsize: int = 100,
        worker_name: str = "PhoenixWorker",
    ):
        if phoenix_base_dir is None:
            phoenix_base_dir = Path(__file__).parent.parent
        elif isinstance(phoenix_base_dir, str):
            phoenix_base_dir = Path(phoenix_base_dir)

        self.phoenix_base_dir = phoenix_base_dir

        # 有界队列：满则丢最旧事件，不阻塞 Hermes
        self._queue: queue.Queue[PhoenixEvent] = queue.Queue(maxsize=queue_maxsize)
        self._running = False
        self._worker_thread: Thread | None = None
        self._worker_name = worker_name
        self._stop_event = threading.Event()

        # Phoenix 核心（延迟导入）
        self._phoenix = None

        # 注册退出清理
        atexit.register(self.stop)

    # ── Phoenix 懒加载 ───────────────────────────────────────

    def _get_phoenix(self):
        """懒加载 Phoenix 核心。"""
        if self._phoenix is None:
            try:
                from core import PhoenixEvo
                self._phoenix = PhoenixEvo(base_dir=self.phoenix_base_dir)
            except Exception as e:
                raise RuntimeError(
                    f"Phoenix-Evo 导入失败: {e}"
                )
        return self._phoenix

    # ── 公共 API ─────────────────────────────────────────────

    def start(self) -> None:
        """
        启动 Phoenix 后台 worker。
        必须在 Hermes 事件循环开始前调用。
        """
        if self._running:
            logger.warning("AsyncBridge 已在运行中")
            return

        self._running = True
        self._stop_event.clear()
        self._worker_thread = threading.Thread(
            target=self._worker_loop,
            name=self._worker_name,
            daemon=True,  # daemon=True 确保进程退出时自动终止
        )
        self._worker_thread.start()
        logger.info("Phoenix AsyncBridge worker 已启动")

    def stop(self, timeout: float = 5.0) -> None:
        """
        优雅停止 Phoenix worker。

        Args:
            timeout: 最多等待 worker 结束的时间（秒）
        """
        if not self._running:
            return

        self._running = False
        self._stop_event.set()

        if self._worker_thread and self._worker_thread.is_alive():
            self._worker_thread.join(timeout=timeout)
            if self._worker_thread.is_alive():
                logger.warning("Phoenix worker 未能在 %.1fs 内停止", timeout)

        self._worker_thread = None
        logger.info("Phoenix AsyncBridge worker 已停止")

    def enqueue(
        self,
        event_type: str,
        data: dict[str, Any],
        timeout: float = 0.0,
    ) -> bool:
        """
        把事件加入 Phoenix worker 队列。

        Args:
            event_type: 事件类型（见 QUEUE_EVENT_TYPES）
            data: 事件数据
            timeout: 阻塞超时（0=非阻塞，默认 0）

        Returns:
            True=入队成功，False=队列满/已停止
        """
        if not self._running:
            return False

        if event_type not in self.QUEUE_EVENT_TYPES:
            logger.warning("未知事件类型: %s", event_type)
            return False

        event = PhoenixEvent(type=event_type, data=data)

        try:
            self._queue.put(event, block=(timeout > 0), timeout=timeout)
            return True
        except queue.Full:
            # 队列满：丢弃最旧事件，再次尝试
            try:
                self._queue.get_nowait()  # 丢弃最旧
                self._queue.put_nowait(event)  # 放入新事件
                logger.debug("队列满，已丢弃最旧事件")
                return True
            except queue.Full:
                logger.warning("Phoenix 事件队列已满，事件丢弃: %s", event_type)
                return False

    def is_running(self) -> bool:
        """检查 worker 是否在运行。"""
        return self._running and self._worker_thread is not None and self._worker_thread.is_alive()

    def queue_size(self) -> int:
        """返回队列当前大小。"""
        return self._queue.qsize()

    # ── Worker 循环 ─────────────────────────────────────────

    def _worker_loop(self) -> None:
        """
        Phoenix worker 主循环。
        在独立线程中运行，消费事件队列并触发自进化闭环。
        """
        logger.info("Phoenix worker 线程启动")

        while not self._stop_event.is_set():
            try:
                # 等待事件，最多等 1 秒（检查 _stop_event）
                try:
                    event = self._queue.get(block=True, timeout=1.0)
                except queue.Empty:
                    continue

                self._process_event(event)

            except Exception as e:
                # 捕获所有异常，确保 worker 不崩溃
                logger.error("Phoenix worker 异常: %s", e, exc_info=True)

        logger.info("Phoenix worker 线程退出")

    def _process_event(self, event: PhoenixEvent) -> None:
        """
        处理单个事件。
        V0.5：只处理 task_end 触发完整闭环。
        其他事件用于累积轨迹上下文。
        """
        if event.type == "task_end":
            self._handle_task_end(event)
        elif event.type == "session_end":
            self._handle_session_end(event)
        elif event.type in ("tool_call", "tool_complete"):
            self._accumulate_context(event)
        # task_start/error/fix 目前暂存，V0.6 才用上

    def _handle_task_end(self, event: PhoenixEvent) -> None:
        """处理任务结束事件：触发 Phoenix 完整自进化闭环。"""
        data = event.data
        trajectory = data.get("trajectory", {})
        data.get("task_goal", "hermes_task")

        if not trajectory:
            logger.warning("task_end 事件缺少 trajectory 数据")
            return

        try:
            phoenix = self._get_phoenix()
            report = phoenix.evolve_from_trajectory(trajectory)
            logger.info(
                "Phoenix 自进化完成: skill_id=%s decision=%s evolution=%s",
                report.get("registry_entry", {}).get("skill_id", "none"),
                report.get("immune_guard", {}).get("decision", "none"),
                report.get("evolution_happened", False),
            )
        except Exception as e:
            logger.error("Phoenix evolve_from_trajectory 失败: %s", e)

    def _handle_session_end(self, event: PhoenixEvent) -> None:
        """会话结束：清理上下文。"""
        # V0.5 暂不处理，V0.6 实现跨任务上下文累积

    def _accumulate_context(self, event: PhoenixEvent) -> None:
        """
        累积工具调用上下文。
        V0.5：暂存到内存，task_end 时组装成完整 trajectory。
        V0.6：Phoenix 支持增量轨迹更新。
        """
        # V0.5 暂不实现增量累积，Phoenix 目前需要一次性完整 trajectory
