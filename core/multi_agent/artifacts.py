"""Artifact types and management for multi-agent collaboration."""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ArtifactType(Enum):
    """Types of artifacts produced during multi-agent collaboration."""
    CODE = "code"
    DOCUMENTATION = "documentation"
    TEST_RESULT = "test_result"
    REVIEW_COMMENT = "review_comment"
    SECURITY_REPORT = "security_report"
    PLAN = "plan"


@dataclass
class Artifact:
    """An artifact produced during multi-agent collaboration."""
    artifact_id: str
    artifact_type: ArtifactType
    producer_id: str
    content: Any
    created_at: float = field(default_factory=time.time)
    version: int = 1
    parent_ids: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "artifact_id": self.artifact_id,
            "artifact_type": self.artifact_type.value,
            "producer_id": self.producer_id,
            "content": self.content,
            "created_at": self.created_at,
            "version": self.version,
            "parent_ids": self.parent_ids,
            "tags": self.tags,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Artifact:
        data = dict(data)
        data["artifact_type"] = ArtifactType(data.get("artifact_type", "code"))
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})

    def content_hash(self) -> str:
        """Compute a hash of the artifact content for integrity checking."""
        serialized = str(self.content)
        return hashlib.sha256(serialized.encode()).hexdigest()[:16]
