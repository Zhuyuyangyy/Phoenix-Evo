"""
SkillRegistry: 技能库管理器
V0.1 - Phoenix-Evo

职责：管理技能生命周期（candidate -> draft -> active -> stale -> archived）。
      V0.1: 只允许写入 draft，不允许自动激活。
      更新 skill_index.json 作为技能库的索引。
"""

import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

from .skill_verifier import VerificationResult


class SkillRegistry:
    def __init__(self, root: Path | None = None):
        self.root = Path(root) if root else Path(__file__).parent.parent
        self.skills_dir   = self.root / "skills"
        self.draft_dir    = self.skills_dir / "draft"
        self.active_dir   = self.skills_dir / "active"
        self.archived_dir = self.skills_dir / "archived"
        for d in [self.draft_dir, self.active_dir, self.archived_dir]:
            d.mkdir(parents=True, exist_ok=True)
        self._index_path = self.skills_dir / "skill_index.json"

    def add_draft(self, skill: dict[str, Any], verify_result: VerificationResult) -> Path:
        skill_id  = skill["skill_id"]
        skill_md  = skill["skill_md"]
        file_path = self.draft_dir / f"{skill_id}.md"
        index = self._load_index()
        index[skill_id] = {
            "skill_id":    skill_id,
            "skill_name":  skill.get("skill_name", skill_id),
            "status":      "draft",
            "source_trajectory": skill.get("source_trajectory", ""),
            "quality_score": skill.get("quality_score", 0.0),
            "risk_level":  verify_result.risk_level,
            "confidence":   verify_result.confidence,
            "created_at":  datetime.now().isoformat(),
            "usage_count": 0,
            "success_rate": None,
            "last_used":   None,
            "verify_reason": verify_result.reason,
            "warnings":    verify_result.warnings,
            "activate_level": verify_result.activation_level,
        }
        self._save_index(index)
        file_path.write_text(skill_md, encoding="utf-8")
        return file_path

    def reject(self, skill: dict[str, Any], reason: str) -> None:
        index = self._load_index()
        skill_id = skill.get("skill_id", "unknown")
        index[f"__rejected__{skill_id}"] = {
            "skill_id":    skill_id,
            "skill_name":  skill.get("skill_name", ""),
            "status":      "rejected",
            "reason":      reason,
            "rejected_at": datetime.now().isoformat(),
        }
        self._save_index(index)

    def activate(self, skill_id: str, approved_by: str = "human") -> Path | None:
        index = self._load_index()
        if skill_id not in index:
            return None
        entry = index[skill_id]
        if entry["status"] != "draft":
            return None
        draft_path = self.draft_dir / f"{skill_id}.md"
        if not draft_path.exists():
            return None
        active_path = self.active_dir / f"{skill_id}.md"
        shutil.move(str(draft_path), str(active_path))
        entry["status"]      = "active"
        entry["activated_at"] = datetime.now().isoformat()
        entry["approved_by"]  = approved_by
        self._save_index(index)
        return active_path

    def archive(self, skill_id: str, reason: str = "") -> bool:
        index = self._load_index()
        if skill_id not in index:
            return False
        entry = index[skill_id]
        for folder, dir_path in [("active", self.active_dir), ("draft", self.draft_dir)]:
            p = dir_path / f"{skill_id}.md"
            if p.exists():
                archived_path = self.archived_dir / f"{skill_id}.md"
                shutil.move(str(p), str(archived_path))
                break
        entry["status"]       = "archived"
        entry["archived_at"]  = datetime.now().isoformat()
        entry["archive_reason"] = reason
        self._save_index(index)
        return True

    def record_usage(self, skill_id: str, success: bool) -> None:
        index = self._load_index()
        if skill_id not in index:
            return
        entry = index[skill_id]
        entry["usage_count"] = entry.get("usage_count", 0) + 1
        total     = entry["usage_count"]
        successes = entry.get("success_count", 0) + (1 if success else 0)
        entry["success_count"] = successes
        entry["success_rate"]  = round(successes / total, 3)
        entry["last_used"]     = datetime.now().isoformat()
        self._save_index(index)

    def get_index(self) -> dict[str, Any]:
        return self._load_index()

    def get_active_skills(self) -> list[dict[str, Any]]:
        index = self._load_index()
        return [v for v in index.values() if v.get("status") == "active"]

    def get_draft_skills(self) -> list[dict[str, Any]]:
        index = self._load_index()
        return [v for v in index.values() if v.get("status") == "draft"]

    def find_similar(self, skill_name: str) -> list[str]:
        index = self._load_index()
        similar = []
        lower_name = skill_name.lower()
        for entry in index.values():
            if entry.get("status") in ("active", "draft"):
                en = entry.get("skill_name", "").lower()
                if en and (lower_name in en or en in lower_name):
                    similar.append(entry["skill_id"])
        return similar

    def _load_index(self) -> dict[str, Any]:
        if not self._index_path.exists():
            return {}
        try:
            return json.loads(self._index_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, IOError):
            return {}

    def _save_index(self, index: dict) -> None:
        self._index_path.parent.mkdir(parents=True, exist_ok=True)
        self._index_path.write_text(
            json.dumps(index, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
