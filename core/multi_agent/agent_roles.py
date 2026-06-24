"""Agent roles and profiles for multi-agent collaboration."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class AgentRole(Enum):
    """Roles that agents can take in multi-agent collaboration."""
    PLANNER = "planner"
    CODER = "coder"
    REVIEWER = "reviewer"
    TESTER = "tester"
    SECURITY_AUDITOR = "security_auditor"
    INTEGRATOR = "integrator"
    COORDINATOR = "coordinator"
    OBSERVER = "observer"


@dataclass
class AgentProfile:
    """Profile of an agent in the multi-agent system."""
    agent_id: str
    role: AgentRole
    name: str = ""
    capabilities: List[str] = field(default_factory=list)
    trust_score: float = 1.0
    max_concurrent_tasks: int = 3
    specializations: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "role": self.role.value,
            "name": self.name,
            "capabilities": self.capabilities,
            "trust_score": self.trust_score,
            "max_concurrent_tasks": self.max_concurrent_tasks,
            "specializations": self.specializations,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AgentProfile":
        data = dict(data)
        data["role"] = AgentRole(data.get("role", "observer"))
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})

    def can_perform(self, capability: str) -> bool:
        """Check if the agent has a specific capability."""
        return capability in self.capabilities

    def is_available(self, current_tasks: int = 0) -> bool:
        """Check if the agent is available for new tasks."""
        return current_tasks < self.max_concurrent_tasks
