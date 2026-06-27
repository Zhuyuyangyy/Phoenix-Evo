"""Base agent adapter framework for Phoenix-Evo."""

from __future__ import annotations

import hashlib
import json
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class EventType(Enum):
    """Types of events in an agent trajectory."""
    TASK_START = "task_start"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    LLM_REQUEST = "llm_request"
    LLM_RESPONSE = "llm_response"
    ERROR = "error"
    FIX = "fix"
    VERIFICATION = "verification"
    TASK_COMPLETE = "task_complete"
    RISK_SIGNAL = "risk_signal"


@dataclass
class TrajectoryEvent:
    """A single event in an agent's execution trajectory."""
    timestamp: float
    agent_id: str
    task_id: str
    event_type: EventType
    input_context_hash: str | None = None
    tool_name: str | None = None
    tool_args_redacted: dict[str, Any] | None = None
    tool_result_summary: str | None = None
    model_name: str | None = None
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    error_type: str | None = None
    error_message: str | None = None
    risk_signal: str | None = None
    verification_result: bool | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class TaskSpec:
    """Specification for a task to be executed by an agent."""
    task_id: str
    description: str
    task_type: str = "general"
    risk_level: str = "low"
    allowed_tools: list[str] = field(default_factory=list)
    max_steps: int = 50
    max_tokens: int = 100000
    timeout_seconds: int = 600
    injected_context: dict[str, Any] | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentRunResult:
    """Result of an agent run."""
    task_id: str
    success: bool
    final_output: str | None = None
    error: str | None = None
    events: list[TrajectoryEvent] = field(default_factory=list)
    total_tokens: int = 0
    total_steps: int = 0
    duration_seconds: float = 0.0
    artifacts: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_trajectory(self) -> dict[str, Any]:
        """Convert the run result to a trajectory dictionary."""
        return {
            "task_id": self.task_id,
            "success": self.success,
            "final_output": self.final_output,
            "error": self.error,
            "total_tokens": self.total_tokens,
            "total_steps": self.total_steps,
            "duration_seconds": self.duration_seconds,
            "events": [
                {
                    "timestamp": e.timestamp,
                    "agent_id": e.agent_id,
                    "task_id": e.task_id,
                    "event_type": e.event_type.value,
                    "input_context_hash": e.input_context_hash,
                    "tool_name": e.tool_name,
                    "tool_args_redacted": e.tool_args_redacted,
                    "tool_result_summary": e.tool_result_summary,
                    "model_name": e.model_name,
                    "prompt_tokens": e.prompt_tokens,
                    "completion_tokens": e.completion_tokens,
                    "error_type": e.error_type,
                    "error_message": e.error_message,
                    "risk_signal": e.risk_signal,
                    "verification_result": e.verification_result,
                    "metadata": e.metadata,
                }
                for e in self.events
            ],
            "artifacts": self.artifacts,
            "metadata": self.metadata,
        }


def compute_context_hash(context: Any) -> str:
    """Compute a hash of the input context for traceability."""
    serialized = json.dumps(context, sort_keys=True, default=str)
    return hashlib.sha256(serialized.encode()).hexdigest()[:16]


class AgentAdapter(ABC):
    """Abstract base class for agent adapters.

    Provides hooks for instrumenting agent execution with Phoenix safety
    mechanisms at key points in the agent lifecycle.
    """

    def __init__(self, agent_id: str, model_name: str = "unknown"):
        self.agent_id = agent_id
        self.model_name = model_name
        self._events: list[TrajectoryEvent] = []

    def _record_event(self, event_type: EventType, **kwargs: Any) -> TrajectoryEvent:
        """Record a trajectory event."""
        event = TrajectoryEvent(
            timestamp=time.time(),
            agent_id=self.agent_id,
            task_id=kwargs.get("task_id", ""),
            event_type=event_type,
            **{k: v for k, v in kwargs.items() if k != "task_id"},
        )
        self._events.append(event)
        return event

    @abstractmethod
    def run_task(self, task: TaskSpec) -> AgentRunResult:
        """Execute a task and return the result."""
        ...

    def before_task(self, task: TaskSpec) -> None:
        """Hook called before task execution begins."""
        self._record_event(
            EventType.TASK_START,
            task_id=task.task_id,
            input_context_hash=compute_context_hash(task.description),
            metadata={"task_type": task.task_type, "risk_level": task.risk_level},
        )

    def before_context_injection(self, task: TaskSpec, context: dict[str, Any]) -> dict[str, Any]:
        """Hook called before injecting context into the agent. Returns possibly modified context."""
        return context

    def before_tool_call(self, task_id: str, tool_name: str, tool_args: dict[str, Any]) -> dict[str, Any]:
        """Hook called before a tool invocation. Returns possibly modified args."""
        self._record_event(
            EventType.TOOL_CALL,
            task_id=task_id,
            tool_name=tool_name,
            tool_args_redacted=self._redact_args(tool_args),
        )
        return tool_args

    def after_tool_call(self, task_id: str, tool_name: str, result: Any) -> None:
        """Hook called after a tool invocation."""
        self._record_event(
            EventType.TOOL_RESULT,
            task_id=task_id,
            tool_name=tool_name,
            tool_result_summary=str(result)[:200] if result else None,
        )

    def after_task(self, task: TaskSpec, result: AgentRunResult) -> None:
        """Hook called after task execution completes."""
        self._record_event(
            EventType.TASK_COMPLETE,
            task_id=task.task_id,
            metadata={"success": result.success},
        )

    def after_failure(self, task: TaskSpec, error: Exception) -> None:
        """Hook called when a task fails."""
        self._record_event(
            EventType.ERROR,
            task_id=task.task_id,
            error_type=type(error).__name__,
            error_message=str(error),
        )

    def after_success(self, task: TaskSpec, result: AgentRunResult) -> None:
        """Hook called when a task succeeds."""
        self._record_event(
            EventType.VERIFICATION,
            task_id=task.task_id,
            verification_result=True,
        )

    @staticmethod
    def _redact_args(args: dict[str, Any]) -> dict[str, Any]:
        """Redact sensitive values from tool arguments."""
        sensitive_keys = {
            "api_key", "token", "password", "secret", "credential",
            "auth", "private_key", "access_key", "secret_key",
        }
        redacted = {}
        for k, v in args.items():
            if any(s in k.lower() for s in sensitive_keys):
                redacted[k] = "***REDACTED***"
            elif isinstance(v, dict):
                redacted[k] = AgentAdapter._redact_args(v)
            else:
                redacted[k] = v
        return redacted
