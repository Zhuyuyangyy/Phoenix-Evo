"""
Phoenix-Evo Runtime Skill Router
V0.6 - Hermes Bridge Integration Layer

对外暴露的完整 Runtime Skill Router 能力。
"""

from .context_injector import ContextInjector, attach_skill_data_to_route
from .fallback_manager import FallbackManager, FallbackReason, FallbackResult
from .phoenix_runtime import PhoenixRuntime
from .runtime_guard import GuardDecision, GuardResult, RuntimeGuard
from .runtime_reporter import RuntimeCallRecord, RuntimeReporter
from .skill_retriever import SkillRetriever
from .skill_router import RouteDecision, RouteResult, SkillRouter

__all__ = [
    # 检索 & 路由
    "SkillRetriever",
    "SkillRouter",
    "RouteResult",
    "RouteDecision",
    # 安全闸门
    "RuntimeGuard",
    "GuardResult",
    "GuardDecision",
    # Fallback
    "FallbackManager",
    "FallbackResult",
    "FallbackReason",
    # 记录器
    "RuntimeReporter",
    "RuntimeCallRecord",
    # 上下文注入
    "ContextInjector",
    "attach_skill_data_to_route",
    # 统一调度
    "PhoenixRuntime",
]
