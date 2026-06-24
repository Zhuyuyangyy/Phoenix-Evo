"""Offline skill access for Phoenix-Evo distributed system."""

from __future__ import annotations

import hashlib
import json
import os
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class OfflineSkill:
    """A skill stored for offline access."""
    skill_id: str
    version: str
    code: str
    checksum: str
    downloaded_at: float = field(default_factory=time.time)
    expires_at: Optional[float] = None
    size_bytes: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def is_expired(self) -> bool:
        if self.expires_at is None:
            return False
        return time.time() > self.expires_at

    def verify_checksum(self) -> bool:
        """Verify the skill's checksum."""
        actual = hashlib.sha256(self.code.encode()).hexdigest()[:16]
        return actual == self.checksum


class OfflineSkillAccess:
    """Provides offline access to skills.

    Downloads and caches skills for use when network
    connectivity is unavailable.
    """

    def __init__(self, storage_dir: str = ".phoenix_offline"):
        self.storage_dir = storage_dir
        self._skills: Dict[str, OfflineSkill] = {}
        self._load_from_disk()

    def _load_from_disk(self) -> None:
        """Load cached skills from disk."""
        if not os.path.exists(self.storage_dir):
            return

        for filename in os.listdir(self.storage_dir):
            if filename.endswith(".offline.json"):
                filepath = os.path.join(self.storage_dir, filename)
                try:
                    with open(filepath, "r") as f:
                        data = json.load(f)
                    skill = OfflineSkill(
                        skill_id=data["skill_id"],
                        version=data["version"],
                        code=data["code"],
                        checksum=data["checksum"],
                        downloaded_at=data.get("downloaded_at", time.time()),
                        expires_at=data.get("expires_at"),
                        size_bytes=data.get("size_bytes", 0),
                        metadata=data.get("metadata", {}),
                    )
                    self._skills[skill.skill_id] = skill
                except (json.JSONDecodeError, KeyError):
                    continue

    def download(self, skill_id: str, code: str, version: str = "1.0.0",
                 ttl_seconds: Optional[float] = None) -> OfflineSkill:
        """Download a skill for offline use."""
        checksum = hashlib.sha256(code.encode()).hexdigest()[:16]
        expires_at = time.time() + ttl_seconds if ttl_seconds else None

        skill = OfflineSkill(
            skill_id=skill_id,
            version=version,
            code=code,
            checksum=checksum,
            expires_at=expires_at,
            size_bytes=len(code.encode()),
        )
        self._skills[skill_id] = skill

        # Persist to disk
        os.makedirs(self.storage_dir, exist_ok=True)
        filepath = os.path.join(self.storage_dir, f"{skill_id}.offline.json")
        with open(filepath, "w") as f:
            json.dump({
                "skill_id": skill.skill_id,
                "version": skill.version,
                "code": skill.code,
                "checksum": skill.checksum,
                "downloaded_at": skill.downloaded_at,
                "expires_at": skill.expires_at,
                "size_bytes": skill.size_bytes,
                "metadata": skill.metadata,
            }, f, default=str)

        return skill

    def get(self, skill_id: str) -> Optional[OfflineSkill]:
        """Get an offline skill by ID."""
        skill = self._skills.get(skill_id)
        if skill and not skill.is_expired:
            return skill
        return None

    def list_available(self) -> List[OfflineSkill]:
        """List all available offline skills (non-expired)."""
        return [s for s in self._skills.values() if not s.is_expired]

    def remove(self, skill_id: str) -> bool:
        """Remove an offline skill."""
        if skill_id in self._skills:
            del self._skills[skill_id]
            filepath = os.path.join(self.storage_dir, f"{skill_id}.offline.json")
            if os.path.exists(filepath):
                os.remove(filepath)
            return True
        return False

    def cleanup_expired(self) -> int:
        """Remove expired skills. Returns count of removed skills."""
        expired = [sid for sid, skill in self._skills.items() if skill.is_expired]
        for sid in expired:
            self.remove(sid)
        return len(expired)

    def verify_all(self) -> Dict[str, bool]:
        """Verify checksums of all offline skills."""
        return {
            sid: skill.verify_checksum()
            for sid, skill in self._skills.items()
        }

    def get_status(self) -> Dict[str, Any]:
        """Get offline access status."""
        available = self.list_available()
        total_size = sum(s.size_bytes for s in available)
        return {
            "total_skills": len(self._skills),
            "available_skills": len(available),
            "expired_skills": len(self._skills) - len(available),
            "total_size_bytes": total_size,
            "storage_dir": self.storage_dir,
        }
