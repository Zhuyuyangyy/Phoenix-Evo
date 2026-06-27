"""System health monitor for Phoenix-Evo self-repair system."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

import numpy as np


@dataclass
class HealthCheck:
    """Result of a health check."""
    component: str
    healthy: bool
    latency_ms: float = 0.0
    message: str = ""
    timestamp: float = field(default_factory=time.time)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class SystemHealth:
    """Overall system health status."""
    status: str  # "healthy", "degraded", "unhealthy"
    components: dict[str, HealthCheck]
    overall_score: float  # 0.0 to 1.0
    timestamp: float = field(default_factory=time.time)
    metadata: dict[str, Any] = field(default_factory=dict)


class SystemHealthMonitor:
    """Monitors the health of system components.

    Periodically checks component health and computes
    an overall system health score.
    """

    def __init__(
        self,
        check_interval: float = 60.0,
        unhealthy_threshold: float = 0.5,
        degraded_threshold: float = 0.8,
    ):
        self.check_interval = check_interval
        self.unhealthy_threshold = unhealthy_threshold
        self.degraded_threshold = degraded_threshold
        self._checks: dict[str, HealthCheck] = {}
        self._check_fns: dict[str, callable] = {}
        self._history: list[SystemHealth] = []

    def register_check(self, component: str, check_fn: callable) -> None:
        """Register a health check function for a component."""
        self._check_fns[component] = check_fn

    def check_component(self, component: str) -> HealthCheck:
        """Run a health check for a specific component."""
        check_fn = self._check_fns.get(component)
        if check_fn:
            try:
                result = check_fn()
                if isinstance(result, HealthCheck):
                    self._checks[component] = result
                    return result
                if isinstance(result, bool):
                    check = HealthCheck(component=component, healthy=result)
                    self._checks[component] = check
                    return check
            except Exception as e:
                check = HealthCheck(component=component, healthy=False, message=str(e))
                self._checks[component] = check
                return check

        # Default: return existing check or unknown
        if component in self._checks:
            return self._checks[component]
        return HealthCheck(component=component, healthy=False, message="No check registered")

    def check_all(self) -> SystemHealth:
        """Run all health checks and compute overall health."""
        for component in self._check_fns:
            self.check_component(component)

        # Compute overall score
        if not self._checks:
            return SystemHealth(
                status="unknown",
                components={},
                overall_score=0.0,
            )

        scores = [1.0 if c.healthy else 0.0 for c in self._checks.values()]
        # Factor in latency (penalize slow components)
        for check in self._checks.values():
            if check.healthy and check.latency_ms > 1000:
                scores[self._checks.values().__iter__()._idx] = max(0.5, 1.0 - check.latency_ms / 10000)  # type: ignore

        overall = float(np.mean([1.0 if c.healthy else 0.0 for c in self._checks.values()]))

        # Determine status
        if overall >= self.degraded_threshold:
            status = "healthy"
        elif overall >= self.unhealthy_threshold:
            status = "degraded"
        else:
            status = "unhealthy"

        health = SystemHealth(
            status=status,
            components=dict(self._checks),
            overall_score=overall,
        )
        self._history.append(health)
        return health

    def get_health(self) -> SystemHealth:
        """Get the latest health status without re-running checks."""
        if self._history:
            return self._history[-1]
        return SystemHealth(status="unknown", components={}, overall_score=0.0)

    def get_history(self, limit: int = 100) -> list[SystemHealth]:
        """Get health history."""
        return self._history[-limit:]

    def get_unhealthy_components(self) -> list[str]:
        """Get list of unhealthy components."""
        return [
            comp for comp, check in self._checks.items()
            if not check.healthy
        ]
