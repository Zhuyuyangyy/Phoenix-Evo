"""Skill versioning system for Phoenix-Evo."""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class SkillState(Enum):
    DRAFT = "draft"
    REVIEW = "review"
    PUBLISHED = "published"
    DEPRECATED = "deprecated"
    REVOKED = "revoked"


@dataclass
class SkillVersion:
    """Represents a versioned skill."""
    skill_id: str
    version: str  # semver
    name: str
    description: str
    code_hash: str
    created_at: float = field(default_factory=time.time)
    author: str = ""
    parent_version: str | None = None
    changelog: str = ""
    dependencies: list[str] = field(default_factory=list)
    state: SkillState = SkillState.DRAFT
    signature: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "skill_id": self.skill_id,
            "version": self.version,
            "name": self.name,
            "description": self.description,
            "code_hash": self.code_hash,
            "created_at": self.created_at,
            "author": self.author,
            "parent_version": self.parent_version,
            "changelog": self.changelog,
            "dependencies": self.dependencies,
            "state": self.state.value,
            "signature": self.signature,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SkillVersion:
        data = dict(data)
        data["state"] = SkillState(data.get("state", "draft"))
        return cls(**data)


class VersionedSkillRegistry:
    """Registry for versioned skills with lineage tracking."""

    def __init__(self):
        self._skills: dict[str, dict[str, SkillVersion]] = {}  # skill_id -> {version -> SkillVersion}

    def register(self, skill: SkillVersion) -> None:
        """Register a skill version."""
        if skill.skill_id not in self._skills:
            self._skills[skill.skill_id] = {}
        self._skills[skill.skill_id][skill.version] = skill

    def get(self, skill_id: str, version: str | None = None) -> SkillVersion | None:
        """Get a skill by ID and optional version (latest if None)."""
        versions = self._skills.get(skill_id, {})
        if not versions:
            return None
        if version:
            return versions.get(version)
        # Return latest published version
        published = [v for v in versions.values() if v.state == SkillState.PUBLISHED]
        if published:
            return max(published, key=lambda v: v.created_at)
        return max(versions.values(), key=lambda v: v.created_at)

    def get_lineage(self, skill_id: str) -> list[SkillVersion]:
        """Get the full lineage of a skill."""
        versions = self._skills.get(skill_id, {})
        if not versions:
            return []

        # Build lineage by following parent_version links
        latest = self.get(skill_id)
        if not latest:
            return []

        lineage = [latest]
        current = latest
        while current.parent_version:
            parent = versions.get(current.parent_version)
            if parent:
                lineage.append(parent)
                current = parent
            else:
                break

        lineage.reverse()
        return lineage

    def list_versions(self, skill_id: str) -> list[str]:
        """List all versions of a skill."""
        return list(self._skills.get(skill_id, {}).keys())

    def deprecate(self, skill_id: str, version: str) -> bool:
        """Deprecate a specific version."""
        skill = self.get(skill_id, version)
        if skill:
            skill.state = SkillState.DEPRECATED
            return True
        return False

    def revoke(self, skill_id: str, version: str) -> bool:
        """Revoke a specific version."""
        skill = self.get(skill_id, version)
        if skill:
            skill.state = SkillState.REVOKED
            return True
        return False

    def search(self, query: str) -> list[SkillVersion]:
        """Search skills by name or description."""
        results = []
        query_lower = query.lower()
        for versions in self._skills.values():
            for skill in versions.values():
                if (query_lower in skill.name.lower() or
                    query_lower in skill.description.lower()):
                    results.append(skill)
        return results


class SkillSigner:
    """Signs and verifies skill integrity."""

    def __init__(self, secret_key: str = "default_key"):
        self._secret_key = secret_key

    def sign(self, skill: SkillVersion) -> str:
        """Sign a skill version."""
        payload = json.dumps({
            "skill_id": skill.skill_id,
            "version": skill.version,
            "code_hash": skill.code_hash,
        }, sort_keys=True)
        message = f"{payload}:{self._secret_key}"
        return hashlib.sha256(message.encode()).hexdigest()

    def verify(self, skill: SkillVersion) -> bool:
        """Verify a skill's signature."""
        if not skill.signature:
            return False
        expected = self.sign(SkillVersion(
            skill_id=skill.skill_id,
            version=skill.version,
            name=skill.name,
            description=skill.description,
            code_hash=skill.code_hash,
        ))
        return skill.signature == expected

    @staticmethod
    def compute_code_hash(code: str) -> str:
        """Compute a hash of skill code."""
        return hashlib.sha256(code.encode()).hexdigest()[:16]


class SkillStateMachine:
    """Manages skill state transitions."""

    TRANSITIONS = {
        SkillState.DRAFT: {SkillState.REVIEW, SkillState.REVOKED},
        SkillState.REVIEW: {SkillState.PUBLISHED, SkillState.DRAFT, SkillState.REVOKED},
        SkillState.PUBLISHED: {SkillState.DEPRECATED, SkillState.REVOKED},
        SkillState.DEPRECATED: {SkillState.REVOKED},
        SkillState.REVOKED: set(),  # Terminal state
    }

    def can_transition(self, current: SkillState, target: SkillState) -> bool:
        """Check if a state transition is valid."""
        return target in self.TRANSITIONS.get(current, set())

    def transition(self, skill: SkillVersion, target: SkillState) -> bool:
        """Attempt to transition a skill to a new state."""
        if self.can_transition(skill.state, target):
            skill.state = target
            return True
        return False

    def get_valid_transitions(self, current: SkillState) -> list[SkillState]:
        """Get valid transitions from the current state."""
        return list(self.TRANSITIONS.get(current, set()))
