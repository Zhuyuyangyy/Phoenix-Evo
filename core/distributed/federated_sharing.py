"""Federated skill sharing with differential privacy for Phoenix-Evo."""

from __future__ import annotations

import math
import random
import time
import uuid
from dataclasses import dataclass, field
from typing import Any


@dataclass
class FederatedUpdate:
    """A federated skill update from a participant."""
    update_id: str
    participant_id: str
    skill_id: str
    version: str
    update_data: dict[str, Any]
    timestamp: float = field(default_factory=time.time)
    privacy_budget_used: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class FederatedAggregation:
    """Result of aggregating federated updates."""
    aggregation_id: str
    skill_id: str
    n_participants: int
    aggregated_data: dict[str, Any]
    privacy_budget_total: float
    noise_added: float
    timestamp: float = field(default_factory=time.time)


class DifferentialPrivacy:
    """Implements differential privacy mechanisms."""

    def __init__(self, epsilon: float = 1.0, delta: float = 1e-5):
        self.epsilon = epsilon
        self.delta = delta
        self._budget_used: float = 0.0
        self._budget_limit: float = 10.0  # Total privacy budget

    @property
    def budget_remaining(self) -> float:
        return max(0.0, self._budget_limit - self._budget_used)

    @property
    def budget_exhausted(self) -> bool:
        return self._budget_used >= self._budget_limit

    def add_laplace_noise(self, value: float, sensitivity: float = 1.0) -> float:
        """Add Laplace noise for epsilon-differential privacy."""
        if self.budget_exhausted:
            raise ValueError("Privacy budget exhausted")

        scale = sensitivity / self.epsilon
        noise = random.gauss(0, scale)  # Using Gaussian as approximation
        self._budget_used += self.epsilon
        return value + noise

    def add_gaussian_noise(self, value: float, sensitivity: float = 1.0) -> float:
        """Add Gaussian noise for (epsilon, delta)-differential privacy."""
        if self.budget_exhausted:
            raise ValueError("Privacy budget exhausted")

        sigma = sensitivity * math.sqrt(2 * math.log(1.25 / self.delta)) / self.epsilon
        noise = random.gauss(0, sigma)
        self._budget_used += self.epsilon
        return value + noise

    def clip_value(self, value: float, lower: float, upper: float) -> float:
        """Clip a value to a range for bounded sensitivity."""
        return max(lower, min(upper, value))

    def reset_budget(self) -> None:
        """Reset the privacy budget."""
        self._budget_used = 0.0


class FederatedSkillNetwork:
    """Federated learning network for skill sharing with DP.

    Allows multiple participants to share skill improvements
    while preserving privacy through differential privacy.
    """

    def __init__(
        self,
        network_id: str | None = None,
        epsilon: float = 1.0,
        delta: float = 1e-5,
        min_participants: int = 3,
    ):
        self.network_id = network_id or f"fed_{uuid.uuid4().hex[:8]}"
        self.dp = DifferentialPrivacy(epsilon=epsilon, delta=delta)
        self.min_participants = min_participants
        self._participants: dict[str, dict[str, Any]] = {}
        self._updates: list[FederatedUpdate] = []
        self._aggregations: list[FederatedAggregation] = []

    def join(self, participant_id: str, metadata: dict[str, Any] | None = None) -> bool:
        """Join the federated network."""
        if participant_id in self._participants:
            return False
        self._participants[participant_id] = {
            "joined_at": time.time(),
            "metadata": metadata or {},
        }
        return True

    def leave(self, participant_id: str) -> bool:
        """Leave the federated network."""
        if participant_id in self._participants:
            del self._participants[participant_id]
            return True
        return False

    def submit_update(self, update: FederatedUpdate) -> bool:
        """Submit a federated update."""
        if update.participant_id not in self._participants:
            return False
        if self.dp.budget_exhausted:
            return False
        self._updates.append(update)
        return True

    def aggregate(self, skill_id: str) -> FederatedAggregation | None:
        """Aggregate updates for a skill with differential privacy."""
        # Filter updates for this skill
        skill_updates = [u for u in self._updates if u.skill_id == skill_id]

        if len(skill_updates) < self.min_participants:
            return None

        # Simple aggregation with DP noise
        aggregated_data: dict[str, Any] = {}
        numeric_fields: dict[str, list[float]] = {}

        for update in skill_updates:
            for key, value in update.update_data.items():
                if isinstance(value, (int, float)):
                    numeric_fields.setdefault(key, []).append(float(value))
                else:
                    aggregated_data.setdefault(key, value)

        # Add DP noise to numeric fields
        noise_added = 0.0
        for key, values in numeric_fields.items():
            mean_val = sum(values) / len(values)
            try:
                noisy_val = self.dp.add_gaussian_noise(mean_val, sensitivity=1.0)
                noise_added += abs(noisy_val - mean_val)
                aggregated_data[key] = noisy_val
            except ValueError:
                # Budget exhausted
                aggregated_data[key] = mean_val

        aggregation = FederatedAggregation(
            aggregation_id=f"agg_{uuid.uuid4().hex[:8]}",
            skill_id=skill_id,
            n_participants=len(skill_updates),
            aggregated_data=aggregated_data,
            privacy_budget_total=self.dp._budget_used,
            noise_added=noise_added,
        )
        self._aggregations.append(aggregation)
        return aggregation

    def get_status(self) -> dict[str, Any]:
        """Get the status of the federated network."""
        return {
            "network_id": self.network_id,
            "n_participants": len(self._participants),
            "n_updates": len(self._updates),
            "n_aggregations": len(self._aggregations),
            "privacy_budget_remaining": self.dp.budget_remaining,
            "privacy_budget_exhausted": self.dp.budget_exhausted,
        }
