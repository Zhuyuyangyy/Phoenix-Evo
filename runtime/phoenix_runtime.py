"""
PhoenixRuntime: Phoenix-Evo 核心运行时编排器
V0.6.3

接收 Hermes task 事件，按以下流程处理：

  task_description
         │
         ▼
  ┌─────────────┐
  │ SkillRouter │ ──► list[RouteResult] (from runtime/skill_router.py)
  └──────┬──────┘
         │
         ▼
  ┌─────────────┐
  │ RuntimeGuard│ ──► list[GuardResult] (一一对应)
  └──────┬──────┘
         │
         ▼
  ┌─────────────────┐
  │ContextInjector  │ ──► context string
  └──────┬──────────┘
         ▼
  ┌─────────────────┐
  │RuntimeReporter  │ ──► RuntimeCallRecord
  └─────────────────┘
         │
         │ no candidate OR all DENY
         ▼
  ┌─────────────────┐
  │ FallbackManager │ ──► FallbackResult
  └─────────────────┘
"""

from __future__ import annotations

import time
import uuid
from pathlib import Path
from typing import Any

from runtime.context_injector import ContextInjector
from runtime.fallback_manager import FallbackManager, FallbackReason
from runtime.runtime_guard import GuardDecision, GuardResult, RuntimeGuard
from runtime.runtime_reporter import RuntimeReporter
from runtime.skill_router import RouteResult, SkillRouter

# ─────────────────────────────────────────────────────────────────────────────
# RuntimeResult — demo_v0.6.py 兼容返回值
# ─────────────────────────────────────────────────────────────────────────────

class RuntimeResult:
    """
    PhoenixRuntime.route() / query() 的返回值。
    兼容 demo_v0.6.py 的断言期望。
    """

    def __init__(
        self,
        skill_found: bool = False,
        injected: bool = False,
        selected_skill_id: str | None = None,
        selected_skill_name: str | None = None,
        route_score: float = 0.0,
        guard_decision: str | None = None,
        fallback_reason: str | None = None,
        context: str = "",
        context_summary: str = "",
        error_message: str | None = None,
        duration_seconds: float = 0.0,
    ):
        self.skill_found = skill_found
        self.injected = injected
        self.selected_skill_id = selected_skill_id
        self.selected_skill_name = selected_skill_name
        self.route_score = route_score
        self.guard_decision = guard_decision
        self.fallback_reason = fallback_reason
        self.context = context
        self.context_summary = context_summary or context
        self.error_message = error_message
        self.duration_seconds = duration_seconds
        self.route_results: list[RouteResult] = []  # Demo4 compat

    # ─────────────────────────────────────────────────────────────────────────
    @classmethod
    def from_route_and_guard(
        cls,
        candidates: list[RouteResult],
        guard_results: list[GuardResult],
        task_description: str,
        task_id: str,
        session_id: str,
        reporter: RuntimeReporter,
    ) -> tuple[RuntimeResult, list[GuardResult]]:
        """
        给定 Router 返回的 candidates + Guard 返回的 guard_results，
        构建 RuntimeResult。
        reporter.record() 同步调用完成记录。
        返回 (RuntimeResult, guard_results) 元组供调用者使用。
        """
        start = time.time()

        # 找第一个 ALLOW 项
        best_idx = None
        for i, gr in enumerate(guard_results):
            if gr.decision == GuardDecision.ALLOW:
                best_idx = i
                break

        if best_idx is not None:
            best_rr = candidates[best_idx]
            best_gr = guard_results[best_idx]
            injector = ContextInjector()
            context_summary = injector.inject(skill=best_rr)

            result = cls(
                skill_found=True,
                injected=True,
                selected_skill_id=best_rr.skill_id,
                selected_skill_name=best_rr.skill_name,
                route_score=best_rr.route_score,
                guard_decision=best_gr.decision.value,
                fallback_reason=None,
                context_summary=context_summary,
                duration_seconds=time.time() - start,
            )
            result.route_results = candidates  # Demo4 compat

            reporter.record(
                task_id=task_id,
                session_id=session_id,
                task_description=task_description,
                selected_skill_id=best_rr.skill_id,
                selected_skill_name=best_rr.skill_name,
                route_score=best_rr.route_score,
                guard_decision=best_gr.decision,
                injected=True,
                context_summary=context_summary,
                duration_seconds=time.time() - start,
            )
            return result, guard_results

        # 无 ALLOW 项 → fallback
        if candidates:
            denied_ids = [rr.skill_id for rr in candidates]
            reason = FallbackReason.ALL_DENIED
        else:
            denied_ids = None
            reason = FallbackReason.NO_SKILL_FOUND

        fb_mgr = FallbackManager()
        fb = fb_mgr.get_fallback(
            task_description=task_description,
            reason=reason,
            denied_skills=denied_ids,
        )
        fb_reason_str = fb.fallback_reason.value if fb.fallback_reason else "no_skill_found"
        guard_decision_str = (
            guard_results[0].decision.value if guard_results else "none"
        )

        result = cls(
            skill_found=False,
            injected=False,
            selected_skill_id=None,
            selected_skill_name=None,
            route_score=0.0,
            guard_decision=guard_decision_str,
            fallback_reason=fb_reason_str,
            context_summary=fb.context,
            duration_seconds=time.time() - start,
        )
        result.route_results = candidates  # Demo4 compat

        reporter.record(
            task_id=task_id,
            session_id=session_id,
            task_description=task_description,
            selected_skill_id=None,
            selected_skill_name=None,
            route_score=0.0,
            guard_decision=GuardDecision.DENY,
            injected=False,
            context_summary=fb.context,
            duration_seconds=time.time() - start,
        )
        return result, guard_results


