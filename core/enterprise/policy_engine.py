"""Policy engine for Phoenix-Evo enterprise features."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional


class PolicyEffect(Enum):
    ALLOW = "allow"
    DENY = "deny"


@dataclass
class Policy:
    """A policy rule that can allow or deny actions."""
    policy_id: str
    name: str
    description: str = ""
    effect: PolicyEffect = PolicyEffect.DENY
    resource_type: str = "*"
    action: str = "*"
    condition: Optional[Dict[str, Any]] = None
    priority: int = 0  # Higher priority wins
    enabled: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)

    def matches(self, resource_type: str, action: str, context: Optional[Dict[str, Any]] = None) -> bool:
        """Check if this policy matches the given request."""
        if not self.enabled:
            return False

        # Check resource type (supports wildcards)
        if self.resource_type != "*" and self.resource_type != resource_type:
            return False

        # Check action (supports wildcards)
        if self.action != "*" and self.action != action:
            return False

        # Check conditions
        if self.condition and context:
            for key, expected in self.condition.items():
                actual = context.get(key)
                if actual != expected:
                    return False

        return True


class PolicyEngine:
    """Evaluates policies to determine allow/deny decisions."""

    def __init__(self, default_effect: PolicyEffect = PolicyEffect.DENY):
        self.default_effect = default_effect
        self._policies: Dict[str, Policy] = {}

    def add_policy(self, policy: Policy) -> None:
        """Add a policy to the engine."""
        self._policies[policy.policy_id] = policy

    def remove_policy(self, policy_id: str) -> bool:
        """Remove a policy."""
        if policy_id in self._policies:
            del self._policies[policy_id]
            return True
        return False

    def evaluate(
        self,
        resource_type: str,
        action: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Evaluate policies for a given request.

        Returns a decision dict with 'allowed', 'matched_policies', and 'reason'.
        """
        matching = []
        for policy in self._policies.values():
            if policy.matches(resource_type, action, context):
                matching.append(policy)

        if not matching:
            return {
                "allowed": self.default_effect == PolicyEffect.ALLOW,
                "matched_policies": [],
                "reason": f"default_effect: {self.default_effect.value}",
            }

        # Sort by priority (highest first)
        matching.sort(key=lambda p: p.priority, reverse=True)

        # Use the highest-priority policy's effect
        top_policy = matching[0]
        return {
            "allowed": top_policy.effect == PolicyEffect.ALLOW,
            "matched_policies": [p.policy_id for p in matching],
            "reason": f"policy: {top_policy.policy_id} ({top_policy.effect.value})",
        }

    def list_policies(self, enabled_only: bool = False) -> List[Policy]:
        """List all policies."""
        policies = list(self._policies.values())
        if enabled_only:
            policies = [p for p in policies if p.enabled]
        return sorted(policies, key=lambda p: p.priority, reverse=True)

    def get_policy(self, policy_id: str) -> Optional[Policy]:
        """Get a specific policy."""
        return self._policies.get(policy_id)

    def update_policy(self, policy_id: str, **kwargs: Any) -> bool:
        """Update a policy's properties."""
        policy = self._policies.get(policy_id)
        if not policy:
            return False
        for k, v in kwargs.items():
            if hasattr(policy, k):
                setattr(policy, k, v)
        return True