# ─────────────────────────────────────────────────────────────────────────────
# PhoenixRuntime — 主编排器
# ─────────────────────────────────────────────────────────────────────────────

class PhoenixRuntime:
    """
    Phoenix 技能运行时编排器。

    Demo 说明：
      Demo1  : sync 任务命中 active skill → 注入成功
      Demo2  : draft skill 被 Guard 拒绝 → FallbackManager 接管
      Demo3  : 无匹配 skill → FallbackManager 返回 no_skill_found
      Demo4  : 高 evidence_score 的 skill 排名靠前
      Demo5  : 低 evidence_score → Guard 拒绝 → FallbackManager 接管
      Demo6  : PhoenixRuntime.query() 端到端全流程
    """

    def __init__(
        self,
        base_dir: Path | str | None = None,
        guard_threshold: float = 0.50,
        allow_draft: bool = False,
    ):
        self.base_dir = Path(base_dir) if base_dir else Path(__file__).parent.parent
        self.guard_threshold = guard_threshold
        self.allow_draft = allow_draft

        # 核心组件
        self.router = SkillRouter(base_dir=self.base_dir)    # runtime/skill_router.py
        self.guard = RuntimeGuard()                            # no __init__ params
        self.injector = ContextInjector()                     # no __init__ params
        self.fallback_mgr = FallbackManager()                  # no __init__ params
        self.reporter = RuntimeReporter()                      # no __init__ params

        # 异步队列（Demo2）
        self._queue: list[dict[str, Any]] = []
        self._worker_running = False

    # ─────────────────────────────────────────────────────────────────────────
    # 公开接口
    # ─────────────────────────────────────────────────────────────────────────

    def query(
        self,
        task_description: str,
        task_type: str | None = None,
        risk_level: str | None = None,
        session_id: str | None = None,
        task_id: str | None = None,
    ) -> RuntimeResult:
        """
        PhoenixRuntime 端到端全流程 query 接口（Demo6 期望）。
        """
        session_id = session_id or f"session_{uuid.uuid4().hex[:8]}"
        task_id = task_id or f"task_{uuid.uuid4().hex[:8]}"
        return self.route(
            task_description=task_description,
            task_type=task_type,
            risk_level=risk_level,
            task_id=task_id,
            session_id=session_id,
        )

    def route(
        self,
        task_description: str,
        task_type: str | None = None,
        risk_level: str | None = None,
        task_id: str | None = None,
        session_id: str | None = None,
    ) -> RuntimeResult:
        """
        核心路由方法。串联 Router → Guard → Injector → Reporter → Fallback。

        参数:
            task_description: 任务描述
            task_type:        任务类型（可选）
            risk_level:       风险等级（可选）
            task_id:          任务 ID
            session_id:       会话 ID

        返回:
            RuntimeResult: 兼容 demo_v0.6.py 的返回对象
        """
        task_id = task_id or f"task_{uuid.uuid4().hex[:8]}"
        session_id = session_id or f"session_{uuid.uuid4().hex[:8]}"

        # 1. Router 检索候选（返回 list[RouteResult]）
        candidates: list[RouteResult] = self.router.route(
            task_description=task_description,
            task_type=task_type,
            risk_level=risk_level,
            max_results=3,
        )

        # 2. Guard 对每个候选做安全评估
        guard_results: list[GuardResult] = [
            self.guard.check(rr, task_risk=risk_level or "low")
            for rr in candidates
        ]

        # 3. 构建 RuntimeResult
        result, _ = RuntimeResult.from_route_and_guard(
            candidates=candidates,
            guard_results=guard_results,
            task_description=task_description,
            task_id=task_id,
            session_id=session_id,
            reporter=self.reporter,
        )
        return result

    # ─────────────────────────────────────────────────────────────────────────
    # 异步队列（Demo2）
    # ─────────────────────────────────────────────────────────────────────────

    def enqueue(
        self,
        task_description: str,
        task_type: str | None = None,
        risk_level: str | None = None,
    ) -> str:
        """将任务放入异步队列（Demo2）"""
        task_id = f"task_{uuid.uuid4().hex[:8]}"
        self._queue.append({
            "task_id": task_id,
            "task_description": task_description,
            "task_type": task_type,
            "risk_level": risk_level,
        })
        return task_id

    def process_queue(self, worker_id: str = "worker_1") -> list[RuntimeResult]:
        """单 worker 处理队列中的任务（Demo2）"""
        self._worker_running = True
        processed: list[RuntimeResult] = []
        while self._queue and self._worker_running:
            job = self._queue.pop(0)
            result = self.route(
                task_description=job["task_description"],
                task_type=job.get("task_type"),
                risk_level=job.get("risk_level"),
                task_id=job["task_id"],
                session_id=worker_id,
            )
            processed.append(result)
        self._worker_running = False
        return processed

    def safe_shutdown(self) -> None:
        """安全关闭（Demo2）：等队列清空后退出"""
        self._worker_running = False
